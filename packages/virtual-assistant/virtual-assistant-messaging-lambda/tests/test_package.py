# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Basic package tests to verify structure."""

from virtual_assistant_messaging_lambda import __version__


def test_package_version():
    """Test that package version is defined."""
    assert __version__ == "1.0.0"


def test_package_imports():
    """Test that package modules can be imported."""
    from virtual_assistant_messaging_lambda import handlers, models, services

    # Basic import test - modules should be importable
    assert handlers is not None
    assert services is not None
    assert models is not None
