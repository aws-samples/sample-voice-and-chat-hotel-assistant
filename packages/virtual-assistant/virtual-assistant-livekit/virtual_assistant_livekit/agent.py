# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import asyncio
import logging
import os

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    AudioConfig,
    AutoSubscribe,
    BackgroundAudioPlayer,
    JobContext,
    JobProcess,
    WorkerOptions,
    WorkerType,
)
from livekit.agents.voice.events import CloseEvent
from livekit.plugins.aws.experimental.realtime import RealtimeModel
from virtual_assistant_common.mcp import (
    AssistantType,
    MCPConfigManager,
    PromptLoader,
)

from .credentials import get_livekit_credentials
from .metrics import (
    decrement_active_calls,
    increment_active_calls,
    start_metrics_publishing,
    stop_metrics_publishing,
)

logger = logging.getLogger(__name__)


class VirtualAssistant(Agent):
    """Industry-agnostic virtual assistant agent with multi-language greeting support.

    This agent extends the base Agent class to provide a native greeting
    using Nova Sonic 2's "speak first" capability via the on_enter() hook.
    The greeting is configurable and supports automatic language detection
    for multi-language interactions.
    """

    def __init__(self, instructions: str, greeting: str | None = None):
        """Initialize the VirtualAssistant agent.

        Args:
            instructions: System prompt with multi-language support rules
            greeting: Optional greeting text. If not provided, uses a default multi-language greeting.
        """
        super().__init__(instructions=instructions)
        self._greeting = greeting or (
            "¡Hola! Soy su asistente virtual. "
            "Estoy aquí para ayudarle con cualquier consulta. "
            "¿En qué puedo asistirle hoy?"
        )
        logger.info("Initialized VirtualAssistant agent")

    async def on_enter(self):
        """Called when agent enters the room - greet the user.

        This method uses Nova Sonic 2's native "speak first" capability
        to deliver a greeting without requiring audio input workarounds.
        The greeting uses the configured greeting text with automatic
        language detection for subsequent interactions.
        """
        logger.info("Agent entering room - delivering greeting")
        try:
            await self.session.generate_reply(instructions=self._greeting)
            logger.info("Greeting delivered successfully via generate_reply()")
        except Exception as e:
            logger.error(f"Failed to deliver greeting: {e}")
            # Session continues - user can still initiate conversation


def _configure_worker_logging():
    """Configure logging for worker processes (multiprocessing resets logging config)."""
    log_level = os.getenv("LOG_LEVEL", "WARN").upper()

    # Configure root logger with force=True to override existing configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Force reconfiguration even if already configured
    )

    # Set level for common noisy loggers that might be generating DEBUG messages
    noisy_loggers = [
        "livekit",
        "livekit.agents",
        "livekit.plugins",
        "livekit.plugins.aws",
        "aws_sdk_bedrock_runtime",
        "smithy_aws_event_stream",
        "boto3",
        "botocore",
        "urllib3",
        "asyncio",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(log_level)


# Configure logging for main process
_configure_worker_logging()


def prewarm(proc: JobProcess):
    """
    Prewarm function to load system prompt.

    This function loads the voice system prompt using a temporary MCP connection.
    The connection is closed immediately after loading the prompt.
    """
    # Configure logging in worker process (multiprocessing resets logging config)
    _configure_worker_logging()

    logger.info("Starting prewarm: loading system prompt")

    async def _load_prompt():
        """Async helper to load system prompt."""
        try:
            # Initialize MCP configuration manager
            config_manager = MCPConfigManager()
            logger.info("Initialized MCPConfigManager")

            # Initialize prompt loader
            prompt_loader = PromptLoader(config_manager)
            logger.info("Initialized PromptLoader")

            # Load voice system prompt (creates temporary connection)
            instructions = await prompt_loader.load_prompt(AssistantType.VOICE)
            logger.info(f"Loaded voice system prompt ({len(instructions)} characters)")
            logger.debug(f"Voice instructions: {instructions}")

            return instructions

        except Exception as e:
            logger.error(f"Failed to load prompt during prewarm: {e}")
            raise

    # Run the async operation synchronously
    instructions = asyncio.run(_load_prompt())

    # Store only the instructions in context for use in entrypoint
    proc.userdata["instructions"] = instructions
    logger.info("Prewarm completed successfully")


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the LiveKit Hotel Assistant agent.
    """
    # Configure logging in worker process (multiprocessing resets logging config)
    _configure_worker_logging()

    logger.info("Starting LiveKit Hotel Assistant agent session")

    # Increment active calls counter for metrics
    increment_active_calls()
    logger.debug(f"Incremented active calls counter for CloudWatch metrics (process {os.getpid()})")

    # Connect to the LiveKit server
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Connected to LiveKit server")

    # Get prewarmed instructions
    if not ctx.proc.userdata.get("instructions"):
        raise Exception("No prewarm data available - instructions required")

    agent_instructions = ctx.proc.userdata["instructions"]
    logger.info("Using prewarmed instructions")
    logger.debug(f"Instructions: {agent_instructions}")

    # Create agent with instructions
    agent = VirtualAssistant(instructions=agent_instructions)
    logger.info("Created VirtualAssistant agent with prewarmed instructions")

    # Create MCP servers for LiveKit (fresh connections per session)
    logger.info("Creating MCP servers for LiveKit agent session...")
    config_manager = MCPConfigManager()
    servers_config = config_manager.load_config()

    mcp_servers = []
    for server_name, server_config in servers_config.items():
        try:
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Create CognitoMCPServer (LiveKit will manage lifecycle)
            from .hotel_pms_mcp_server import CognitoMCPServer

            mcp_server = CognitoMCPServer(
                url=server_config.url,
                user_pool_id=creds["userPoolId"],
                client_id=creds["clientId"],
                client_secret=creds["clientSecret"],
                region=creds["region"],
                server_name=server_name,
                headers=server_config.headers,
            )
            mcp_servers.append(mcp_server)
            logger.info(f"Created CognitoMCPServer for {server_name}")
        except Exception as e:
            logger.warning(f"Failed to create MCP server for {server_name}: {e}")

    if not mcp_servers:
        logger.warning("No MCP servers available - agent will continue without MCP tools")

    # Get configuration from environment
    model_temperature = float(os.getenv("MODEL_TEMPERATURE", "0.0"))
    endpointing_sensitivity = os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM").upper()

    # Validate endpointing sensitivity
    valid_sensitivities = ["HIGH", "MEDIUM", "LOW"]
    if endpointing_sensitivity not in valid_sensitivities:
        logger.warning(
            f"Invalid ENDPOINTING_SENSITIVITY '{endpointing_sensitivity}', "
            f"using default 'MEDIUM'. Valid values: {valid_sensitivities}"
        )
        endpointing_sensitivity = "MEDIUM"

    # Log model configuration
    logger.info(f"Using Nova Sonic 2 with voice=tiffany, turn_detection={endpointing_sensitivity}")
    logger.debug(f"Model configuration: temperature={model_temperature}, tool_choice=auto")

    # Create AgentSession with Nova Sonic 2 model
    session = AgentSession(
        llm=RealtimeModel.with_nova_sonic_2(
            voice="lupe",
            temperature=model_temperature,
            turn_detection=endpointing_sensitivity,
            tool_choice="auto",
        ),
        mcp_servers=mcp_servers,
    )

    # nosemgrep: useless-inner-function
    @session.on("close")
    def on_close(_: CloseEvent):
        """Handle session close event (synchronous callback)."""
        logger.info("Agent session closed")
        # Decrement active calls counter when session ends
        decrement_active_calls()
        logger.debug(f"Decremented active calls counter for CloudWatch metrics (process {os.getpid()})")

    # Configure thinking audio
    thinking_audio = BackgroundAudioPlayer(
        thinking_sound=[
            AudioConfig(
                os.path.join(os.path.dirname(__file__), "assets", "un_momento.mp3"),
                volume=1,
                probability=1,
            ),
        ]
    )

    # Start the session
    await session.start(room=ctx.room, agent=agent)
    logger.info("Agent session started successfully - greeting will be delivered via on_enter()")

    await thinking_audio.start(room=ctx.room, agent_session=session)


def main():
    """Main entry point for the LiveKit Hotel Assistant agent."""

    try:
        # Log LiveKit agents version information
        import livekit.agents
        import livekit.plugins.aws

        logger.info(f"LiveKit agents version: {livekit.agents.__version__}")
        logger.info(f"LiveKit AWS plugin version: {livekit.plugins.aws.__version__}")

        # Detect if using Git-based installation
        if "git" in str(livekit.agents.__version__).lower() or "+" in str(livekit.agents.__version__):
            logger.info("Using Git-based LiveKit agents (pre-release)")
        else:
            logger.info("Using PyPI LiveKit agents (official release)")

        # Initialize LiveKit credentials only (MCP and instructions will be initialized per worker)
        credentials = get_livekit_credentials()

        # Start CloudWatch metrics publishing in main process
        try:
            asyncio.run(start_metrics_publishing())
            logger.info("Started CloudWatch metrics publishing")
        except Exception as e:
            logger.warning(f"Failed to start metrics publishing: {e}")
            logger.warning("Agent will continue without metrics publishing")

        # Configure WorkerOptions with credentials and prewarm function
        worker_options = WorkerOptions(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            ws_url=credentials.url,
            worker_type=WorkerType.ROOM,
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )

        # Start the LiveKit agent worker
        logger.info("Starting LiveKit agent worker")
        agents.cli.run_app(worker_options)

    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.info("Agent shutdown requested by user")
        # Stop metrics publishing on shutdown
        try:
            asyncio.run(stop_metrics_publishing())
            logger.info("Stopped metrics publishing")
        except Exception as e:
            logger.error(f"Error stopping metrics publishing: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")  # nosemgrep: logging-error-without-handling
        # Stop metrics publishing on error
        try:
            asyncio.run(stop_metrics_publishing())
        except Exception as cleanup_error:
            logger.error(  # nosemgrep: logging-error-without-handling
                f"Error stopping metrics publishing during cleanup: {cleanup_error}"
            )
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
