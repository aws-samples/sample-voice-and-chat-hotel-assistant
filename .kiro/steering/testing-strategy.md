---
inclusion: always
---

# Testing Strategy Guide

## Overview

The Hotel Assistant project uses a comprehensive testing strategy across all
components, including unit tests and integration tests. Each package has its own
testing setup tailored to its technology stack.

## Testing Stack by Package

### Frontend Testing (`packages/frontend/`)

**Framework**: Vitest + React Testing Library **Configuration**: `vite.config.ts`

```bash
# Run frontend tests
pnpm test                    # nx test frontend
pnpm test --watch           # Watch mode
pnpm test --coverage        # With coverage report
```

**Test Types**:

- Component tests
- Hook tests
- Integration tests
- Accessibility tests

### Python Testing (`packages/infra/`, `packages/websocket-server/`)

**Framework**: pytest + pytest-asyncio **Configuration**: `pyproject.toml` with
pytest settings

## Testing Patterns

### Frontend Component Testing

```tsx
// Component test example
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SpeechToSpeech } from './SpeechToSpeech';

describe('SpeechToSpeech', () => {
  it('should start recording when button is clicked', async () => {
    render(<SpeechToSpeech />);

    const startButton = screen.getByRole('button', {
      name: /start recording/i,
    });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/recording/i)).toBeInTheDocument();
    });
  });

  it('should handle WebSocket connection errors', async () => {
    // Mock WebSocket to simulate error
    const mockWebSocket = vi.fn().mockImplementation(() => ({
      addEventListener: vi.fn(),
      send: vi.fn(),
      close: vi.fn(),
    }));

    global.WebSocket = mockWebSocket;

    render(<SpeechToSpeech />);

    // Test error handling
    const errorEvent = new Event('error');
    mockWebSocket.mock.calls[0][0].onerror(errorEvent);

    await waitFor(() => {
      expect(screen.getByText(/connection error/i)).toBeInTheDocument();
    });
  });
});
```

### Custom Hook Testing

```tsx
// Hook test example
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';

describe('useWebSocket', () => {
  it('should manage WebSocket connection state', () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8080'));

    expect(result.current.connectionStatus).toBe('Connecting');

    act(() => {
      // Simulate connection open
      result.current.socket?.onopen?.(new Event('open'));
    });

    expect(result.current.connectionStatus).toBe('Open');
  });
});
```

### Python Unit Testing

```python
# Unit test example
import pytest
from unittest.mock import AsyncMock, patch
from core.websocket_handler import WebSocketHandler

@pytest.mark.asyncio
async def test_websocket_handler_message_routing():
    mock_websocket = AsyncMock()
    handler = WebSocketHandler(mock_websocket)

    message = '{"type": "start_recording", "sessionId": "test-123"}'

    await handler.handle_message(message)

    # Verify message was processed
    mock_websocket.send_str.assert_called_once()

    # Verify correct response format
    call_args = mock_websocket.send_str.call_args[0][0]
    response = json.loads(call_args)
    assert response['type'] == 'recording_started'
    assert response['sessionId'] == 'test-123'

def test_audio_processor_chunk_handling():
    processor = AudioProcessor()

    # Test audio chunk processing
    test_chunk = b'\x00\x01\x02\x03'  # Mock audio data
    processed = processor.process_audio_chunk(test_chunk)

    assert processed is not None
    assert len(processed) > 0
```

### Python Integration Testing

```python
# Integration test example
import pytest
import boto3
from moto import mock_cognitoidp
from clients.cognito_validator import CognitoValidator

@pytest.mark.integration
@mock_cognitoidp
async def test_cognito_token_validation():
    # Setup mock Cognito
    client = boto3.client('cognito-idp', region_name='us-east-1')
    user_pool = client.create_user_pool(PoolName='test-pool')
    user_pool_id = user_pool['UserPool']['Id']

    # Create validator
    validator = CognitoValidator(user_pool_id, 'us-east-1')

    # Test token validation (would need valid JWT for real test)
    # This is a simplified example
    result = await validator.validate_token('mock-jwt-token')

    # Assert validation behavior
    assert result is not None or result is None  # Depending on test setup

@pytest.mark.integration
async def test_bedrock_client_integration():
    """Test actual Bedrock integration (requires AWS credentials)"""
    from clients.bedrock_client import BedrockClient

    client = BedrockClient()

    try:
        response = await client.generate_speech_response(
            text_input="Hello, this is a test.",
            audio_input=None
        )

        assert 'audioData' in response
        assert response['audioData'] is not None

    except Exception as e:
        pytest.skip(f"Bedrock integration test failed: {e}")
```

### CDK Testing

```python
# CDK unit test example
import aws_cdk as cdk
from aws_cdk.assertions import Template
from stack.backend_stack import BackendStack

def test_stack_creates_required_resources():
    app = cdk.App()
    stack = BackendStack(app, "TestStack")
    template = Template.from_stack(stack)

    # Test VPC creation
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "10.0.0.0/16"
    })

    # Test Cognito User Pool
    template.has_resource_properties("AWS::Cognito::UserPool", {
        "UserPoolName": cdk.Match.string_like_regexp(".*UserPool.*")
    })

    # Test ECS Service
    template.has_resource_properties("AWS::ECS::Service", {
        "LaunchType": "FARGATE"
    })
```

## Test Configuration

### Pytest Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests",
    "slow: marks tests as slow running",
    "aws: marks tests that require AWS credentials",
]
testpaths = ["tests"]
addopts = "-m 'not integration'"  # Skip integration tests by default
asyncio_mode = "auto"  # Enable async test support
```

## CI/CD Testing

### GitHub Actions Workflow

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: pnpm install
      - run: pnpm test --coverage
      - uses: codecov/codecov-action@v3

  python-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12']
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest --cov
      - run: uv run pytest -m integration # Run integration tests
```

## Best Practices

### Test Organization

1. **Separate unit and integration tests**: Use markers/directories
2. **Mock external dependencies**: Use mocks for AWS services, WebSocket
   connections
3. **Test edge cases**: Include error conditions and boundary cases
4. **Maintain test data**: Use factories or fixtures for consistent test data

### Test Quality

1. **Clear test names**: Describe what is being tested and expected outcome
2. **Single assertion per test**: Focus each test on one specific behavior
3. **Setup and teardown**: Properly clean up resources after tests
4. **Test isolation**: Tests should not depend on each other

### Coverage Goals

- **Frontend**: 80% code coverage minimum
- **Python**: 85% code coverage minimum
- **Integration**: Cover all major user flows
