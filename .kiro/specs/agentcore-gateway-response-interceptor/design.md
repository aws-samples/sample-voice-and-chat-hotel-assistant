# Design Document

## Overview

This design implements an AgentCore Gateway response interceptor that transforms
all HTTP responses to status code 200, preserving the original response body.
This simple approach allows AI agents to access error details in the response
body rather than being blocked by non-2xx status codes.

The solution consists of:

1. A minimal Python Lambda function that sets all status codes to 200
2. CDK infrastructure to deploy and configure the Lambda as a gateway
   interceptor
3. Updated integration tests that expect 200 status codes for all responses

## Architecture

### High-Level Flow

```
Hotel PMS API → AgentCore Gateway → Response Interceptor Lambda → AI Agent
   (any status)                        (always 200)
```

**Before Interceptor:**

```
API returns 400 → Gateway → AI Agent receives generic error
API returns 404 → Gateway → AI Agent receives generic error
API returns 500 → Gateway → AI Agent receives generic error
```

**After Interceptor:**

```
API returns 400 → Gateway → Interceptor → AI Agent receives 200 with error body
API returns 404 → Gateway → Interceptor → AI Agent receives 200 with error body
API returns 500 → Gateway → Interceptor → AI Agent receives 200 with error body
API returns 200 → Gateway → Interceptor → AI Agent receives 200 with success body
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        AgentCore Gateway                         │
│                                                                   │
│  ┌──────────────┐      ┌──────────────────────────────────┐    │
│  │   Request    │      │    Response Interceptor Lambda    │    │
│  │   Handler    │──────▶                                   │    │
│  │              │      │  - Receives gateway response       │    │
│  └──────────────┘      │  - Sets statusCode = 200          │    │
│         │              │  - Preserves original body         │    │
│         ▼              │  - Returns transformed response    │    │
│  ┌──────────────┐      └──────────────────────────────────┘    │
│  │  Hotel PMS   │                                                │
│  │     API      │                                                │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Response Interceptor Lambda

**Location:** `packages/infra/stack/lambdas/gateway_response_interceptor.py`

**Purpose:** Transform all HTTP status codes to 200 while preserving response
body

**Interface:**

```python
def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for AgentCore Gateway response interceptor.

    Input Event Structure:
    {
        "interceptorInputVersion": "1.0",
        "mcp": {
            "gatewayRequest": {...},
            "gatewayResponse": {
                "statusCode": 400,  # Original status code
                "headers": {...},
                "body": {           # Original response body
                    "error": true,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid input"
                }
            }
        }
    }

    Output Structure:
    {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,  # Always 200
                "body": {           # Original body preserved
                    "error": true,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid input"
                }
            }
        }
    }
    """
```

**Implementation:**

```python
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Transform all gateway responses to status code 200.

    This interceptor ensures AI agents can access response bodies
    regardless of the original HTTP status code.
    """
    mcp_data = event.get('mcp', {})

    # Check if this is a RESPONSE interceptor
    if 'gatewayResponse' not in mcp_data or mcp_data['gatewayResponse'] is None:
        logger.warning("Not a RESPONSE interceptor event, passing through")
        return event

    gateway_response = mcp_data.get('gatewayResponse', {})
    original_status = gateway_response.get('statusCode', 200)

    logger.info(f"Transforming status code {original_status} to 200")

    # Return transformed response with status code 200
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,
                "body": gateway_response.get('body', {})
            }
        }
    }
```

### 2. CDK Infrastructure

**Location:** `packages/infra/stack/hotel_pms_stack.py` (or new construct)

**Components:**

1. **Lambda Function**
   - Runtime: Python 3.13
   - Architecture: ARM64
   - Memory: 128 MB (minimal)
   - Timeout: 10 seconds
   - Handler: `gateway_response_interceptor.lambda_handler`

2. **IAM Role**
   - Basic Lambda execution role
   - CloudWatch Logs permissions

3. **Gateway Interceptor Configuration**
   - Interception point: RESPONSE
   - Lambda ARN reference
   - No request headers passed (not needed)

**CDK Implementation:**

```python
from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_bedrockagentcore as bedrockagentcore,
    Duration,
)
import os

class HotelPMSStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ... existing code before gateway creation ...

        # Create response interceptor Lambda
        lambda_code_path = os.path.join(
            os.path.dirname(__file__),
            "lambdas"
        )

        interceptor_lambda = _lambda.Function(
            self,
            "GatewayResponseInterceptor",
            runtime=_lambda.Runtime.PYTHON_3_13,
            architecture=_lambda.Architecture.ARM_64,
            handler="gateway_response_interceptor.lambda_handler",
            code=_lambda.Code.from_asset(lambda_code_path),
            memory_size=128,
            timeout=Duration.seconds(10),
            description="AgentCore Gateway response interceptor - transforms all status codes to 200",
        )

        # Grant gateway permission to invoke Lambda
        interceptor_lambda.grant_invoke(
            iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")
        )

        # Create gateway with interceptor configuration
        gateway = bedrockagentcore.CfnGateway(
            self,
            "HotelPMSGateway",
            name=f"{Stack.of(self).stack_name}-hotel-pms-gateway",
            authorizer_type="CUSTOM_JWT",
            protocol_type="MCP",
            role_arn=gateway_role.role_arn,
            # ... other gateway properties ...
            interceptor_configurations=[
                bedrockagentcore.CfnGateway.GatewayInterceptorConfigurationProperty(
                    interception_points=["RESPONSE"],
                    interceptor=bedrockagentcore.CfnGateway.InterceptorConfigurationProperty(
                        lambda_=bedrockagentcore.CfnGateway.LambdaInterceptorConfigurationProperty(
                            arn=interceptor_lambda.function_arn
                        )
                    ),
                    input_configuration=bedrockagentcore.CfnGateway.InterceptorInputConfigurationProperty(
                        pass_request_headers=False  # Not needed for response transformation
                    )
                )
            ]
        )
```

### 3. Test Updates

**Files to Update:**

- `packages/hotel-pms-simulation/tests/post_deploy/test_input_validation.py`
- `packages/hotel-pms-simulation/tests/post_deploy/test_mcp_runtime_integration.py`
- `packages/hotel-pms-simulation/tests/post_deploy/test_mcp_e2e_reservation_flow.py`

**Pattern for Updates:**

**Before:**

```python
# Old test expecting 400 status code
response = mcp_client.call_tool("check_availability", {...})
assert response.status_code == 400
assert "error" in response.body
```

**After:**

```python
# New test expecting 200 with error in body
response = mcp_client.call_tool("check_availability", {...})
assert response.status_code == 200  # Always 200 now
result = response.body
assert result.get("error") == True  # Check error flag in body
assert result.get("error_code") == "VALIDATION_ERROR"
```

## Data Models

### Interceptor Input Event

```python
from typing import TypedDict, Optional, Any

class GatewayResponse(TypedDict):
    statusCode: int
    headers: Optional[dict[str, str]]
    body: Any  # Can be dict, string, or other JSON-serializable type

class MCPData(TypedDict):
    gatewayRequest: Optional[dict]
    gatewayResponse: Optional[GatewayResponse]

class InterceptorInputEvent(TypedDict):
    interceptorInputVersion: str  # "1.0"
    mcp: MCPData
```

### Interceptor Output Response

```python
class TransformedGatewayResponse(TypedDict):
    statusCode: int  # Always 200
    body: Any  # Original body preserved

class MCPOutput(TypedDict):
    transformedGatewayResponse: TransformedGatewayResponse

class InterceptorOutputResponse(TypedDict):
    interceptorOutputVersion: str  # "1.0"
    mcp: MCPOutput
```

### Hotel PMS Error Response Structure

```python
class ErrorResponse(TypedDict):
    error: bool  # True for errors
    error_code: str  # e.g., "VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_ERROR"
    message: str  # Human-readable error message
    details: Optional[list[dict]]  # Optional validation error details
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all
valid executions of a system—essentially, a formal statement about what the
system should do. Properties serve as the bridge between human-readable
specifications and machine-verifiable correctness guarantees._

### Property 1: Status Code Transformation

_For any_ gateway response with any status code, the interceptor should return a
transformed response with status code 200 **Validates: Requirements 1.1, 2.3**

### Property 2: Body Preservation

_For any_ gateway response body, the interceptor should preserve the exact body
content without modification **Validates: Requirements 1.2, 1.5, 4.5**

### Property 3: Error Structure Preservation

_For any_ gateway response containing error fields (error, error_code, message),
the interceptor should preserve these fields in the 200 response **Validates:
Requirements 1.3, 4.1, 4.2, 4.3**

### Property 4: Success Data Preservation

_For any_ successful gateway response (2xx), the interceptor should preserve the
success data in the 200 response **Validates: Requirements 1.4, 4.4**

### Property 5: Output Format Compliance

_For any_ interceptor invocation, the output should conform to the AgentCore
Gateway interceptor output format with interceptorOutputVersion "1.0"
**Validates: Requirements 2.4, 7.3**

### Property 6: Idempotent Processing

_For any_ gateway response, processing it multiple times should produce
identical transformed responses **Validates: Requirements 8.4**

## Error Handling

### Lambda Error Handling

The Lambda function uses a simple error handling strategy:

1. **Missing Gateway Response**: If `gatewayResponse` is not present, log
   warning and return original event
2. **Invalid Event Structure**: If event structure is malformed, log error and
   return original event
3. **Lambda Timeout**: Configured with 10-second timeout (more than sufficient
   for simple transformation)
4. **Lambda Failure**: Gateway will retry automatically; idempotent design
   ensures safe retries

```python
def lambda_handler(event, context):
    try:
        mcp_data = event.get('mcp', {})

        if 'gatewayResponse' not in mcp_data or mcp_data['gatewayResponse'] is None:
            logger.warning("Not a RESPONSE interceptor event")
            return event  # Pass through unchanged

        # Transform response
        return transform_response(mcp_data)

    except Exception as e:
        logger.error(f"Error in interceptor: {str(e)}")
        return event  # Return original on error
```

### Gateway Error Handling

- **Interceptor Unavailable**: Gateway will retry with exponential backoff
- **Interceptor Timeout**: Gateway will use original response after timeout
- **Interceptor Error**: Gateway will use original response and log error

## Testing Strategy

### Unit Tests

**Location:** `packages/infra/tests/test_gateway_response_interceptor.py`

**Test Cases:**

1. **Test 400 Response Transformation**

   ```python
   def test_transform_400_to_200():
       event = create_interceptor_event(status_code=400, body={"error": True})
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["statusCode"] == 200
       assert result["mcp"]["transformedGatewayResponse"]["body"]["error"] == True
   ```

2. **Test 404 Response Transformation**

   ```python
   def test_transform_404_to_200():
       event = create_interceptor_event(status_code=404, body={"error": True, "error_code": "NOT_FOUND"})
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["statusCode"] == 200
   ```

3. **Test 500 Response Transformation**

   ```python
   def test_transform_500_to_200():
       event = create_interceptor_event(status_code=500, body={"error": True, "error_code": "INTERNAL_ERROR"})
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["statusCode"] == 200
   ```

4. **Test 200 Response Transformation**

   ```python
   def test_transform_200_to_200():
       event = create_interceptor_event(status_code=200, body={"hotel_id": "h1", "available": True})
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["statusCode"] == 200
       assert result["mcp"]["transformedGatewayResponse"]["body"]["available"] == True
   ```

5. **Test Body Preservation**

   ```python
   def test_body_preservation():
       original_body = {"complex": {"nested": {"data": [1, 2, 3]}}}
       event = create_interceptor_event(status_code=400, body=original_body)
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["body"] == original_body
   ```

6. **Test Output Format**
   ```python
   def test_output_format():
       event = create_interceptor_event(status_code=400, body={})
       result = lambda_handler(event, None)
       assert result["interceptorOutputVersion"] == "1.0"
       assert "mcp" in result
       assert "transformedGatewayResponse" in result["mcp"]
   ```

### Integration Tests

**Updates to Existing Tests:**

1. **test_input_validation.py**
   - Update all assertions to expect 200 status code
   - Check error fields in response body instead of status codes
2. **test_mcp_runtime_integration.py**
   - Update tool call assertions to expect 200
   - Verify error handling through body content
3. **test_mcp_e2e_reservation_flow.py**
   - Update end-to-end flow assertions
   - Verify success and error cases both return 200

**Example Integration Test Update:**

```python
# Before
def test_validation_error_returns_400(mcp_client):
    response = mcp_client.call_tool("check_availability", {
        "hotel_id": "",  # Invalid
        "check_in_date": "2024-01-01",
        "check_out_date": "2024-01-02",
        "guests": 2
    })
    assert response.status_code == 400
    assert "error" in response.body

# After
def test_validation_error_returns_200_with_error_body(mcp_client):
    response = mcp_client.call_tool("check_availability", {
        "hotel_id": "",  # Invalid
        "check_in_date": "2024-01-01",
        "check_out_date": "2024-01-02",
        "guests": 2
    })
    assert response.status_code == 200  # Always 200 now
    result = response.body
    assert result.get("error") == True
    assert result.get("error_code") == "VALIDATION_ERROR"
    assert "hotel_id" in result.get("message", "")
```

### Property-Based Tests

**Location:** `packages/infra/tests/test_gateway_interceptor_properties.py`

**Property Tests:**

1. **Property 1: Status Code Transformation**

   ```python
   @given(status_code=st.integers(min_value=100, max_value=599))
   def test_all_status_codes_become_200(status_code):
       """For any status code, interceptor returns 200."""
       event = create_interceptor_event(status_code=status_code, body={})
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["statusCode"] == 200
   ```

2. **Property 2: Body Preservation**

   ```python
   @given(body=st.recursive(
       st.none() | st.booleans() | st.integers() | st.text(),
       lambda children: st.lists(children) | st.dictionaries(st.text(), children)
   ))
   def test_body_preserved_unchanged(body):
       """For any body structure, interceptor preserves it exactly."""
       event = create_interceptor_event(status_code=400, body=body)
       result = lambda_handler(event, None)
       assert result["mcp"]["transformedGatewayResponse"]["body"] == body
   ```

3. **Property 6: Idempotent Processing**
   ```python
   @given(
       status_code=st.integers(min_value=100, max_value=599),
       body=st.dictionaries(st.text(), st.text())
   )
   def test_idempotent_processing(status_code, body):
       """Processing same event multiple times produces identical results."""
       event = create_interceptor_event(status_code=status_code, body=body)
       result1 = lambda_handler(event, None)
       result2 = lambda_handler(event, None)
       assert result1 == result2
   ```

## Security Considerations

### IAM Permissions

**Lambda Execution Role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

**Gateway Invoke Permission:**

```python
interceptor_lambda.grant_invoke(
    iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")
)
```

### Security Best Practices

1. **Least Privilege**: Lambda only has CloudWatch Logs permissions
2. **No Data Persistence**: Stateless function with no external storage
3. **No Sensitive Logging**: Function doesn't log request/response bodies
4. **Service Principal**: Gateway uses service principal for invocation
5. **Idempotent Design**: Safe for automatic retries

## Deployment Considerations

### Deployment Order

1. Deploy Lambda function
2. Update gateway configuration with interceptor
3. Deploy updated tests
4. Verify interceptor is working

### Rollback Strategy

If issues occur:

1. Remove interceptor configuration from gateway
2. Gateway will revert to passing through original status codes
3. Tests will need to be reverted to expect original status codes

### Monitoring

**CloudWatch Metrics:**

- Lambda invocation count
- Lambda error count
- Lambda duration

**CloudWatch Logs:**

- Interceptor invocations
- Status code transformations
- Any errors or warnings

**Alarms:**

- Lambda error rate > 1%
- Lambda duration > 5 seconds

## Performance Considerations

### Lambda Performance

- **Cold Start**: ~100-200ms (minimal dependencies)
- **Warm Execution**: ~1-5ms (simple transformation)
- **Memory**: 128 MB (minimal)
- **Concurrent Executions**: Scales automatically with gateway traffic

### Gateway Impact

- **Latency Addition**: ~1-10ms per request
- **Throughput**: No impact (Lambda scales automatically)
- **Cost**: Minimal (simple function, low memory, fast execution)

## Alternative Approaches Considered

### 1. Modify API to Return 200 for Errors

**Rejected:** Would require changing API contract and all existing clients

### 2. Complex Error Structure Transformation

**Rejected:** Unnecessary complexity; simple status code change is sufficient

### 3. Request Interceptor Instead of Response

**Rejected:** Need to transform responses, not requests

### 4. Gateway Configuration Without Interceptor

**Rejected:** Gateway doesn't support status code transformation without
interceptor

## Future Enhancements

1. **Metrics Dashboard**: CloudWatch dashboard for interceptor performance
2. **Error Rate Alerting**: SNS notifications for high error rates
3. **Response Caching**: Cache transformed responses for identical requests
4. **Header Preservation**: Optionally preserve response headers if needed
