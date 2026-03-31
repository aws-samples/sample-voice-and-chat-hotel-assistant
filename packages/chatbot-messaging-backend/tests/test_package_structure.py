# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Test basic package structure and imports."""


def test_package_import():
    """Test that the main package can be imported."""
    import chatbot_messaging_backend

    assert chatbot_messaging_backend.__version__ == "1.0.0"


def test_handlers_module_import():
    """Test that handlers module can be imported."""
    from chatbot_messaging_backend import handlers

    assert handlers is not None


def test_models_module_import():
    """Test that models module can be imported."""
    from chatbot_messaging_backend import models

    assert models is not None


def test_utils_module_import():
    """Test that utils module can be imported."""
    from chatbot_messaging_backend import utils

    assert utils is not None


def test_lambda_handler_import():
    """Test that lambda handler can be imported."""
    from chatbot_messaging_backend.handlers.lambda_handler import lambda_handler

    assert lambda_handler is not None
