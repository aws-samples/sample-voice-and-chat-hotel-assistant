# Implementation Plan

- [x] 1. Create response interceptor Lambda function
  - Create `packages/infra/stack/lambdas/gateway_response_interceptor.py` with
    simple status code transformation logic
  - Implement Lambda handler that receives gateway response and returns
    transformed response with status code 200
  - Include logging for status code transformations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ]\* 1.1 Write unit tests for interceptor Lambda
  - Create `packages/infra/tests/test_gateway_response_interceptor.py`
  - Test 400, 404, 500 responses are transformed to 200
  - Test 200 responses remain 200
  - Test body preservation for all status codes
  - Test output format compliance
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]\* 1.2 Write property-based tests for interceptor
  - Create `packages/infra/tests/test_gateway_interceptor_properties.py`
  - **Property 1: Status Code Transformation** - For any status code,
    interceptor returns 200
  - **Property 2: Body Preservation** - For any body structure, interceptor
    preserves it exactly
  - **Property 6: Idempotent Processing** - Processing same event multiple times
    produces identical results
  - _Requirements: 1.1, 1.2, 1.5_

- [x] 2. Add interceptor configuration to CDK stack
  - Update `packages/infra/stack/hotel_pms_stack.py` to create interceptor
    Lambda function
  - Configure Lambda with Python 3.13 runtime and ARM64 architecture
  - Grant bedrock-agentcore.amazonaws.com permission to invoke the Lambda
  - Add `interceptor_configurations` parameter to CfnGateway creation with
    RESPONSE interception point
  - _Requirements: 2.1, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Update integration tests to expect 200 status codes
  - Update
    `packages/hotel-pms-simulation/tests/post_deploy/test_input_validation.py`
    to expect 200 with error body
  - Update
    `packages/hotel-pms-simulation/tests/post_deploy/test_mcp_runtime_integration.py`
    to expect 200 for all tool calls
  - Update
    `packages/hotel-pms-simulation/tests/post_deploy/test_mcp_e2e_reservation_flow.py`
    to expect 200 for all responses
  - Change assertions from checking status codes to checking error fields in
    response body
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
    - [ ] 3.1 Verify interceptor functionality
    - The updated infrastructure has been deployed
    - Run post-deployment tests to verify interceptor is working
    - Verify all responses return 200 status code
    - Verify error details are preserved in response bodies
    - _Requirements: 5.5_
