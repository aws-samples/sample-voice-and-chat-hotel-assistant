# Requirements Document

## Introduction

The Hotel PMS MCP server currently provides generic error messages that don't
help AI agents understand what went wrong with their requests. When agents send
invalid input (like float values for integer fields or dates in the past), they
receive unhelpful messages like "Failed to store quote. Please try again." or
"An internal error has occurred". This makes it impossible for agents to
self-correct and retry with valid input.

This feature will implement comprehensive input validation using Pydantic models
generated from the OpenAPI specification, ensuring that all API operations
validate input before processing and return detailed, actionable error messages
that agents can use to fix their requests.

## Glossary

- **Hotel PMS**: Hotel Property Management System - the backend API for managing
  hotel reservations
- **MCP Server**: Model Context Protocol server that exposes hotel operations as
  tools for AI agents
- **AgentCore Gateway**: AWS service that routes MCP tool calls to backend
  services
- **Pydantic**: Python library for data validation using type annotations
- **OpenAPI Specification**: Machine-readable API definition in YAML format
- **datamodel-code-generator**: Tool that generates Pydantic models from OpenAPI
  specs
- **Input Validation**: Process of checking that request parameters meet
  expected types and constraints
- **Error Response**: Structured response containing error details that help
  agents understand what went wrong

## Requirements

### Requirement 1

**User Story:** As an AI agent, I want to receive detailed validation error
messages when I send invalid input, so that I can understand what's wrong and
retry with corrected parameters.

#### Acceptance Criteria

1. WHEN an agent sends a request with invalid parameter types (e.g., float
   instead of integer for guests field) THEN the system SHALL return an error
   response with specific field-level validation details
2. WHEN an agent sends a request with dates in the past THEN the system SHALL
   return an error response indicating that dates must be in the future
3. WHEN an agent sends a request with missing required fields THEN the system
   SHALL return an error response listing all missing required fields
4. WHEN an agent sends a request with invalid enum values THEN the system SHALL
   return an error response listing the valid enum options
5. WHEN validation errors occur THEN the system SHALL return HTTP 400 status
   with error_code "VALIDATION_ERROR" and a message field containing
   human-readable details

### Requirement 2

**User Story:** As a developer, I want Pydantic models to be automatically
generated from the OpenAPI specification, so that validation logic stays
synchronized with the API contract.

#### Acceptance Criteria

1. WHEN the OpenAPI specification is updated THEN the system SHALL provide a
   command to regenerate Pydantic models
2. WHEN Pydantic models are generated THEN they SHALL include all request and
   response schemas from the OpenAPI spec
3. WHEN Pydantic models are generated THEN they SHALL preserve field types,
   constraints, and descriptions from the OpenAPI spec
4. WHEN Pydantic models are generated THEN they SHALL be placed in a dedicated
   models directory

### Requirement 3

**User Story:** As a developer, I want all API operations to validate input
using Pydantic models before processing, so that invalid requests are caught
early with clear error messages.

#### Acceptance Criteria

1. WHEN any API operation receives a request THEN the system SHALL validate the
   request body against the corresponding Pydantic model before calling business
   logic
2. WHEN validation fails THEN the system SHALL capture all validation errors
   from Pydantic
3. WHEN validation fails THEN the system SHALL format validation errors into a
   structured error response
4. WHEN validation succeeds THEN the system SHALL pass the validated data to the
   business logic layer
5. WHEN validation errors occur THEN the system SHALL log the validation
   failures with request context for debugging

### Requirement 4

**User Story:** As a developer, I want integration tests that verify validation
error handling, so that I can ensure agents receive helpful error messages for
common mistakes.

#### Acceptance Criteria

1. WHEN integration tests run THEN they SHALL test the generate_quote operation
   with float values in the guests field
2. WHEN integration tests run THEN they SHALL test the generate_quote operation
   with dates in the past
3. WHEN integration tests run THEN they SHALL verify that error responses
   include specific field names and validation messages
4. WHEN integration tests run THEN they SHALL verify that error responses use
   the VALIDATION_ERROR error code
5. WHEN integration tests run THEN they SHALL test multiple validation errors in
   a single request

### Requirement 5

**User Story:** As a developer, I want date validation to ensure check-in and
check-out dates are valid for hotel reservations, so that agents cannot create
reservations with impossible dates.

#### Acceptance Criteria

1. WHEN a request includes check_in_date THEN the system SHALL validate that the
   date is today or in the future
2. WHEN a request includes check_out_date THEN the system SHALL validate that
   the date is after check_in_date
3. WHEN date validation fails THEN the system SHALL return an error message
   explaining the date constraint violation
4. WHEN dates are in valid YYYY-MM-DD format but represent invalid dates THEN
   the system SHALL return an error message about the invalid date
5. WHEN dates are in the wrong format THEN the system SHALL return an error
   message specifying the required YYYY-MM-DD format

### Requirement 6

**User Story:** As a developer, I want the OpenAPI specification to be the
single source of truth for API contracts, so that documentation, validation, and
implementation stay synchronized.

#### Acceptance Criteria

1. WHEN the OpenAPI specification defines a field as required THEN the generated
   Pydantic model SHALL enforce that requirement
2. WHEN the OpenAPI specification defines field constraints (min, max, enum)
   THEN the generated Pydantic model SHALL enforce those constraints
3. WHEN the OpenAPI specification defines field types THEN the generated
   Pydantic model SHALL use corresponding Python types
4. WHEN the OpenAPI specification includes field descriptions THEN the generated
   Pydantic model SHALL preserve those descriptions
5. WHEN the OpenAPI specification changes THEN developers SHALL regenerate
   models to maintain consistency

### Requirement 7

**User Story:** As an AI agent, I want error responses to follow a consistent
structure across all operations, so that I can reliably parse and understand
validation errors.

#### Acceptance Criteria

1. WHEN any validation error occurs THEN the response SHALL include an "error"
   field set to true
2. WHEN any validation error occurs THEN the response SHALL include an
   "error_code" field with value "VALIDATION_ERROR"
3. WHEN any validation error occurs THEN the response SHALL include a "message"
   field with a human-readable summary
4. WHEN multiple validation errors occur THEN the response SHALL include a
   "details" field with an array of field-specific errors
5. WHEN field-specific errors are returned THEN each error SHALL include the
   field name, error type, and specific constraint that was violated
