# Implementation Plan

- [x] 1. Create Pydantic response wrapper models
  - Add response wrapper classes to agentcore_handler.py
  - Import required types and models from service layers
  - Use modern type annotations (dict, list instead of Dict, List)
  - _Requirements: 1.1, 4.1, 4.2_

- [x] 2. Update handler function signatures and return types
  - [x] 2.1 Update handle_check_availability function
    - Change return type annotation to AvailabilityResponseWrapper
    - Wrap service response in AvailabilityResponseWrapper
    - _Requirements: 1.1, 6.1_

  - [x] 2.2 Update handle_generate_quote function
    - Change return type annotation to QuoteResponseWrapper
    - Wrap service response in QuoteResponseWrapper
    - _Requirements: 1.1, 6.2_

  - [x] 2.3 Update handle_create_reservation function
    - Change return type annotation to ReservationResponseWrapper
    - Wrap service response in ReservationResponseWrapper
    - _Requirements: 1.1, 6.3_

  - [x] 2.4 Update handle_get_reservations function
    - Change return type annotation to ReservationsListResponse
    - Create ReservationsListResponse with reservations list and total_count
    - _Requirements: 1.1, 4.2, 6.3_

  - [x] 2.5 Update handle_get_reservation function
    - Change return type annotation to ReservationResponseWrapper
    - Wrap service response in ReservationResponseWrapper
    - _Requirements: 1.1, 6.3_

  - [x] 2.6 Update handle_update_reservation function
    - Change return type annotation to ReservationResponseWrapper
    - Wrap service response in ReservationResponseWrapper
    - _Requirements: 1.1, 6.3_

  - [x] 2.7 Update handle_checkout_guest function
    - Change return type annotation to CheckoutResponseWrapper
    - Wrap service response in CheckoutResponseWrapper
    - _Requirements: 1.1, 6.4_

  - [x] 2.8 Update handle_create_housekeeping_request function
    - Change return type annotation to HousekeepingRequestResponseWrapper
    - Wrap service response in HousekeepingRequestResponseWrapper
    - _Requirements: 1.1, 6.4_

- [x] 3. Update test assertions for Pydantic models
  - [x] 3.1 Update test_handle_get_hotels assertions
    - Change dictionary key assertions to Pydantic attribute assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.2 Update test_handle_check_availability assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.3 Update test_handle_generate_quote assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.4 Update test_handle_create_reservation assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.5 Update test_handle_get_reservations assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - Test both reservations list and total_count fields
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.6 Update test_handle_get_reservation assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.7 Update test_handle_update_reservation assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.8 Update test_handle_checkout_guest assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

  - [x] 3.9 Update test_handle_create_housekeeping_request assertions
    - Change dictionary assertions to Pydantic model assertions
    - Add JSON serialization verification test
    - _Requirements: 3.1, 3.2, 7.1_

- [x] 4. Add comprehensive JSON serialization tests
  - Create test helper function for JSON serialization verification
  - Add datetime serialization tests for handlers with datetime fields
  - Verify round-trip JSON serialization (serialize and deserialize)
  - _Requirements: 1.3, 1.4, 3.2, 3.3_

- [x] 5. Update import statements for modern type annotations
  - Remove deprecated typing.Dict and typing.List imports
  - Use builtin dict and list types in all type annotations
  - Update Any import to remain from typing module
  - _Requirements: 4.3_

- [x] 6. Run comprehensive test suite validation
  - Execute all existing tests to ensure no regressions
  - Verify all handlers return Pydantic models
  - Confirm JSON serialization works for all response types
  - Test error scenarios to ensure exception handling is preserved
  - _Requirements: 2.4, 5.1, 5.2, 7.2, 7.3, 7.4_

- [x] 7. Verify lambda_handler integration
  - Test that lambda_handler properly detects Pydantic models
  - Confirm model_dump(mode='json') is called correctly
  - Verify final return values are JSON serializable
  - Test with sample AgentCore Gateway requests
  - _Requirements: 2.1, 2.2, 2.3_
