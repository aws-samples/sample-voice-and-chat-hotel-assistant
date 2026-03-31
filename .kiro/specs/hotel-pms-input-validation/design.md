# Design Document

## Overview

This design implements comprehensive input validation for the Hotel PMS MCP
server using Pydantic models automatically generated from the OpenAPI
specification. The solution ensures that AI agents receive detailed, actionable
error messages when they send invalid requests, enabling them to self-correct
and retry with valid input.

The design follows a three-layer approach:

1. **OpenAPI Specification** - Single source of truth for API contracts
2. **Generated Pydantic Models** - Type-safe validation models created from
   OpenAPI
3. **Validation Layer** - Early validation in API handlers before business logic

## Architecture

### Current Architecture

```
Agent Request → API Gateway Handler → Tool Functions → Business Logic → DynamoDB
                     ↓ (minimal validation)
                Generic Error Response
```

### Proposed Architecture

```
Agent Request → API Gateway Handler → Pydantic Validation → Tool Functions → Business Logic → DynamoDB
                     ↓                      ↓
                     ↓                 Validation Errors
                     ↓                      ↓
                Detailed Error Response ←───┘
```

### Key Components

1. **OpenAPI Specification** (`openapi.yaml`)
   - Defines all request/response schemas
   - Specifies field types, constraints, and descriptions
   - Source of truth for API contracts

2. **Model Generator** (`datamodel-code-generator`)
   - Reads OpenAPI specification
   - Generates Pydantic models with validation
   - Runs as NX target for easy regeneration

3. **Generated Models** (`models/generated/`)
   - Pydantic models for all request schemas
   - Type-safe with automatic validation
   - Includes field constraints from OpenAPI

4. **Validation Layer** (API handlers)
   - Validates requests before processing
   - Catches Pydantic ValidationError
   - Formats errors into structured responses

5. **Error Formatter** (`utils/validation_errors.py`)
   - Converts Pydantic errors to API responses
   - Provides consistent error structure
   - Includes field-level details

## Components and Interfaces

### 1. OpenAPI Schema Definitions

The OpenAPI specification already defines comprehensive schemas. We'll enhance
them with validation constraints for type checking, string length, number
ranges, and date validation only (no ID pattern validation):

```yaml
components:
  schemas:
    QuoteRequest:
      type: object
      required: [hotel_id, room_type_id, check_in_date, check_out_date, guests]
      properties:
        hotel_id:
          type: string
          description: Unique identifier for the hotel
        room_type_id:
          type: string
          description: Unique identifier for the room type
        check_in_date:
          type: string
          format: date
          description:
            Check-in date in YYYY-MM-DD format (must be today or future)
        check_out_date:
          type: string
          format: date
          description:
            Check-out date in YYYY-MM-DD format (must be after check_in_date)
        guests:
          type: integer
          minimum: 1
          maximum: 10
          description: Number of guests
        package_type:
          type: string
          enum: [simple, detailed]
          default: simple
```

### 2. Generated Pydantic Models

Models will be generated in `models/generated/api_models.py`:

````python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class QuoteRequest(BaseModel):
    """Generated from OpenAPI: Quote request model."""

    hotel_id: str
    room_type_id: str
    check_in_date: date
    check_out_date: date
    guests: int = Field(..., ge=1, le=10)
    package_type: Literal["simple", "detailed"] = "simple"

    @field_validator('check_in_date')
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        from datetime import date as date_class
        if v < date_class.today():
            raise ValueError('check_in_date must be today or in the future')
        return v

    @field_validator('check_out_date')
    @classmethod
    def validate_check_out_date(cls, v: date, info) -> date:
        check_in = info.data.get('check_in_date')
        if check_in and v <= check_in:
            raise ValueError('check_out_date must be after check_in_date')
        return v
```$'
          description: Unique identifier for the hotel
        room_type_id:
          type: string
          description: Unique identifier for the room type
        check_in_date:
          type: string
          format: date
          description:
            Check-in date in YYYY-MM-DD format (must be today or future)
        check_out_date:
          type: string
          format: date
          description:
            Check-out date in YYYY-MM-DD format (must be after check_in_date)
        guests:
          type: integer
          minimum: 1
          maximum: 10
          description: Number of guests
        package_type:
          type: string
          enum: [simple, detailed]
          default: simple
````

### 2. Generated Pydantic Models

Models will be generated in `models/generated/api_models.py`:

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class QuoteRequest(BaseModel):
    """Generated from OpenAPI: Quote request model."""

    hotel_id: str = Field(..., pattern=r'^H-[A-Z]{3}-\d{3}$')
    room_type_id: str
    check_in_date: date
    check_out_date: date
    guests: int = Field(..., ge=1, le=10)
    package_type: Literal["simple", "detailed"] = "simple"

    @field_validator('check_in_date')
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        from datetime import date as date_class
        if v < date_class.today():
            raise ValueError('check_in_date must be today or in the future')
        return v

    @field_validator('check_out_date')
    @classmethod
    def validate_check_out_date(cls, v: date, info) -> date:
        check_in = info.data.get('check_in_date')
        if check_in and v <= check_in:
            raise ValueError('check_out_date must be after check_in_date')
        return v
```

### 3. Validation Error Formatter

New utility module `utils/validation_errors.py`:

```python
from pydantic import ValidationError
from typing import Any

def format_validation_error(error: ValidationError) -> dict[str, Any]:
    """Format Pydantic validation error into API error response.

    Args:
        error: Pydantic ValidationError

    Returns:
        Structured error response with field-level details
    """
    errors = []
    for err in error.errors():
        field_path = '.'.join(str(loc) for loc in err['loc'])
        errors.append({
            'field': field_path,
            'message': err['msg'],
            'type': err['type'],
            'input': err.get('input')
        })

    return {
        'error': True,
        'error_code': 'VALIDATION_ERROR',
        'message': 'Request validation failed',
        'details': errors
    }
```

### 4. Updated API Handlers

API handlers will validate input before calling business logic:

```python
from ..models.generated.api_models import QuoteRequest
from ..utils.validation_errors import format_validation_error
from pydantic import ValidationError

@app.post("/quotes/generate")
@tracer.capture_method
def generate_quote_handler():
    """Generate a detailed pricing quote with input validation."""
    try:
        body = app.current_event.json_body

        # Validate request using Pydantic model
        try:
            validated_request = QuoteRequest(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Quote request validation failed",
                extra={"validation_errors": error_response['details']}
            )
            raise BadRequestError(error_response['message'])

        # Convert to dict for business logic
        result = generate_quote(**validated_request.model_dump())

        # Check for business logic errors
        if result.get("error"):
            raise BadRequestError(result.get("message"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Quote generation failed", extra={"error": str(e)})
        raise InternalServerError("Failed to generate quote")
```

### 5. NX Target for Model Generation

Add to `project.json`:

```json
{
  "generate-models": {
    "executor": "nx:run-commands",
    "options": {
      "commands": [
        "mkdir -p hotel_pms_simulation/models/generated",
        "touch hotel_pms_simulation/models/generated/__init__.py",
        "uv run datamodel-codegen --input openapi.yaml --output hotel_pms_simulation/models/generated/api_models.py --input-file-type openapi --output-model-type pydantic_v2.BaseModel --field-constraints --use-standard-collections --use-schema-description --use-field-description --use-default --use-default-kwarg --target-python-version 3.13 --formatters ruff-check ruff-format"
      ],
      "parallel": false,
      "cwd": "packages/hotel-pms-simulation"
    },
    "outputs": [
      "{projectRoot}/hotel_pms_simulation/models/generated/api_models.py"
    ]
  }
}
```

## Data Models

### Error Response Structure

```python
class ValidationErrorDetail(BaseModel):
    """Single field validation error."""
    field: str  # Field path (e.g., "guests", "check_in_date")
    message: str  # Human-readable error message
    type: str  # Error type (e.g., "int_type", "greater_than_equal")
    input: Any | None  # The invalid input value

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: bool = True
    error_code: str  # e.g., "VALIDATION_ERROR", "NOT_FOUND"
    message: str  # Human-readable summary
    details: list[ValidationErrorDetail] | None = None  # Field-level errors
```

### Example Error Responses

**Float instead of integer:**

```json
{
  "error": true,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [
    {
      "field": "guests",
      "message": "Input should be a valid integer",
      "type": "int_type",
      "input": 3.0
    }
  ]
}
```

**Date in the past:**

```json
{
  "error": true,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [
    {
      "field": "check_in_date",
      "message": "check_in_date must be today or in the future",
      "type": "value_error",
      "input": "2025-01-08"
    }
  ]
}
```

**Multiple errors:**

```json
{
  "error": true,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [
    {
      "field": "guests",
      "message": "Input should be a valid integer",
      "type": "int_type",
      "input": 3.0
    },
    {
      "field": "check_in_date",
      "message": "check_in_date must be today or in the future",
      "type": "value_error",
      "input": "2025-01-08"
    }
  ]
}
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all
valid executions of a system-essentially, a formal statement about what the
system should do. Properties serve as the bridge between human-readable
specifications and machine-verifiable correctness guarantees._

Property 1: Type validation errors are reported with field details _For any_ API
request with type mismatches (float for int, string for date, etc.), the error
response should include the field name, expected type, and actual input value
**Validates: Requirements 1.1**

Property 2: Past dates are rejected with clear error messages _For any_ API
request with dates in the past, the system should return an error response
indicating that dates must be in the future **Validates: Requirements 1.2, 5.1**

Property 3: Missing required fields are all reported _For any_ API request with
missing required fields, the error response should list all missing required
fields, not just the first one **Validates: Requirements 1.3**

Property 4: Invalid enum values include valid options _For any_ API request with
invalid enum values, the error response should include the list of valid enum
options **Validates: Requirements 1.4**

Property 5: Validation errors have consistent structure _For any_ validation
error, the response should have HTTP 400 status, error=true,
error_code="VALIDATION_ERROR", and a non-empty message field **Validates:
Requirements 1.5, 7.1, 7.2, 7.3**

Property 6: Generated models preserve OpenAPI constraints _For any_ field with
constraints (min, max, enum, pattern) in the OpenAPI spec, the generated
Pydantic model should enforce those constraints **Validates: Requirements 2.3,
6.2**

Property 7: Validation happens before business logic _For any_ API operation
with invalid input, the business logic layer should never be called **Validates:
Requirements 3.1**

Property 8: All validation errors are captured _For any_ request with multiple
validation errors, all errors should be captured and returned in the details
array **Validates: Requirements 3.2, 7.4**

Property 9: Validation errors are formatted consistently _For any_ Pydantic
ValidationError, the formatted response should follow the standard structure
with error, error_code, message, and details fields **Validates: Requirements
3.3**

Property 10: Validated data is passed to business logic _For any_ valid request,
the business logic should receive the validated and potentially type-coerced
data from Pydantic **Validates: Requirements 3.4**

Property 11: Check-out date must be after check-in date _For any_ request with
both check_in_date and check_out_date, the system should reject requests where
check_out_date is not strictly after check_in_date **Validates: Requirements
5.2**

Property 12: Date validation errors explain constraints _For any_ date
validation failure, the error message should explain what constraint was
violated (past date, wrong order, invalid format, etc.) **Validates:
Requirements 5.3**

Property 13: Invalid date strings are rejected _For any_ date string that is
well-formed (YYYY-MM-DD) but represents an invalid date (like 2025-02-30), the
system should reject it with an appropriate error message **Validates:
Requirements 5.4**

Property 14: Wrong date formats are rejected _For any_ date string in the wrong
format (not YYYY-MM-DD), the system should reject it with an error message
specifying the required format **Validates: Requirements 5.5**

Property 15: Required fields in OpenAPI are required in Pydantic _For any_ field
marked as required in the OpenAPI specification, the generated Pydantic model
should enforce that requirement (no default value) **Validates: Requirements
6.1**

Property 16: OpenAPI types map to correct Python types _For any_ field type in
the OpenAPI specification (string, integer, number, boolean, array, object), the
generated Pydantic model should use the corresponding Python type **Validates:
Requirements 6.3**

Property 17: Field descriptions are preserved _For any_ field with a description
in the OpenAPI specification, the generated Pydantic model should preserve that
description in the Field() definition **Validates: Requirements 6.4**

Property 18: Error details include all required fields _For any_ field-specific
error in the details array, it should include field name, message, type, and
input value **Validates: Requirements 7.5**

## Error Handling

### Validation Error Handling

1. **Pydantic ValidationError**: Caught at API handler level and formatted into
   structured response
2. **Business Logic Errors**: Returned as before with appropriate error codes
3. **System Errors**: Logged and returned as generic 500 errors

### Error Response Hierarchy

```
ValidationError (400)
├── Type errors (int_type, string_type, etc.)
├── Constraint errors (greater_than, less_than, etc.)
├── Format errors (date_format, pattern, etc.)
└── Custom validator errors (value_error)

Business Logic Errors (400)
├── QUOTE_NOT_FOUND
├── HOTEL_NOT_FOUND
├── ROOM_TYPE_NOT_FOUND
└── AVAILABILITY_ERROR

System Errors (500)
└── INTERNAL_ERROR
```

### Logging Strategy

- **Validation Errors**: Log at WARNING level with field details
- **Business Logic Errors**: Log at ERROR level with context
- **System Errors**: Log at ERROR level with full stack trace

## Testing Strategy

### Unit Tests

1. **Validation Error Formatter Tests**
   - Test formatting of single validation error
   - Test formatting of multiple validation errors
   - Test handling of nested field errors
   - Test preservation of input values in error details

2. **Pydantic Model Tests**
   - Test type validation for each field type
   - Test constraint validation (min, max, pattern)
   - Test enum validation
   - Test custom validators (date validation)
   - Test required field validation

3. **API Handler Tests**
   - Test validation before business logic
   - Test error response structure
   - Test HTTP status codes
   - Test logging of validation errors

### Integration Tests

Integration tests will be added to
`tests/post_deploy/test_mcp_e2e_reservation_flow.py`:

1. **Test: Invalid guests field (float instead of int)**

   ```python
   async def test_generate_quote_with_float_guests():
       """Test that float values for guests field are rejected."""
       result = await call_mcp_tool_via_gateway(
           gateway_url=gateway_url,
           access_token=access_token,
           tool_name="HotelPMS___generate_quote",
           arguments={
               "hotel_id": "H-PTL-003",
               "room_type_id": "JVIL-PTL",
               "check_in_date": "2025-03-15",
               "check_out_date": "2025-03-17",
               "guests": 3.0,  # Invalid: should be int
           },
       )

       # Verify error response structure
       assert result.get("error") is True
       assert result.get("error_code") == "VALIDATION_ERROR"
       assert "details" in result

       # Verify field-specific error
       guest_error = next(
           (e for e in result["details"] if e["field"] == "guests"),
           None
       )
       assert guest_error is not None
       assert "integer" in guest_error["message"].lower()
       assert guest_error["input"] == 3.0
   ```

2. **Test: Dates in the past**

   ```python
   async def test_generate_quote_with_past_dates():
       """Test that past dates are rejected."""
       result = await call_mcp_tool_via_gateway(
           gateway_url=gateway_url,
           access_token=access_token,
           tool_name="HotelPMS___generate_quote",
           arguments={
               "hotel_id": "H-PTL-003",
               "room_type_id": "JVIL-PTL",
               "check_in_date": "2025-01-08",  # Past date
               "check_out_date": "2025-01-15",  # Past date
               "guests": 3,
           },
       )

       # Verify error response
       assert result.get("error") is True
       assert result.get("error_code") == "VALIDATION_ERROR"

       # Verify date validation error
       date_error = next(
           (e for e in result["details"] if "check_in_date" in e["field"]),
           None
       )
       assert date_error is not None
       assert "future" in date_error["message"].lower()
   ```

3. **Test: Multiple validation errors**

   ```python
   async def test_generate_quote_with_multiple_errors():
       """Test that multiple validation errors are all reported."""
       result = await call_mcp_tool_via_gateway(
           gateway_url=gateway_url,
           access_token=access_token,
           tool_name="HotelPMS___generate_quote",
           arguments={
               "hotel_id": "H-PTL-003",
               "room_type_id": "JVIL-PTL",
               "check_in_date": "2025-01-08",  # Past date
               "check_out_date": "2025-01-15",  # Past date
               "guests": 3.0,  # Invalid type
               "package_type": "invalid",  # Invalid enum
           },
       )

       # Verify multiple errors are reported
       assert result.get("error") is True
       assert len(result.get("details", [])) >= 3

       # Verify each error type is present
       error_fields = {e["field"] for e in result["details"]}
       assert "guests" in error_fields
       assert "check_in_date" in error_fields or "check_out_date" in error_fields
       assert "package_type" in error_fields
   ```

### Property-Based Tests

Property-based tests will use the `hypothesis` library to generate random test
cases:

1. **Property: Type validation**

   ```python
   from hypothesis import given, strategies as st

   @given(
       guests=st.one_of(st.floats(), st.text(), st.lists(st.integers()))
   )
   def test_guests_must_be_integer(guests):
       """Property: guests field must be an integer."""
       if not isinstance(guests, int):
           result = validate_quote_request({
               "hotel_id": "H-PTL-003",
               "room_type_id": "JVIL-PTL",
               "check_in_date": "2025-03-15",
               "check_out_date": "2025-03-17",
               "guests": guests,
           })
           assert result["error"] is True
           assert any(e["field"] == "guests" for e in result["details"])
   ```

2. **Property: Date ordering**

   ```python
   @given(
       check_in=st.dates(min_value=date.today()),
       days_between=st.integers(min_value=-10, max_value=10)
   )
   def test_checkout_must_be_after_checkin(check_in, days_between):
       """Property: check_out_date must be after check_in_date."""
       check_out = check_in + timedelta(days=days_between)

       result = validate_quote_request({
           "hotel_id": "H-PTL-003",
           "room_type_id": "JVIL-PTL",
           "check_in_date": check_in.isoformat(),
           "check_out_date": check_out.isoformat(),
           "guests": 2,
       })

       if days_between <= 0:
           assert result["error"] is True
           assert any("check_out_date" in e["field"] for e in result["details"])
       else:
           assert result.get("error") is not True
   ```

### Testing Framework

- **Unit Tests**: pytest with standard assertions
- **Integration Tests**: pytest with async support, boto3 for AWS resources
- **Property Tests**: hypothesis for generating test cases
- **Coverage Target**: 90% for validation and error handling code

## Implementation Notes

### Model Generation Process

1. Run `nx generate-models hotel-pms-simulation` to generate models
2. Generated models go to `models/generated/api_models.py`
3. Add custom validators for business logic (date validation, etc.)
4. Import generated models in API handlers

### Custom Validators

Some validation logic requires custom Pydantic validators:

```python
from pydantic import field_validator
from datetime import date

class QuoteRequestWithValidation(QuoteRequest):
    """Extended quote request with custom validation."""

    @field_validator('check_in_date')
    @classmethod
    def validate_check_in_future(cls, v: date) -> date:
        if v < date.today():
            raise ValueError('check_in_date must be today or in the future')
        return v

    @field_validator('check_out_date')
    @classmethod
    def validate_check_out_after_check_in(cls, v: date, info) -> date:
        check_in = info.data.get('check_in_date')
        if check_in and v <= check_in:
            raise ValueError('check_out_date must be after check_in_date')
        return v
```

### Migration Strategy

1. **Phase 1**: Generate models and add validation utilities
2. **Phase 2**: Update all API handlers with validation
3. **Phase 3**: Add integration tests for validation
4. **Phase 4**: Add verify-models to CI/CD pipeline

### Performance Considerations

- Pydantic validation is fast (microseconds for typical requests)
- No significant performance impact expected
- Validation happens once per request before business logic
- Error formatting only occurs on validation failures

## Dependencies

### New Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "pydantic>=2.10.0",  # Already present, ensure version 2.x
]

[dependency-groups]
dev = [
    # ... existing dev dependencies ...
    "datamodel-code-generator>=0.26.0",  # For model generation
    "hypothesis>=6.100.0",  # For property-based testing
]
```

### Tool Installation

```bash
# Install dependencies
cd packages/hotel-pms-simulation
uv sync

# Generate models
uv run datamodel-codegen --input openapi.yaml --output hotel_pms_simulation/models/generated/api_models.py --input-file-type openapi --output-model-type pydantic_v2.BaseModel --field-constraints --use-standard-collections --target-python-version 3.13
```

## Security Considerations

### Input Sanitization

- Pydantic automatically sanitizes input based on type definitions
- String fields are validated against patterns where defined
- No SQL injection risk (using DynamoDB with boto3)
- No XSS risk (API returns JSON, not HTML)

### Error Information Disclosure

- Validation errors reveal field names and constraints (acceptable for API)
- Do not include sensitive data in error messages
- Do not reveal internal system details in error messages
- Log full errors server-side for debugging

### Rate Limiting

- Validation errors should not bypass rate limiting
- Failed validation attempts count toward rate limits
- Prevents abuse through malformed requests

## Monitoring and Observability

### Logging

- Log validation errors at WARNING level
- Include request ID for correlation
- Include field names and error types
- Do not log sensitive field values

## Future Enhancements

1. **OpenAPI Validation**: Validate responses against OpenAPI spec
2. **Custom Error Messages**: Allow customization of error messages per field
3. **Localization**: Support multiple languages for error messages
