# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Simple integration test to verify test discovery."""

import pytest


@pytest.mark.integration
def test_simple():
    """Simple test to verify integration test discovery."""
    assert True


def test_regular():
    """Regular test without integration marker."""
    assert True
