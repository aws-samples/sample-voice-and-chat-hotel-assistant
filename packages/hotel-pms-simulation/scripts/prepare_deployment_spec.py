#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Prepare OpenAPI spec for deployment by adding servers block with template variable."""

import json
import sys
from pathlib import Path

import yaml


def prepare_deployment_spec():
    """Read openapi.source.yaml, add servers block, and write openapi.json for deployment."""
    source_path = Path(__file__).parent.parent / "openapi.source.yaml"
    output_path = Path(__file__).parent.parent / "openapi.json"

    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    with open(source_path) as f:
        spec = yaml.safe_load(f)

    # Add servers block with template variable
    spec["servers"] = [
        {"url": "{{ base_url }}", "description": "Hotel PMS API endpoint."}
    ]

    # Write output as JSON (consumed by CDK DeployTimeSubstitutedFile)
    with open(output_path, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"✓ Created deployment spec: {output_path}")
    print("  Added servers block with {{ base_url }} template")


if __name__ == "__main__":
    prepare_deployment_spec()
