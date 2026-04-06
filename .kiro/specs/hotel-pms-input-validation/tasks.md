# Implementation Plan

- [x] 1. Update OpenAPI specification with validation constraints
  - Add minimum/maximum constraints for guests field (min: 1, max: 10)
  - Add format: date constraints for check_in_date and check_out_date fields
  - Add enum constraints for package_type (simple, detailed)
  - Add enum constraints for request_type (cleaning, maintenance, amenities,
    towels, other)
  - Document validation error responses in OpenAPI (ErrorResponse schema)
  - Note: Do NOT add ID pattern validation (e.g., hotel_id patterns) - ID
    validation is handled by business logic
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 2. Generate Pydantic models and set up validation infrastructure
  - [x] 2.1 Add dependencies
    - Add datamodel-code-generator to dev dependencies in pyproject.toml
    - Add hypothesis for property-based testing to dev dependencies
    - Run uv sync to install dependencies
    - _Requirements: 2.1_

  - [x] 2.2 Create NX targets for model generation
    - Add generate-models target with datamodel-codegen command
    - Use --formatters ruff-check ruff-format for automatic formatting
    - Create models/generated/ directory structure
    - Add **init**.py to make it a Python package
    - Add outputs configuration for NX caching
    - _Requirements: 2.1, 2.4_

  - [x] 2.3 Generate initial models
    - Run nx generate-models hotel-pms-simulation
    - Review generated models for completeness
    - Verify all request/response schemas are present
    - _Requirements: 2.2, 2.3_

  - [x] 2.4 Add custom date validators
    - Create models/generated/validators.py module
    - Add check_in_date validator (must be today or future)
    - Add check_out_date validator (must be after check_in_date)
    - Extend generated models with custom validators
    - _Requirements: 5.1, 5.2_

  - [x] 2.5 Add unit tests for custom validators
    - Create tests/test_validators.py
    - Test check_in_date future validation
    - Test check_out_date ordering validation
    - Test date format validation
    - Test invalid date value validation
    - _Requirements: 5.1, 5.2, 5.4, 5.5_

- [x] 3. Create validation error formatter utility
  - Create utils/validation_errors.py module
  - Implement format_validation_error() function
  - Handle single validation errors
  - Handle multiple validation errors
  - Preserve field names, error types, and input values
  - Format errors into standard ErrorResponse structure
  - _Requirements: 3.3, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3.1 Add unit tests for validation error formatter
  - Create tests/test_validation_errors.py
  - Test formatting single validation error
  - Test formatting multiple validation errors
  - Test preservation of field names and input values
  - Test error response structure
  - _Requirements: 3.3, 7.1, 7.2, 7.3, 7.5_

- [x] 4. Update API handlers with validation
  - [x] 4.1 Update generate_quote handler
    - Import QuoteRequest model from generated models
    - Add Pydantic validation before business logic
    - Catch ValidationError and format response using format_validation_error()
    - Log validation errors at WARNING level with request context
    - Test manually with valid and invalid inputs
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.4, 3.5_

  - [x] 4.2 Update check_availability handler
    - Import AvailabilityRequest model
    - Add Pydantic validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.3 Update create_reservation handler
    - Import ReservationRequest model
    - Add Pydantic validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.4 Update get_reservations handler
    - Add query parameter validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.5 Update get_reservation handler
    - Add path parameter validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.6 Update update_reservation handler
    - Import ReservationUpdateRequest model
    - Add Pydantic validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.7 Update checkout_guest handler
    - Import CheckoutRequest model
    - Add Pydantic validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.8 Update get_hotels handler
    - Add query parameter validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

  - [x] 4.9 Update create_housekeeping_request handler
    - Import HousekeepingRequest model
    - Add Pydantic validation
    - Format validation errors
    - _Requirements: 3.1, 3.2, 3.4_

- [x] 4.10 Add unit and property-based tests for validation
  - Create tests/test_models.py for Pydantic model tests
  - Test type validation for each field type
  - Test constraint validation (min, max, pattern)
  - Test enum validation
  - Test required field validation
  - Create tests/test_validation_properties.py for property-based tests
  - Property test: Generate random non-integer values for guests field, verify
    rejection
  - Property test: Generate random check_in/check_out dates, verify ordering
  - Property test: Generate random past dates, verify rejection
  - Property test: Generate various invalid inputs, verify consistent error
    structure
  - _Requirements: 1.1, 1.2, 2.3, 5.2, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3_
  - **Property 1: Type validation errors are reported with field details**
  - **Property 2: Past dates are rejected with clear error messages**
  - **Property 5: Validation errors have consistent structure**
  - **Property 11: Check-out date must be after check-in date**

- [x] 4.11 Update MCP tools and api_functions with validation
  - Update tools/api_functions.py to use Pydantic validators
  - Import QuoteRequestWithValidation, AvailabilityRequestWithValidation,
    ReservationRequestWithValidation
  - Add Pydantic validation in check_availability, generate_quote,
    create_reservation functions
  - Catch ValidationError and format response using format_validation_error()
  - Ensure consistent validation across API Gateway and MCP Gateway interfaces
  - Update mcp_gateway_utils.py to parse embedded validation errors from
    AgentCore Gateway responses
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.4, 3.5, 5.1, 5.2_

- [x] 5. Add integration tests for validation
  - [x] 5.1 Add tests for float guests field coercion and validation
    - Create new test file: tests/post_deploy/test_input_validation.py
    - Follow same patterns as test_mcp_e2e_reservation_flow.py (use
      mcp_gateway_utils, pytest fixtures, integration marker)
    - Add test_generate_quote_with_coercible_float_guests
    - Test generate_quote with guests=3.0 (should succeed via Pydantic coercion
      to 3)
    - Use dynamic date computation: check_in_date = (today + 30 days),
      check_out_date = (today + 32 days)
    - Verify successful response with quote_id and total_price
    - Add test_generate_quote_with_invalid_float_guests
    - Test generate_quote with guests=3.5 (should fail - non-integer float)
    - Use same dynamic date computation pattern
    - Verify error response structure (error=true,
      error_code="VALIDATION_ERROR")
    - Verify field-level error details include field="guests"
    - Verify error message indicates integer requirement
    - **Property 1: Type validation errors are reported with field details**
    - **Validates: Requirements 1.1, 4.1**

  - [x] 5.2 Add test for past dates
    - Add test_generate_quote_with_past_dates to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with check_in_date="2025-01-08" and
      check_out_date="2025-01-15"
    - Verify error response indicates future date required
    - Verify error_code is VALIDATION_ERROR
    - Verify error message explains date constraint
    - **Property 2: Past dates are rejected with clear error messages**
    - **Validates: Requirements 1.2, 5.1, 4.2**

  - [x] 5.3 Add test for multiple validation errors
    - Add test_generate_quote_with_multiple_errors to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with guests=3.5 (invalid float),
      check_in_date=(today - 7 days) (past date), package_type="invalid"
      (invalid enum)
    - Use dynamic date computation for check_in_date to ensure it's always in
      the past
    - Verify all errors are captured in details array
    - Verify each error has field, message, type, input
    - Verify at least 3 errors are reported (guests, check_in_date,
      package_type)
    - **Property 8: All validation errors are captured**
    - **Validates: Requirements 3.2, 7.4, 4.3**

  - [x] 5.4 Add test for missing required fields
    - Add test_generate_quote_with_missing_fields to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with only hotel_id provided
    - Verify error lists all missing required fields
    - **Property 3: Missing required fields are all reported**
    - **Validates: Requirements 1.3, 4.4**

  - [x] 5.5 Add test for invalid enum values
    - Add test_generate_quote_with_invalid_enum to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with package_type="invalid"
    - Verify error includes list of valid options ("simple", "detailed")
    - **Property 4: Invalid enum values include valid options**
    - **Validates: Requirements 1.4, 4.5**

  - [x] 5.6 Add test for check_out_date before check_in_date
    - Add test_generate_quote_with_invalid_date_order to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with check_out_date before check_in_date
    - Verify error explains date ordering constraint
    - **Property 11: Check-out date must be after check-in date**
    - **Validates: Requirements 5.2**

  - [x] 5.7 Add test for invalid date format
    - Add test_generate_quote_with_invalid_date_format to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with date in wrong format (e.g., "01/15/2025")
    - Verify error specifies required YYYY-MM-DD format
    - **Property 14: Wrong date formats are rejected**
    - **Validates: Requirements 5.5**

  - [x] 5.8 Add test for invalid date values
    - Add test_generate_quote_with_invalid_date_value to
      tests/post_deploy/test_input_validation.py
    - Test generate_quote with date like "2025-02-30"
    - Verify error indicates invalid date
    - **Property 13: Invalid date strings are rejected**
    - **Validates: Requirements 5.4**

  - [x] 5.9 Run integration tests
    - Run pytest tests/post_deploy/test_input_validation.py -v -m integration
    - Verify all validation error tests pass
    - Fix any failing tests before proceeding

- [x] 6. Checkpoint - Ensure all tests pass
  - Run nx test hotel-pms-simulation
  - Run integration tests: pytest -m integration
  - Verify all validation scenarios pass
  - Ensure all tests pass, ask the user if questions arise.
  - **Note**: Simplified reservation API to only require quote_id, guest_name,
    guest_email, and guest_phone (all required). Removed support for direct
    reservations without quote. Updated OpenAPI spec, Pydantic models, business
    logic in tools.py, and all related tests.
  - **Result**: All 155 unit tests passing
