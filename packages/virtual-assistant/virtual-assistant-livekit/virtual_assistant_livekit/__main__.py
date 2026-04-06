# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Entry point for running the hotel assistant livekit agent as a module.

This allows the agent to be run with: python -m hotel_assistant_livekit
"""

from .agent import main

if __name__ == "__main__":
    main()
