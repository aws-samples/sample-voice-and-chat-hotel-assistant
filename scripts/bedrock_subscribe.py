# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#
# /// script
# dependencies = [
#     "boto3>=1.40.64",
# ]
# ///
"""
Amazon Bedrock Model Subscription Tool

A simplified tool that uses Bedrock's native agreement APIs to discover
available model offers and create subscriptions automatically.
"""

import argparse
import boto3
import fnmatch
import sys
from typing import List, Dict, Any, Optional


def get_foundation_models(region: str) -> List[Dict[str, Any]]:
    """Get all foundation models from Bedrock API.

    Args:
        region: AWS region to use for the Bedrock client

    Returns:
        List of model dictionaries with modelId, providerName, modelName

    Raises:
        Exception: If API call fails with descriptive error message
    """
    try:
        # Create Bedrock client for the specified region
        bedrock_client = boto3.client("bedrock", region_name=region)

        # Call list_foundation_models API
        response = bedrock_client.list_foundation_models()

        # Extract model summaries from response
        models = response.get("modelSummaries", [])

        if not models:
            print("Warning: No foundation models found in the response")
            return []

        print(f"Found {len(models)} foundation models")
        return models

    except Exception as e:
        error_msg = (
            f"Failed to retrieve foundation models from region {region}: {str(e)}"
        )
        print(f"Error: {error_msg}")
        raise Exception(error_msg)


def filter_models(
    models: List[Dict[str, Any]], patterns: List[str]
) -> List[Dict[str, Any]]:
    """Filter models based on glob patterns.

    Args:
        models: List of model dictionaries from list_foundation_models
        patterns: List of glob patterns to match against. If empty, processes all models.

    Returns:
        List of filtered models that match patterns and require subscriptions
    """
    # Providers that don't require subscriptions
    excluded_providers = {
        "amazon",
        "deepseek",
        "mistral ai",
        "meta",
        "qwen",
        "openai",
    }

    # First filter out providers that don't need subscriptions
    subscription_models = []
    for model in models:
        provider_name = model.get("providerName", "").lower()
        if provider_name not in excluded_providers:
            subscription_models.append(model)

    print(
        f"Filtered out {len(models) - len(subscription_models)} models from providers that don't require subscriptions"
    )

    # If no patterns provided, return all models that require subscriptions
    if not patterns:
        return subscription_models

    # Apply glob pattern filtering
    filtered_models = []

    for model in subscription_models:
        model_id = model.get("modelId", "")
        provider_name = model.get("providerName", "")
        model_name = model.get("modelName", "")

        # Create combined string for provider + model name matching
        provider_model_combo = f"{provider_name} {model_name}".strip()

        # Check if model matches any of the provided patterns
        model_matches = False

        for pattern in patterns:
            # Match against modelId directly
            if fnmatch.fnmatch(model_id, pattern):
                model_matches = True
                break

            # Match against providerName + modelName combination
            if fnmatch.fnmatch(provider_model_combo, pattern):
                model_matches = True
                break

            # Also try case-insensitive matching for provider + model name
            if fnmatch.fnmatch(provider_model_combo.lower(), pattern.lower()):
                model_matches = True
                break

        if model_matches:
            filtered_models.append(model)

    print(f"Pattern matching found {len(filtered_models)} models")

    return filtered_models


def handle_anthropic_use_case(
    region: str,
    company_name: Optional[str],
    use_cases: Optional[str],
    skip_use_case: bool,
) -> None:
    """Handle Anthropic use case submission if needed.

    Args:
        region: AWS region to use for the Bedrock client
        company_name: Company name for use case submission (optional)
        use_cases: Use cases description (optional)
        skip_use_case: If True, skip use case submission entirely
    """
    # Skip use case submission entirely when --skip-use-case flag is provided
    if skip_use_case:
        print("Skipping Anthropic use case submission (--skip-use-case flag provided)")
        return

    try:
        # Create Bedrock client for the specified region
        bedrock_client = boto3.client("bedrock", region_name=region)

        # Check if use case already exists
        try:
            response = bedrock_client.get_use_case_for_model_access()
            if response and response.get("formData"):
                print("✓ Found existing Anthropic use case submission")
                return
        except Exception as e:
            # If ResourceNotFoundException or similar, continue to submit new use case
            if "ResourceNotFoundException" not in str(e):
                print(f"Warning: Could not check existing use case: {str(e)}")

        # Get company name - use provided argument or prompt user
        if company_name is None:
            company_name = input(
                "Enter your company name for Anthropic use case submission: "
            ).strip()
            if not company_name:
                print("Warning: No company name provided, skipping use case submission")
                return

        # Get use cases - use provided argument or prompt user
        if use_cases is None:
            use_cases = input(
                "Enter your use cases for Anthropic models (e.g., 'AI development and research'): "
            ).strip()
            if not use_cases:
                print("Warning: No use cases provided, skipping use case submission")
                return

        print("Submitting use case for Anthropic models...")
        print(f"  Company: {company_name}")
        print(f"  Use cases: {use_cases}")

        # Submit use case via put_use_case_for_model_access only once for all Anthropic models
        # Format the data as required by the API
        import base64
        import json

        form_data = {"companyName": company_name, "useCases": use_cases}

        json_data = json.dumps(form_data, ensure_ascii=False)
        encoded_data = base64.b64encode(json_data.encode("utf-8"))

        bedrock_client.put_use_case_for_model_access(formData=encoded_data)

        print("✓ Anthropic use case submitted successfully")

    except Exception as e:
        print(f"Warning: Failed to submit Anthropic use case: {str(e)}")
        print("Continuing with model subscriptions...")


def subscribe_to_model(model_id: str, region: str) -> tuple[bool, str]:
    """Subscribe to a single model using agreement APIs.

    Args:
        model_id: The model ID to subscribe to
        region: AWS region to use for the Bedrock client

    Returns:
        Tuple of (success: bool, message: str) indicating subscription status
    """
    try:
        # Create Bedrock client for the specified region
        bedrock_client = boto3.client("bedrock", region_name=region)

        # Step 1: Call list_foundation_model_agreement_offers for the model
        try:
            offers_response = bedrock_client.list_foundation_model_agreement_offers(
                modelId=model_id
            )
        except Exception as e:
            return False, f"Failed to get agreement offers: {str(e)}"

        # Step 2: Extract offers from response
        offers = offers_response.get("offers", [])

        if not offers:
            # Skip models that have no available offers (requirement 2.5)
            return False, "No agreement offers available"

        # Step 3: Extract offer token from first available offer
        first_offer = offers[0]
        offer_token = first_offer.get("offerToken")

        if not offer_token:
            return False, "No offer token found in first offer"

        # Step 4: Call create_foundation_model_agreement with offer token and model ID
        try:
            agreement_response = bedrock_client.create_foundation_model_agreement(
                offerToken=offer_token, modelId=model_id
            )

            # Step 5: Handle successful subscription response
            agreement_arn = agreement_response.get("agreementArn", "")
            if agreement_arn:
                return True, f"Successfully subscribed (Agreement: {agreement_arn})"
            else:
                return True, "Successfully subscribed"

        except Exception as e:
            # Handle subscription errors gracefully and continue with remaining models
            error_message = str(e)

            # Check if the model is already subscribed
            if "Agreement already exists" in error_message:
                return True, "Already subscribed"

            return False, f"Failed to create agreement: {error_message}"

    except Exception as e:
        # Handle any other errors gracefully
        return False, f"Unexpected error during subscription: {str(e)}"


def main():
    """Main function with CLI interface and processing flow."""
    parser = argparse.ArgumentParser(
        description="Subscribe to Amazon Bedrock foundation models using agreement APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Subscribe to all available models
  %(prog)s "Anthropic*"                 # Subscribe to all Anthropic models
  %(prog)s "*claude*" "*gpt*"           # Subscribe to Claude and GPT models
  %(prog)s "anthropic.claude-3-sonnet*" # Subscribe to specific model ID pattern
  %(prog)s --skip-use-case "Anthropic*" # Skip use case submission for Anthropic
        """,
    )

    # Region argument
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region to use (default: us-east-1)"
    )

    # Anthropic use case parameters
    parser.add_argument(
        "--company-name", help="Company name for Anthropic use case submission"
    )

    parser.add_argument(
        "--use-cases", help="Use cases description for Anthropic models"
    )

    parser.add_argument(
        "--skip-use-case",
        action="store_true",
        help="Skip Anthropic use case submission even for Anthropic models",
    )

    # Glob patterns for model filtering
    parser.add_argument(
        "patterns",
        nargs="*",
        help="Glob patterns to match against providerName + modelName or modelId",
    )

    args = parser.parse_args()

    print("Amazon Bedrock Model Subscription Tool")
    print(f"Region: {args.region}")

    if args.patterns:
        print(f"Patterns: {', '.join(args.patterns)}")
    else:
        print("Processing all available models that require subscriptions")

    if args.skip_use_case:
        print("Skipping Anthropic use case submission")

    print("-" * 60)

    try:
        # Step 1: Get all foundation models
        print("Discovering foundation models...")
        models = get_foundation_models(args.region)

        # Step 2: Filter models based on patterns
        if args.patterns:
            print(f"Filtering models with patterns: {', '.join(args.patterns)}")
            filtered_models = filter_models(models, args.patterns)
        else:
            print("Processing all models that require subscriptions...")
            filtered_models = filter_models(models, [])

        print(f"Found {len(filtered_models)} models to process")

        # Step 3: Handle Anthropic use case if needed
        anthropic_models = [
            m
            for m in filtered_models
            if m.get("providerName", "").lower() == "anthropic"
        ]
        if anthropic_models:
            print(f"Found {len(anthropic_models)} Anthropic models")
            handle_anthropic_use_case(
                args.region, args.company_name, args.use_cases, args.skip_use_case
            )

        # Step 4: Process each model for subscription
        print("\nProcessing model subscriptions...")
        success_count = 0
        failure_count = 0

        for model in filtered_models:
            model_id = model.get("modelId", "unknown")
            print(f"Processing {model_id}...")

            success, message = subscribe_to_model(model_id, args.region)
            if success:
                success_count += 1
                print(f"  ✓ {message}")
            else:
                failure_count += 1
                print(f"  ✗ {message}")

        # Step 5: Show final summary
        print("\n" + "=" * 60)
        print("Subscription Summary:")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {failure_count}")
        print(f"  Total: {success_count + failure_count}")
        print("Processing complete!")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
