# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Hotel Virtual Assistant Chat Agent Evaluation.

Evaluates the chat agent across multiple Bedrock models using Strands Evals SDK.
Measures:
- Output quality (factual accuracy) for single-turn knowledge queries
- Trajectory efficiency (tool calling) for single-turn queries
- Goal success rate for multi-turn reservation flows via ActorSimulator
- Conversation outcome (custom evaluator that reviews conversation logs to
  validate the simulator's assessment and catch issues like wrong language,
  successful reservations scored as failures, etc.)

Prerequisites:
    - Deployed infrastructure (VirtualAssistantStack + HotelPmsStack)
    - AWS credentials configured
    - `uv sync` run in packages/virtual-assistant/

Usage:
    cd packages/virtual-assistant
    uv run python eval/run_evaluation.py
"""

import asyncio
import contextlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from strands import Agent
from strands.models import BedrockModel
from strands_evals import ActorSimulator, Case, Experiment
from strands_evals.evaluators import Evaluator, GoalSuccessRateEvaluator, OutputEvaluator, TrajectoryEvaluator
from strands_evals.extractors import tools_use_extractor
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.telemetry import StrandsEvalsTelemetry
from strands_evals.types import TaskOutput
from strands_evals.types.evaluation import EvaluationData, EvaluationOutput
from virtual_assistant_chat.agent_factory import AgentFactory
from virtual_assistant_common.mcp.config_manager import MCPConfigManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODELS = [
    "global.amazon.nova-2-lite-v1:0",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-pro-v1:0",
    "us.amazon.nova-micro-v1:0",
    "us.anthropic.claude-3-haiku-20240307-v1:0",
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "us.amazon.nova-lite-v1:0",
]

# Model used by the ActorSimulator (user simulator) and evaluator judges.
JUDGE_MODEL = "global.anthropic.claude-sonnet-4-6"
SIMULATOR_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Bedrock pricing per 1M tokens (verified with AWS Pricing API on Feb 24, 2026)
# Source: AWS Pricing API via MCP server
# Note: Prices shown are for standard on-demand inference in us-east-1
BEDROCK_PRICING = {
    # Nova models - verified pricing
    "global.amazon.nova-2-lite-v1:0": {"input": 0.33, "output": 2.75},  # Nova 2.0 Lite standard
    "us.amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},  # Nova Pro (multiple SKUs, using standard)
    "us.amazon.nova-micro-v1:0": {"input": 0.035, "output": 0.14},  # Nova Micro (multiple SKUs, using standard)
    "us.amazon.nova-lite-v1:0": {"input": 0.06, "output": 0.24},  # Nova Lite (multiple SKUs, using standard)
    
    # Claude models - verified pricing
    "us.anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.25, "output": 1.25},  # Claude 3 Haiku
    
    # Claude 3.5 Haiku and Claude Haiku 4.5 - using estimated pricing
    # Note: These models may use cross-region inference profiles with different pricing
    # Actual pricing should be verified for your specific model ID and region
    "us.anthropic.claude-3-5-haiku-20241022-v1:0": {"input": 0.80, "output": 4.00},  # Estimated
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00, "output": 5.00},  # Estimated
    
    # Judge model (Claude Sonnet 4.6) - estimated pricing
    "global.anthropic.claude-sonnet-4-6": {"input": 3.00, "output": 15.00},  # Estimated
}


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for the given token usage.
    
    Args:
        model_id: Bedrock model ID
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Cost in USD
    """
    pricing = BEDROCK_PRICING.get(model_id, {"input": 0.0, "output": 0.0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

TOOL_DESCRIPTIONS = {
    "hotel_assistant_mcp_query_hotel_knowledge": (
        "Queries the hotel knowledge base for information about hotel amenities, "
        "facilities, restaurants, spa services, activities, room types, and policies."
    ),
    "hotel_pms_mcp_HotelPMS___check_availability": (
        "Checks room availability for given dates, guest count, and hotel. Returns available room types with pricing."
    ),
    "hotel_pms_mcp_HotelPMS___checkout_guest": "Processes guest checkout for an existing reservation.",
    "hotel_pms_mcp_HotelPMS___create_housekeeping_request": (
        "Creates a housekeeping service request for a room or reservation."
    ),
    "hotel_pms_mcp_HotelPMS___create_reservation": (
        "Creates a confirmed reservation using a valid quote ID, guest name, and email. "
        "Requires a prior generate_quote call."
    ),
    "hotel_pms_mcp_HotelPMS___generate_quote": (
        "Generates a price quote for a specific room type, dates, and guest count. "
        "Must be called before creating a reservation."
    ),
    "hotel_pms_mcp_HotelPMS___get_hotels": "Retrieves the list of available hotels with their details.",
    "hotel_pms_mcp_HotelPMS___get_reservation": "Retrieves details of a specific reservation by ID.",
    "hotel_pms_mcp_HotelPMS___get_reservations": (
        "Retrieves a list of reservations, optionally filtered by guest or hotel."
    ),
    "hotel_pms_mcp_HotelPMS___update_reservation": (
        "Updates an existing reservation with new details such as dates or room type."
    ),
}

EVAL_DIR = Path(__file__).parent
TEST_CASES_FILE = EVAL_DIR / "test-cases.jsonl"
RESULTS_DIR = EVAL_DIR / "results"


# ---------------------------------------------------------------------------
# Infrastructure bootstrap (mirrors integration test conftest.py)
# ---------------------------------------------------------------------------


def load_cloudformation_outputs() -> dict[str, str]:
    """Load outputs from deployed CloudFormation stacks."""
    cfn = boto3.client("cloudformation")
    outputs: dict[str, str] = {}

    for stack_name in ("VirtualAssistantStack", "HotelPmsStack"):
        try:
            resp = cfn.describe_stacks(StackName=stack_name)
            for o in resp["Stacks"][0].get("Outputs", []):
                outputs[o["OutputKey"]] = o["OutputValue"]
        except Exception as e:
            logger.warning(f"Could not load {stack_name} outputs: {e}")

    required = ["MCPConfigParameterName"]
    missing = [k for k in required if k not in outputs]
    if missing:
        raise RuntimeError(
            f"Missing CloudFormation outputs: {missing}. Deploy infrastructure first: pnpm exec nx deploy infra"
        )
    return outputs


# Email addresses used in test case actor profiles.
TEST_EMAILS = [
    "maria.garcia@example.com",
    "john.smith@example.com",
    "carlos.mendoza@example.com",
    "sarah.johnson@example.com",
    "ana.rodriguez@example.com",
    "michael.chen@example.com",
]


def cleanup_test_reservations(cfn_outputs: dict[str, str]) -> None:
    """Delete reservations created by previous eval runs.

    Uses the guest-email-index GSI to efficiently find reservations matching
    test case email addresses, then batch-deletes them by reservation_id (PK).
    """
    table_name = cfn_outputs.get("ReservationsTableName")
    if not table_name:
        logger.warning("ReservationsTableName not found in stack outputs — skipping cleanup")
        return

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    deleted = 0

    for email in TEST_EMAILS:
        response = table.query(
            IndexName="guest-email-index",
            KeyConditionExpression="guest_email = :email",
            ExpressionAttributeValues={":email": email},
        )

        with table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"reservation_id": item["reservation_id"]})
                deleted += 1

    logger.info(f"Cleaned up {deleted} test reservations from {table_name}")


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

output_evaluator = OutputEvaluator(
    model=JUDGE_MODEL,
    rubric="""
    Evaluate the hotel assistant's response for factual accuracy and helpfulness.

    Important: The assistant is designed to be conversational and concise. It is NOT
    expected to list every single detail from the knowledge base. A good response
    covers the most relevant facts for the user's question without being exhaustive.

    Scoring criteria:
    1. Factual Accuracy — Is the information provided actually correct? No fabricated
       details, wrong names, wrong prices, or wrong hours.
    2. Relevance — Does the response address the user's question with the most
       important facts? It should cover the core answer, not necessarily every detail.
    3. Helpfulness — Is the response conversational, clear, and useful to a hotel guest?
    4. Language — The assistant MUST respond in the same language the user used.
       If the user writes in English, the response MUST be in English.
       If the user writes in Spanish, the response MUST be in Spanish.
       Responding in the wrong language is a significant issue that should reduce
       the score by at least 0.3 points, even if the facts are correct.

    Score 1.0 if the response is factually correct, addresses the question well,
       is helpful, and uses the correct language.
    Score 0.7 if mostly accurate with minor omissions, in the correct language.
    Score 0.5 if facts are correct but response is in the WRONG language.
    Score 0.4 if it answers the question but has factual errors or misses the main point.
    Score 0.0 if the response is incorrect, fabricated, or doesn't address the question.
    """,
    include_inputs=True,
)

trajectory_evaluator = TrajectoryEvaluator(
    model=JUDGE_MODEL,
    rubric="""
    Evaluate the tool calling trajectory for efficiency and correctness.

    For hotel information queries, the agent should:
    1. Call hotel_assistant_mcp_query_hotel_knowledge to retrieve information
    2. Avoid unnecessary calls to other tools (like check_availability or get_hotels)
       unless the query specifically requires them

    Scoring:
    - Score 1.0 if the agent used exactly the right tools with no redundant calls
    - Score 0.7 if the agent used the right tools but made 1 extra unnecessary call
    - Score 0.4 if the agent used the right tools but made multiple unnecessary calls
    - Score 0.0 if the agent failed to call the necessary tools or used completely wrong tools

    Use the built-in scoring tools (exact_match_scorer, in_order_match_scorer,
    any_order_match_scorer) to compare actual vs expected trajectory.
    """,
    trajectory_description=TOOL_DESCRIPTIONS,
    include_inputs=True,
)

goal_evaluator = GoalSuccessRateEvaluator(
    model=JUDGE_MODEL,
    system_prompt="""You are evaluating whether all user goals were successfully achieved in a
conversation between a hotel assistant agent and a simulated customer.

IMPORTANT — IGNORE FRAMEWORK ARTIFACTS:
If the conversation contains a message like "You must format the previous response
as structured output", this is an INTERNAL EVALUATION FRAMEWORK ARTIFACT, NOT a
real user request. You MUST completely ignore it when determining whether user
goals were achieved. It is injected by the evaluation harness and has nothing to
do with the customer's actual objectives.

Focus ONLY on the customer's real goals as expressed in their messages (e.g.,
checking availability, getting a quote, making a reservation, receiving a
confirmation number).

A reservation is considered successful if a confirmation number (e.g. CONF-XXXXXXX)
was provided to the customer in the agent's messages, regardless of what happens
in the conversation after that point.

Provide your assessment as a structured GoalSuccessRating with:
- "Yes" (score 1.0) if all real user goals were achieved
- "No" (score 0.0) if any real user goal was not achieved

Include step-by-step reasoning explaining your evaluation.""",
)


# ---------------------------------------------------------------------------
# Custom ConversationOutcomeEvaluator
# ---------------------------------------------------------------------------


class ConversationOutcomeEvaluator(Evaluator):
    """Reviews the full conversation log to validate the simulator's assessment.

    This evaluator acts as a second opinion on multi-turn conversations. It catches
    cases where:
    - The agent succeeded (e.g. got a confirmation number) but the simulator didn't
      stop, leading GoalSuccessRate to score it as a failure.
    - The agent responded in the wrong language for the customer's profile.
    - The agent fabricated information (fake phone numbers, emails, policies).
    - The reservation was created but the process was unnecessarily painful.

    Uses an LLM judge to review the full conversation transcript, supplemented by
    a programmatic language compliance check and tool trajectory data.
    """

    # Maximum transcript length (in characters) sent to the judge to avoid
    # Bedrock token-limit ValidationExceptions on very long conversations.
    MAX_TRANSCRIPT_CHARS = 40_000

    def __init__(self, model: str | None = None):
        super().__init__()
        self.model = model

    def evaluate(self, evaluation_case: EvaluationData) -> list[EvaluationOutput]:
        interactions = getattr(evaluation_case, "actual_interactions", None)
        if not interactions:
            # Fall back to checking if interactions are in the output dict
            output = evaluation_case.actual_output
            if isinstance(output, dict):
                interactions = output.get("interactions", [])

        if not interactions:
            return [
                EvaluationOutput(
                    score=0.0,
                    test_pass=False,
                    reason="No conversation interactions available to evaluate.",
                )
            ]

        metadata = evaluation_case.metadata or {}
        expected_language = metadata.get("language", "unknown")
        task_description = metadata.get("task_description", "Complete a hotel reservation.")

        # --- Programmatic language compliance check ---
        # Detect the language of the agent's first response before invoking the
        # LLM judge. If it doesn't match the expected language, auto-set
        # language_compliance to 0.0 so we don't rely on subjective LLM scoring.
        agent_messages = [t.get("message", "") for t in interactions if t.get("role") == "agent"]
        first_agent_msg = agent_messages[0] if agent_messages else ""
        detected_lang = detect_language_heuristic(first_agent_msg)
        programmatic_lang_pass = detected_lang == expected_language or detected_lang == "unknown"

        # Build conversation transcript
        transcript_lines = []
        for turn in interactions:
            role = turn.get("role", "unknown").upper()
            message = turn.get("message", "")
            transcript_lines.append(f"[{role}]: {message}")
        transcript = "\n\n".join(transcript_lines)

        # Truncate very long transcripts to avoid Bedrock token-limit errors
        if len(transcript) > self.MAX_TRANSCRIPT_CHARS:
            transcript = transcript[: self.MAX_TRANSCRIPT_CHARS] + "\n\n[... transcript truncated for length ...]"

        # Check for confirmation number in conversation (heuristic)
        conf_pattern = re.compile(r"CONF-\d+", re.IGNORECASE)
        has_confirmation = bool(conf_pattern.search(transcript))

        # --- Extract simulator data mismatches if available ---
        sim_mismatches: list[str] = []
        output = evaluation_case.actual_output
        if isinstance(output, dict):
            sim_mismatches = output.get("simulator_data_mismatches", [])

        sim_mismatch_section = ""
        if sim_mismatches:
            items = "\n".join(f"  - {m}" for m in sim_mismatches)
            sim_mismatch_section = (
                f"\n\nSIMULATOR DATA DRIFT WARNINGS:\n{items}\n"
                "Note: These mismatches mean the simulated customer may have provided "
                "different data than what was in their profile. This is a simulator issue, "
                "not an agent issue. Reduce process_quality by 0.1 per mismatch."
            )

        # --- Extract tool trajectory if available ---
        tool_calls_section = ""
        output = evaluation_case.actual_output
        if isinstance(output, dict):
            trajectory = output.get("trajectory")
            if trajectory and hasattr(trajectory, "tool_calls"):
                tool_names = [tc.get("name", "unknown") for tc in (trajectory.tool_calls or [])]
                if tool_names:
                    items = "\n".join(f"  {i + 1}. {n}" for i, n in enumerate(tool_names))
                    tool_calls_section = f"\n\nTOOL CALLS (in order):\n{items}"
            elif isinstance(trajectory, list):
                # trajectory might be a plain list of dicts with tool info
                tool_names = [t.get("name", "unknown") for t in trajectory if isinstance(t, dict)]
                if tool_names:
                    items = "\n".join(f"  {i + 1}. {n}" for i, n in enumerate(tool_names))
                    tool_calls_section = f"\n\nTOOL CALLS (in order):\n{items}"

        prompt = f"""You are evaluating a multi-turn conversation between a hotel assistant agent
and a simulated customer. Review the full conversation and assess the outcome.

TASK DESCRIPTION: {task_description}
EXPECTED LANGUAGE: {expected_language} (es = Spanish, en = English)
CONFIRMATION NUMBER FOUND IN TRANSCRIPT: {has_confirmation}
{tool_calls_section}
{sim_mismatch_section}

IMPORTANT CONTEXT:
- This conversation was generated by an automated evaluation framework using a
  simulated customer (ActorSimulator). The conversation you see is the COMPLETE
  interaction — there are no missing turns.
- If the transcript contains a message like "You must format the previous response
  as structured output", this is an INTERNAL FRAMEWORK ARTIFACT injected by the
  evaluation harness, NOT a real user request. IGNORE it completely when assessing
  whether user goals were met.
- Focus ONLY on the actual customer goals described in the TASK DESCRIPTION above.

CONVERSATION TRANSCRIPT:
{transcript}

Evaluate the following dimensions and provide an overall score:

1. RESERVATION OUTCOME (most important, 40% weight):
   - Was a reservation successfully created with a confirmation number?
   - If a confirmation number (CONF-XXXXX) appears in the agent's messages, the
     reservation WAS successful regardless of how the conversation ended afterward.
   - Score 1.0 if reservation confirmed, 0.0 if not.

2. LANGUAGE COMPLIANCE (20% weight):
   - Did the agent respond in the expected language throughout the conversation?
   - If expected language is "en" (English), the agent MUST respond in English.
   - If expected language is "es" (Spanish), the agent MUST respond in Spanish.
   - Score 1.0 if correct language throughout, 0.5 if mixed, 0.0 if wrong language.

3. PROCESS QUALITY (20% weight):
   - Was the reservation flow efficient? (check availability → quote → collect info → create)
   - Did the agent avoid asking for information already provided?
   - Did the agent avoid fabricating information (fake phone numbers, policies, etc.)?
   - If TOOL CALLS are provided above, verify the correct sequence was followed:
     check_availability → generate_quote → create_reservation.
   - Score 1.0 if smooth, 0.5 if some friction, 0.0 if very problematic.

4. INFORMATION ACCURACY (20% weight):
   - Did the agent use correct room type IDs from availability results?
   - Did the agent properly use generate_quote before create_reservation?
     (Check the TOOL CALLS section if available to verify this.)
   - Did the agent avoid hallucinating data (fake quote IDs, contact info, etc.)?
   - Score 1.0 if accurate, 0.5 if minor issues, 0.0 if major fabrications.

Provide your assessment as JSON with this exact structure:
{{
  "reservation_outcome": {{"score": <float>, "notes": "<brief explanation>"}},
  "language_compliance": {{"score": <float>, "notes": "<brief explanation>"}},
  "process_quality": {{"score": <float>, "notes": "<brief explanation>"}},
  "information_accuracy": {{"score": <float>, "notes": "<brief explanation>"}},
  "overall_score": <float between 0.0 and 1.0>,
  "overall_pass": <true if overall_score >= 0.5>,
  "summary": "<2-3 sentence summary>"
}}

Return ONLY the JSON object, no other text."""

        try:
            judge = Agent(
                model=BedrockModel(model_id=self.model) if self.model else None,
                system_prompt="You are an evaluation judge. Return only valid JSON.",
                callback_handler=None,
            )
            result = judge(prompt)
            result_text = str(result)

            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", result_text)
            if json_match:
                parsed = json.loads(json_match.group())
                score = float(parsed.get("overall_score", 0.0))
                test_pass = bool(parsed.get("overall_pass", score >= 0.5))
                reason = parsed.get("summary", "No summary provided.")

                # Override language_compliance with programmatic check if it detected a mismatch
                if not programmatic_lang_pass:
                    lang_dim = parsed.get("language_compliance", {})
                    original_lang_score = lang_dim.get("score", 1.0)
                    parsed["language_compliance"] = {
                        "score": 0.0,
                        "notes": (
                            f"Programmatic check: agent's first response detected as '{detected_lang}', "
                            f"expected '{expected_language}'. Original LLM score was {original_lang_score}."
                        ),
                    }
                    # Recalculate overall score with the overridden language dimension
                    score = (
                        float(parsed.get("reservation_outcome", {}).get("score", 0)) * 0.4
                        + 0.0 * 0.2  # language_compliance overridden to 0
                        + float(parsed.get("process_quality", {}).get("score", 0)) * 0.2
                        + float(parsed.get("information_accuracy", {}).get("score", 0)) * 0.2
                    )
                    test_pass = score >= 0.5

                # Include dimension breakdowns in reason
                dimensions = []
                for dim in ("reservation_outcome", "language_compliance", "process_quality", "information_accuracy"):
                    dim_data = parsed.get(dim, {})
                    dim_score = dim_data.get("score", "N/A")
                    dim_notes = dim_data.get("notes", "")
                    dimensions.append(f"{dim}: {dim_score} — {dim_notes}")

                full_reason = f"{reason}\n\nDimension scores:\n" + "\n".join(dimensions)

                return [EvaluationOutput(score=score, test_pass=test_pass, reason=full_reason)]
            else:
                return [
                    EvaluationOutput(
                        score=0.0,
                        test_pass=False,
                        reason=f"Could not parse judge response: {result_text[:500]}",
                    )
                ]
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"ConversationOutcomeEvaluator failed ({error_type}): {e}", exc_info=True)
            return [
                EvaluationOutput(
                    score=0.0,
                    test_pass=False,
                    reason=f"Evaluation skipped: {error_type} — {e}",
                )
            ]

    async def evaluate_async(self, evaluation_case: EvaluationData) -> list[EvaluationOutput]:
        return self.evaluate(evaluation_case)


conversation_outcome_evaluator = ConversationOutcomeEvaluator(model=JUDGE_MODEL)


# ---------------------------------------------------------------------------
# Simulator prompt — stronger stop conditions
# ---------------------------------------------------------------------------

USER_SIMULATOR_PROMPT = """
You are simulating a hotel customer with the following profile:
{actor_profile}

═══════════════════════════════════════════════════════════════
THE SINGLE MOST IMPORTANT RULE — STOPPING AFTER CONFIRMATION:
═══════════════════════════════════════════════════════════════
When you see a confirmation number (e.g. CONF-1234567) in the agent's response,
you MUST do ALL of the following in your VERY NEXT message:
  1. Thank the agent briefly (one sentence).
  2. Include the tag <stop/> at the end of your message.
  3. Do NOT ask any follow-up questions.
  4. Do NOT start a new topic or request.
  5. Do NOT say anything after <stop/>.

Example of a correct response after seeing CONF-1234567:
  "Thank you so much! That's all I needed. <stop/>"

This rule overrides everything else. Even if you have more questions, STOP.
═══════════════════════════════════════════════════════════════

CRITICAL RULES:
1. Respond ONLY in the language specified in your profile. If your profile says
   "Language: English", respond exclusively in English. If "Language: Spanish",
   respond exclusively in Spanish.
2. Provide your name, email, and phone number ONLY when the agent asks for them.
   Give them exactly as listed in your profile — do NOT invent different data.
3. When choosing a room, ALWAYS pick the most affordable option available.
4. If the agent asks you to confirm details, confirm them promptly.

LANGUAGE ENFORCEMENT:
- If the agent responds in a language DIFFERENT from the one in your profile,
  you MUST firmly insist they switch before answering any questions.
- For example, if your profile says "Language: English" and the agent responds
  in Spanish, say something like: "I only speak English, please respond in
  English." Do NOT continue the conversation or provide any information until
  the agent switches to your language.
- Keep insisting on every turn until the agent complies.

ADDITIONAL STOPPING RULES:
- If the agent has failed to complete the reservation after 3+ attempts with
  errors, express frustration and include <stop/> to end the conversation.
- If the agent redirects you to contact the hotel directly (giving up), accept
  it and include <stop/>.

NEVER RESTART THE CONVERSATION:
- Once you have received a confirmation number and stopped, the conversation is
  OVER. Do NOT start a new reservation request or greet the agent again.
- If for any reason you find yourself at the beginning of a new conversation
  flow, immediately say "I already completed my reservation, goodbye. <stop/>"

CONVERSATION STYLE:
- Be natural and conversational but efficient — don't over-complicate things.
- Answer questions directly without volunteering extra information.
- If the agent asks for something you already provided, politely remind them.
"""


# ---------------------------------------------------------------------------
# Test case loading
# ---------------------------------------------------------------------------


def load_test_cases() -> tuple[list[Case], list[Case]]:
    """Load test cases from JSONL file, split into single-turn and multi-turn."""
    single_turn: list[Case] = []
    multi_turn: list[Case] = []

    with open(TEST_CASES_FILE) as f:
        for line in f:
            data = json.loads(line.strip())
            case_type = data.get("type", "single_turn")

            if case_type == "multi_turn":
                multi_turn.append(
                    Case[str, str](
                        name=data["id"],
                        input=data["input"],
                        expected_output=data.get("expected_output", ""),
                        expected_trajectory=data.get("expected_trajectory", []),
                        metadata=data.get("metadata", {}),
                    )
                )
            else:
                single_turn.append(
                    Case[str, str](
                        name=data["id"],
                        input=data["input"],
                        expected_output=data["expected_output"],
                        expected_trajectory=data["expected_trajectory"],
                        metadata=data.get("metadata", {}),
                    )
                )

    logger.info(f"Loaded {len(single_turn)} single-turn and {len(multi_turn)} multi-turn test cases")
    return single_turn, multi_turn


# ---------------------------------------------------------------------------
# Agent factory initialization
# ---------------------------------------------------------------------------

# Shared config manager (caches SSM config) and system prompt.
# Each parallel task creates its own AgentFactory with fresh MCP clients
# because MCPClient sessions cannot be shared across threads.
_config_manager: MCPConfigManager | None = None
_system_prompt: str | None = None
_factories: list[AgentFactory] = []
_factories_lock = threading.Lock()


async def init_shared_config(cfn_outputs: dict[str, str]) -> None:
    """Pre-load MCP config and system prompt so parallel workers don't race on AWS calls."""
    global _config_manager, _system_prompt
    if _config_manager is None:
        _config_manager = MCPConfigManager(parameter_name=cfn_outputs["MCPConfigParameterName"])
        # Warm the config cache and retrieve the system prompt once
        factory = AgentFactory(_config_manager)
        await factory.initialize()
        _system_prompt = factory.system_prompt
        # Keep this first factory for potential sequential use
        with _factories_lock:
            _factories.append(factory)
        logger.info("Shared config initialized — system prompt and MCP config cached")


def create_factory_for_task() -> AgentFactory:
    """Create a fresh AgentFactory with its own MCP client instances.

    Reuses the cached config_manager (avoids SSM calls) but creates new
    MCPClient objects so each thread gets its own session.
    """
    import asyncio as _asyncio

    factory = AgentFactory(_config_manager)
    # initialize() is async — run it in a new event loop since we're in a thread
    _asyncio.run(factory.initialize())
    # Override system prompt from cache to avoid an extra MCP prompt-loading call
    factory.system_prompt = _system_prompt
    with _factories_lock:
        _factories.append(factory)
    return factory


# ---------------------------------------------------------------------------
# Setup telemetry for GoalSuccessRateEvaluator (needs OTEL spans)
# ---------------------------------------------------------------------------

telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
memory_exporter = telemetry.in_memory_exporter


# ---------------------------------------------------------------------------
# Helpers: language detection & simulator data consistency
# ---------------------------------------------------------------------------

# Common Spanish words used as a heuristic for language detection.
_SPANISH_MARKERS = {
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "en",
    "un",
    "una",
    "es",
    "por",
    "para",
    "con",
    "que",
    "su",
    "al",
    "como",
    "más",
    "pero",
    "sus",
    "le",
    "ya",
    "este",
    "esta",
    "también",
    "nos",
    "nuestro",
    "nuestra",
    "tiene",
    "puede",
    "habitación",
    "reservación",
    "disponible",
    "huéspedes",
    "bienvenido",
    "bienvenida",
    "gracias",
    "hola",
    "buenas",
    "tardes",
    "noches",
    "días",
    "hotel",
    "precio",
    "noche",
    "adultos",
    "niños",
    "fecha",
    "nombre",
    "correo",
    "teléfono",
}

# Common English words for the same heuristic.
_ENGLISH_MARKERS = {
    "the",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "will",
    "would",
    "could",
    "should",
    "can",
    "do",
    "does",
    "did",
    "this",
    "that",
    "these",
    "those",
    "with",
    "from",
    "for",
    "and",
    "but",
    "not",
    "you",
    "your",
    "our",
    "their",
    "available",
    "room",
    "reservation",
    "guests",
    "welcome",
    "thank",
    "hello",
    "please",
    "price",
    "night",
    "adults",
    "children",
    "date",
    "name",
    "email",
    "phone",
    "check",
    "book",
    "booking",
}


def detect_language_heuristic(text: str) -> str:
    """Detect whether *text* is primarily English or Spanish using word-frequency heuristics.

    Returns ``"en"`` or ``"es"``. Falls back to ``"unknown"`` if the signal is too weak.
    This avoids adding an external dependency like ``langdetect``.
    """
    words = set(re.findall(r"[a-záéíóúñü]+", text.lower()))
    es_hits = len(words & _SPANISH_MARKERS)
    en_hits = len(words & _ENGLISH_MARKERS)

    if es_hits == 0 and en_hits == 0:
        return "unknown"
    if es_hits > en_hits:
        return "es"
    if en_hits > es_hits:
        return "en"
    return "unknown"


def _check_simulator_data_consistency(case: Case, conversation_log: list[dict]) -> list[str]:
    """Compare data the simulator actually provided against the actor profile.

    Returns a list of mismatch descriptions (empty if all data matched).
    Also logs a warning for each mismatch so we can catch simulator data drift
    (e.g., the simulator inventing a different phone number).
    """
    mismatches: list[str] = []
    metadata = case.metadata or {}
    actor_profile: str = metadata.get("actor_profile", "")
    if not actor_profile:
        return mismatches

    # Extract expected values from actor profile string
    expected: dict[str, str] = {}
    for field, pattern in [
        ("email", r"Email:\s*([\w.+-]+@[\w.-]+)"),
        ("phone", r"Phone:\s*([\+\d\s()-]+)"),
        ("name", r"Name:\s*([^.]+)"),
    ]:
        m = re.search(pattern, actor_profile)
        if m:
            expected[field] = m.group(1).strip()

    if not expected:
        return mismatches

    # Collect all user messages from the conversation
    user_text = " ".join(turn["message"] for turn in conversation_log if turn.get("role") == "user")

    for field, value in expected.items():
        # Normalise for comparison: strip whitespace, dashes, parens
        normalised_value = re.sub(r"[\s\-()]+", "", value.lower())
        normalised_text = re.sub(r"[\s\-()]+", "", user_text.lower())
        if normalised_value and normalised_value not in normalised_text:
            msg = f"expected {field}='{value}' from actor profile but it was not found in user messages"
            mismatches.append(msg)
            logger.warning(f"[{case.name}] Simulator data drift: {msg}")

    return mismatches


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------

# Collects agent responses and tool calls per case for post-hoc review.
# Keyed by case name, populated by task functions, saved alongside eval results.
_conversation_logs: dict[str, dict] = {}
_conversation_logs_lock = threading.Lock()


def make_single_turn_task(model_id: str):
    """Task function for single-turn knowledge queries."""

    def task_fn(case: Case) -> dict:
        factory = create_factory_for_task()
        agent = factory.create_agent(model_id, callback_handler=None)

        logger.info(f"[{model_id}] Running single-turn case: {case.name}")
        start = time.time()
        response = agent(case.input)
        elapsed = time.time() - start
        logger.info(f"[{model_id}] Case {case.name} completed in {elapsed:.1f}s")

        trajectory = tools_use_extractor.extract_agent_tools_used_from_messages(agent.messages)

        # Extract token usage and cost from AgentResult metrics
        usage = response.metrics.accumulated_usage
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", 0)
        cost = calculate_cost(model_id, input_tokens, output_tokens)

        with _conversation_logs_lock:
            _conversation_logs[f"{model_id}::{case.name}"] = {
                "input": case.input,
                "agent_response": str(response),
                "tools_called": [t.get("name", "") for t in trajectory] if trajectory else [],
                "elapsed_seconds": round(elapsed, 1),
                "token_usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                },
                "cost_usd": round(cost, 6),
            }

        return TaskOutput(
            output=str(response),
            trajectory=trajectory,
        )

    return task_fn


def make_multi_turn_task(model_id: str):
    """Task function for multi-turn reservation flows.

    Each case gets its own fresh Agent (with isolated conversation memory) and
    its own session_id for OTEL span filtering. The shared memory_exporter
    collects spans from all parallel cases, but ``map_to_session`` filters by
    session_id so each case only sees its own spans. This is the pattern
    recommended by the Strands Evals docs for parallel execution.
    """

    def task_fn(case: Case) -> dict:
        factory = create_factory_for_task()

        # Fresh agent per case — conversation memory is fully isolated
        agent = factory.create_agent(
            model_id,
            callback_handler=None,
            trace_attributes={
                "gen_ai.conversation.id": case.session_id,
                "session.id": case.session_id,
            },
        )

        user_sim = ActorSimulator.from_case_for_user_simulator(
            case=case,
            model=SIMULATOR_MODEL,
            system_prompt_template=USER_SIMULATOR_PROMPT,
            max_turns=18,
        )

        logger.info(f"[{model_id}] Running multi-turn case: {case.name}")
        start = time.time()

        user_message = case.input
        conversation_log: list[dict] = []
        conf_pattern = re.compile(r"CONF-\d+", re.IGNORECASE)
        
        # Track per-turn metrics
        turn_metrics: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        while user_sim.has_next():
            turn_start = time.time()
            agent_response = agent(user_message)
            turn_elapsed = time.time() - turn_start
            
            agent_message = str(agent_response)
            
            # Extract token usage for this turn from the latest invocation
            latest_invocation = agent_response.metrics.latest_agent_invocation
            turn_usage = latest_invocation.usage if latest_invocation else {}
            turn_input_tokens = turn_usage.get("inputTokens", 0)
            turn_output_tokens = turn_usage.get("outputTokens", 0)
            turn_total_tokens = turn_usage.get("totalTokens", 0)
            turn_cost = calculate_cost(model_id, turn_input_tokens, turn_output_tokens)
            
            # Accumulate totals
            total_input_tokens += turn_input_tokens
            total_output_tokens += turn_output_tokens
            total_cost += turn_cost
            
            # Record turn metrics
            turn_number = len(conversation_log) // 2 + 1
            turn_metrics.append({
                "turn": turn_number,
                "elapsed_seconds": round(turn_elapsed, 3),
                "token_usage": {
                    "input_tokens": turn_input_tokens,
                    "output_tokens": turn_output_tokens,
                    "total_tokens": turn_total_tokens,
                },
                "cost_usd": round(turn_cost, 6),
            })
            
            conversation_log.append({"role": "agent", "message": agent_message})

            # Programmatic stop: if agent response contains a confirmation number,
            # break immediately instead of waiting for the simulator to emit <stop/>.
            # Strip XML/HTML tags first so CONF numbers inside <message> tags are found.
            agent_text_plain = re.sub(r"<[^>]+>", " ", agent_message)
            if conf_pattern.search(agent_text_plain):
                logger.info(f"  [{case.name}] Confirmation number detected in agent response — stopping early")
                # Use the expected language for the thank-you message so the
                # conversation log stays consistent with the customer profile.
                expected_lang = (case.metadata or {}).get("language", "en")
                stop_msg = (
                    "¡Gracias! Eso es todo lo que necesitaba."
                    if expected_lang == "es"
                    else "Thank you! That's all I needed."
                )
                conversation_log.append(
                    {
                        "role": "user",
                        "message": stop_msg,
                        "reasoning": "Programmatic stop: confirmation number detected in agent response.",
                    }
                )
                break

            user_result = user_sim.act(agent_message)
            user_message = str(user_result.structured_output.message)
            conversation_log.append(
                {
                    "role": "user",
                    "message": user_message,
                    "reasoning": user_result.structured_output.reasoning,
                }
            )
            logger.info(f"  [{case.name}] Turn {turn_number}: tokens={turn_total_tokens}, cost=${turn_cost:.6f}, time={turn_elapsed:.2f}s")

        elapsed = time.time() - start
        turns = len(conversation_log) // 2
        logger.info(f"[{model_id}] Case {case.name} completed in {elapsed:.1f}s ({turns} turns, {total_input_tokens + total_output_tokens} tokens, ${total_cost:.6f})")

        # Simulator data consistency check: compare what the simulator actually
        # provided against the actor profile in the test case metadata.
        sim_mismatches = _check_simulator_data_consistency(case, conversation_log)

        # Spans from all parallel cases live in the shared exporter, but
        # map_to_session filters by this case's unique session_id
        mapper = StrandsInMemorySessionMapper()
        all_spans = list(memory_exporter.get_finished_spans())
        session = mapper.map_to_session(all_spans, session_id=case.session_id)

        with _conversation_logs_lock:
            _conversation_logs[f"{model_id}::{case.name}"] = {
                "input": case.input,
                "turns": turns,
                "elapsed_seconds": round(elapsed, 1),
                "conversation": conversation_log,
                "turn_metrics": turn_metrics,
                "total_token_usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                },
                "total_cost_usd": round(total_cost, 6),
            }

        return {
            "output": agent_message,
            "trajectory": session,
            "interactions": conversation_log,
            "simulator_data_mismatches": sim_mismatches,
        }

    return task_fn


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------


def calculate_aggregate_metrics(run_dir: Path) -> dict:
    """Calculate aggregate cost and performance metrics from conversation logs.
    
    Args:
        run_dir: Directory containing evaluation results
        
    Returns:
        Dictionary mapping model_id to aggregate metrics
    """
    import glob
    
    aggregate: dict = {}
    
    # Load all conversation log files
    for log_file in glob.glob(str(run_dir / "*_conversations.json")):
        with open(log_file) as f:
            logs = json.load(f)
        
        # Extract model_id from filename (e.g., "us_amazon_nova-micro-v1_0_conversations.json")
        model_label = Path(log_file).stem.replace("_conversations", "")
        model_id = model_label.replace("_", ".", 1).replace("_", ":", 1)  # Reverse the transformation
        
        # Aggregate metrics across all test cases for this model
        total_turns = 0
        total_time = 0.0
        total_tokens = 0
        total_cost = 0.0
        turn_count = 0
        
        for case_name, case_data in logs.items():
            # Single-turn cases
            if "elapsed_seconds" in case_data and "token_usage" in case_data:
                total_time += case_data["elapsed_seconds"]
                usage = case_data["token_usage"]
                total_tokens += usage.get("total_tokens", 0)
                total_cost += case_data.get("cost_usd", 0.0)
                turn_count += 1
            
            # Multi-turn cases
            if "turn_metrics" in case_data:
                for turn in case_data["turn_metrics"]:
                    total_time += turn["elapsed_seconds"]
                    total_tokens += turn["token_usage"]["total_tokens"]
                    total_cost += turn["cost_usd"]
                    turn_count += 1
                total_turns += case_data.get("turns", 0)
        
        if turn_count > 0:
            aggregate[model_id] = {
                "total_turns": turn_count,
                "avg_response_time_seconds": total_time / turn_count,
                "avg_tokens_per_turn": total_tokens / turn_count,
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost,
                "avg_cost_per_turn_usd": total_cost / turn_count,
            }
    
    return aggregate


async def evaluate_model(
    model_id: str,
    single_turn_cases: list[Case],
    multi_turn_cases: list[Case],
    run_dir: Path,
    timestamp: str,
) -> tuple[str, dict]:
    """Evaluate a single model across all test cases. Returns (model_id, summary_scores)."""

    model_label = model_id.replace(":", "_").replace(".", "_")
    logger.info(f"\n{'=' * 60}\nEvaluating model: {model_id}\n{'=' * 60}")

    model_results: dict = {"model_id": model_id, "timestamp": timestamp, "evaluators": {}}
    model_conversation_logs: dict[str, dict] = {}

    # --- Single-turn evaluation (OutputEvaluator + TrajectoryEvaluator) ---
    if single_turn_cases:
        try:
            experiment = Experiment[str, str](
                cases=single_turn_cases,
                evaluators=[output_evaluator, trajectory_evaluator],
            )
            task_fn = make_single_turn_task(model_id)
            reports = await experiment.run_evaluations_async(task_fn, max_workers=len(single_turn_cases))

            for eval_name, report in zip(["OutputEvaluator", "TrajectoryEvaluator"], reports, strict=False):
                pass_count = sum(1 for p in report.test_passes if p)
                total = len(report.test_passes)
                model_results["evaluators"][eval_name] = {
                    "overall_score": report.overall_score,
                    "pass_rate": pass_count / total if total > 0 else 0,
                    "cases": [
                        {
                            "name": report.cases[i].get("name", f"case_{i}"),
                            "score": report.scores[i],
                            "test_pass": report.test_passes[i],
                            "reason": report.reasons[i] if i < len(report.reasons) else "",
                        }
                        for i in range(len(report.scores))
                    ],
                }
                logger.info(f"\n--- {eval_name} for {model_id} ---")
                report.display()

        except Exception as e:
            logger.error(f"Single-turn evaluation failed for {model_id}: {e}", exc_info=True)
            model_results["evaluators"]["single_turn_error"] = str(e)

    # Collect conversation logs from single-turn tasks
    with _conversation_logs_lock:
        prefix = f"{model_id}::"
        for key in [k for k in _conversation_logs if k.startswith(prefix)]:
            model_conversation_logs[key.removeprefix(prefix)] = _conversation_logs.pop(key)

    # --- Multi-turn evaluation (GoalSuccessRate + ConversationOutcome) ---
    if multi_turn_cases:
        try:
            experiment = Experiment[str, str](
                cases=multi_turn_cases,
                evaluators=[goal_evaluator, conversation_outcome_evaluator],
            )
            task_fn = make_multi_turn_task(model_id)
            reports = await experiment.run_evaluations_async(task_fn, max_workers=len(multi_turn_cases))

            eval_names = ["GoalSuccessRate", "ConversationOutcome"]
            for eval_name, report in zip(eval_names, reports, strict=False):
                pass_count = sum(1 for p in report.test_passes if p)
                total = len(report.test_passes)
                model_results["evaluators"][eval_name] = {
                    "overall_score": report.overall_score,
                    "pass_rate": pass_count / total if total > 0 else 0,
                    "cases": [
                        {
                            "name": report.cases[i].get("name", f"case_{i}"),
                            "score": report.scores[i],
                            "test_pass": report.test_passes[i],
                            "reason": report.reasons[i] if i < len(report.reasons) else "",
                        }
                        for i in range(len(report.scores))
                    ],
                }
                logger.info(f"\n--- {eval_name} for {model_id} ---")
                report.display()

        except Exception as e:
            logger.error(f"Multi-turn evaluation failed for {model_id}: {e}", exc_info=True)
            model_results["evaluators"]["multi_turn_error"] = str(e)

    # Collect conversation logs from multi-turn tasks
    with _conversation_logs_lock:
        prefix = f"{model_id}::"
        for key in [k for k in _conversation_logs if k.startswith(prefix)]:
            model_conversation_logs[key.removeprefix(prefix)] = _conversation_logs.pop(key)

    # Save per-model results
    results_file = run_dir / f"{model_label}.json"
    with open(results_file, "w") as f:
        json.dump(model_results, f, indent=2, default=str)

    if model_conversation_logs:
        logs_file = run_dir / f"{model_label}_conversations.json"
        with open(logs_file, "w") as f:
            json.dump(model_conversation_logs, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Results saved to {results_file}")

    summary_scores = {
        k: {"overall_score": v.get("overall_score"), "pass_rate": v.get("pass_rate")}
        for k, v in model_results["evaluators"].items()
        if isinstance(v, dict) and "overall_score" in v
    }
    return model_id, summary_scores


async def run_all_evaluations():
    """Run evaluations for all models concurrently and save results.

    Each model is evaluated in parallel via asyncio.gather. Within each model,
    test cases also run in parallel via run_evaluations_async.
    """

    cfn_outputs = load_cloudformation_outputs()

    # Delete reservations from previous eval runs so rooms aren't fully booked
    cleanup_test_reservations(cfn_outputs)

    # Pre-load config and system prompt so parallel workers reuse cached values
    await init_shared_config(cfn_outputs)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    single_turn_cases, multi_turn_cases = load_test_cases()

    # Clear exporter once before all evaluations start
    memory_exporter.clear()

    # Launch all models concurrently
    results = await asyncio.gather(
        *(evaluate_model(model_id, single_turn_cases, multi_turn_cases, run_dir, timestamp) for model_id in MODELS),
        return_exceptions=True,
    )

    # Collect summary from results
    summary: dict = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Model evaluation failed: {result}", exc_info=result)
            continue
        model_id, scores = result
        summary[model_id] = scores

    # Save overall summary
    summary_file = run_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Calculate aggregate metrics from conversation logs
    aggregate_metrics = calculate_aggregate_metrics(run_dir)
    
    # Save aggregate metrics
    metrics_file = run_dir / "aggregate_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(aggregate_metrics, f, indent=2, default=str)

    # Print summary table
    print(f"\n{'=' * 100}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 100}")
    print(f"{'Model':<50} {'Output':>8} {'Traj':>8} {'Goal':>8} {'Conv':>8}")
    print(f"{'-' * 50} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8}")
    for model_id, scores in summary.items():
        out = scores.get("OutputEvaluator", {}).get("overall_score")
        traj = scores.get("TrajectoryEvaluator", {}).get("overall_score")
        goal = scores.get("GoalSuccessRate", {}).get("overall_score")
        conv = scores.get("ConversationOutcome", {}).get("overall_score")
        out_s = f"{out:.2f}" if isinstance(out, (int, float)) else "N/A"
        traj_s = f"{traj:.2f}" if isinstance(traj, (int, float)) else "N/A"
        goal_s = f"{goal:.2f}" if isinstance(goal, (int, float)) else "N/A"
        conv_s = f"{conv:.2f}" if isinstance(conv, (int, float)) else "N/A"
        print(f"{model_id:<50} {out_s:>8} {traj_s:>8} {goal_s:>8} {conv_s:>8}")
    print(f"{'=' * 100}")
    
    # Print cost and performance metrics
    print(f"\n{'=' * 100}")
    print("COST & PERFORMANCE METRICS")
    print(f"{'=' * 100}")
    print(f"{'Model':<50} {'Avg Time':>10} {'Avg Tokens':>12} {'Total Cost':>12}")
    print(f"{'-' * 50} {'-' * 10} {'-' * 12} {'-' * 12}")
    for model_id, metrics in aggregate_metrics.items():
        avg_time = metrics.get("avg_response_time_seconds", 0)
        avg_tokens = metrics.get("avg_tokens_per_turn", 0)
        total_cost = metrics.get("total_cost_usd", 0)
        print(f"{model_id:<50} {avg_time:>9.2f}s {avg_tokens:>11.0f} ${total_cost:>10.6f}")
    print(f"{'=' * 100}")
    print(f"\nResults saved to: {run_dir}")
    print(f"Detailed metrics: {metrics_file}")


def cleanup_factories():
    """Stop MCP client connections on all factories so the process can exit cleanly."""
    with _factories_lock:
        for factory in _factories:
            for client in factory._mcp_clients:
                with contextlib.suppress(Exception):
                    client.stop()
        _factories.clear()
    logger.info("All MCP clients stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_evaluations())
    finally:
        cleanup_factories()
        # Force exit — background threads from OTEL telemetry and MCP async
        # transports keep the process alive even after cleanup.
        import os

        os._exit(0)
