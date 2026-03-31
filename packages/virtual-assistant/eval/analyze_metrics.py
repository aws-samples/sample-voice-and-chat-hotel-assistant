# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Analyze token usage, cost, and time metrics from evaluation results.

This script reads existing evaluation results and generates a detailed analysis
of token usage, cost, and response time metrics across models and test cases.

Usage:
    cd packages/virtual-assistant
    uv run python eval/analyze_metrics.py [results_dir]
    
    # Analyze latest results
    uv run python eval/analyze_metrics.py
    
    # Analyze specific results
    uv run python eval/analyze_metrics.py eval/results/20260224_185245
"""

import json
import sys
from pathlib import Path
from typing import Any

# Bedrock pricing per 1M tokens (verified with AWS Pricing API on Feb 24, 2026)
BEDROCK_PRICING = {
    "global.amazon.nova-2-lite-v1:0": {"input": 0.33, "output": 2.75},
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00, "output": 5.00},
    "us.amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},
    "us.amazon.nova-micro-v1:0": {"input": 0.035, "output": 0.14},
    "us.anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.25, "output": 1.25},
    "us.anthropic.claude-3-5-haiku-20241022-v1:0": {"input": 0.80, "output": 4.00},
    "us.amazon.nova-lite-v1:0": {"input": 0.06, "output": 0.24},
}


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for the given token usage."""
    pricing = BEDROCK_PRICING.get(model_id, {"input": 0.0, "output": 0.0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def analyze_results(results_dir: Path) -> dict[str, Any]:
    """Analyze evaluation results and calculate metrics.
    
    Args:
        results_dir: Directory containing evaluation results
        
    Returns:
        Dictionary with analysis results
    """
    analysis: dict[str, Any] = {}
    
    # Find all result files
    result_files = list(results_dir.glob("*.json"))
    conversation_files = [f for f in result_files if "_conversations" in f.name]
    
    if not conversation_files:
        print(f"No conversation log files found in {results_dir}")
        return analysis
    
    for conv_file in conversation_files:
        # Extract model ID from filename
        model_label = conv_file.stem.replace("_conversations", "")
        # Reverse the transformation: us_amazon_nova-micro-v1_0 -> us.amazon.nova-micro-v1:0
        parts = model_label.split("_", 2)
        if len(parts) >= 3:
            model_id = f"{parts[0]}.{parts[1]}.{parts[2].rsplit('_', 1)[0]}:{parts[2].rsplit('_', 1)[1]}"
        else:
            model_id = model_label
        
        with open(conv_file) as f:
            logs = json.load(f)
        
        # Analyze each test case
        cases: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_time = 0.0
        total_turns = 0
        
        for case_name, case_data in logs.items():
            case_analysis: dict[str, Any] = {
                "name": case_name,
                "type": "multi_turn" if "turn_metrics" in case_data else "single_turn",
            }
            
            if "turn_metrics" in case_data:
                # Multi-turn case - aggregate turn metrics
                turn_metrics = case_data["turn_metrics"]
                case_input = sum(t["token_usage"]["input_tokens"] for t in turn_metrics)
                case_output = sum(t["token_usage"]["output_tokens"] for t in turn_metrics)
                case_time = sum(t["elapsed_seconds"] for t in turn_metrics)
                case_turns = len(turn_metrics)
                
                case_analysis.update({
                    "turns": case_turns,
                    "total_time_seconds": round(case_time, 2),
                    "avg_time_per_turn": round(case_time / case_turns, 2),
                    "input_tokens": case_input,
                    "output_tokens": case_output,
                    "total_tokens": case_input + case_output,
                    "avg_tokens_per_turn": round((case_input + case_output) / case_turns, 1),
                    "cost_usd": round(calculate_cost(model_id, case_input, case_output), 6),
                    "turn_details": turn_metrics,
                })
                
                total_turns += case_turns
            else:
                # Single-turn case
                usage = case_data.get("token_usage", {})
                case_input = usage.get("input_tokens", 0)
                case_output = usage.get("output_tokens", 0)
                case_time = case_data.get("elapsed_seconds", 0)
                
                case_analysis.update({
                    "turns": 1,
                    "total_time_seconds": case_time,
                    "input_tokens": case_input,
                    "output_tokens": case_output,
                    "total_tokens": case_input + case_output,
                    "cost_usd": round(calculate_cost(model_id, case_input, case_output), 6),
                })
                
                total_turns += 1
            
            total_input_tokens += case_analysis["input_tokens"]
            total_output_tokens += case_analysis["output_tokens"]
            total_time += case_analysis["total_time_seconds"]
            cases.append(case_analysis)
        
        # Calculate model-level aggregates
        total_cost = calculate_cost(model_id, total_input_tokens, total_output_tokens)
        
        analysis[model_id] = {
            "total_cases": len(cases),
            "total_turns": total_turns,
            "total_time_seconds": round(total_time, 2),
            "avg_time_per_turn": round(total_time / total_turns, 3) if total_turns > 0 else 0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "avg_tokens_per_turn": round((total_input_tokens + total_output_tokens) / total_turns, 1) if total_turns > 0 else 0,
            "total_cost_usd": round(total_cost, 6),
            "avg_cost_per_turn": round(total_cost / total_turns, 6) if total_turns > 0 else 0,
            "cases": cases,
        }
    
    return analysis


def print_analysis(analysis: dict[str, Any]) -> None:
    """Print formatted analysis results."""
    
    print("\n" + "=" * 120)
    print("TOKEN USAGE, COST & PERFORMANCE ANALYSIS")
    print("=" * 120)
    
    # Summary table
    print(f"\n{'Model':<50} {'Turns':>7} {'Avg Time':>10} {'Avg Tokens':>12} {'Total Cost':>12}")
    print("-" * 120)
    
    for model_id, metrics in sorted(analysis.items()):
        print(
            f"{model_id:<50} "
            f"{metrics['total_turns']:>7} "
            f"{metrics['avg_time_per_turn']:>9.2f}s "
            f"{metrics['avg_tokens_per_turn']:>11.1f} "
            f"${metrics['total_cost_usd']:>10.6f}"
        )
    
    print("=" * 120)
    
    # Detailed per-case breakdown
    print("\n" + "=" * 120)
    print("PER-CASE BREAKDOWN")
    print("=" * 120)
    
    for model_id, metrics in sorted(analysis.items()):
        print(f"\n{model_id}")
        print("-" * 120)
        print(f"{'Case':<30} {'Type':>12} {'Turns':>7} {'Time':>10} {'Tokens':>10} {'Cost':>12}")
        print("-" * 120)
        
        for case in metrics["cases"]:
            print(
                f"{case['name']:<30} "
                f"{case['type']:>12} "
                f"{case['turns']:>7} "
                f"{case['total_time_seconds']:>9.2f}s "
                f"{case['total_tokens']:>10} "
                f"${case['cost_usd']:>10.6f}"
            )
        
        print("-" * 120)
        print(
            f"{'TOTAL':<30} "
            f"{'':<12} "
            f"{metrics['total_turns']:>7} "
            f"{metrics['total_time_seconds']:>9.2f}s "
            f"{metrics['total_tokens']:>10} "
            f"${metrics['total_cost_usd']:>10.6f}"
        )
    
    print("\n" + "=" * 120)


def main():
    """Main entry point."""
    eval_dir = Path(__file__).parent
    
    # Determine results directory
    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1])
    else:
        # Use latest results
        results_dirs = sorted((eval_dir / "results").glob("*"), reverse=True)
        if not results_dirs:
            print("No results found in eval/results/")
            sys.exit(1)
        results_dir = results_dirs[0]
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        sys.exit(1)
    
    print(f"Analyzing results from: {results_dir}")
    
    # Analyze results
    analysis = analyze_results(results_dir)
    
    if not analysis:
        print("No data to analyze")
        sys.exit(1)
    
    # Print analysis
    print_analysis(analysis)
    
    # Save detailed analysis
    output_file = results_dir / "metrics_analysis.json"
    with open(output_file, "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\nDetailed analysis saved to: {output_file}")


if __name__ == "__main__":
    main()
