# AWS Lambda Handler Real Integration Test Summary

## Task 7: Verify lambda_handler integration

This document summarizes the comprehensive **real integration testing**
performed to verify that the lambda_handler properly integrates with Pydantic
models according to requirements 2.1, 2.2, and 2.3.

**Important**: These are true integration tests that use bastion host, port
forwarding, and real database connections - **no mocking is used**.

## Real Integration Test Infrastructure

### Test Setup

- **Bastion Host**: Creates EC2 instance in same VPC as Lambda
- **Port Forwarding**: Uses Session Manager, a capability of AWS Systems Manager for secure database access
- **Real Database**: Tests against actual Aurora PostgreSQL cluster
- **Environment Variables**: Uses real database credentials from Secrets Manager
- **No Mocks**: All services, databases, and handlers are real

### Prerequisites

1. SSMInstanceProfile IAM role exists
2. HotelPmsStack deployed with Aurora database
3. AWS credentials configured
4. Database contains seed data

## Test Coverage

### 1. Real Data Pydantic Model Detection Tests

**Requirement 2.1**: Test that lambda_handler properly detects Pydantic models
with real data

✅ **test_lambda_handler_get_hotels_real_data**

- Tests against actual hotels table in Aurora database
- Verifies lambda_handler detects HotelsListResponse Pydantic model
- Confirms result is converted to JSON-serializable dictionary
- Validates datetime serialization from real database timestamps

✅ **test_lambda_handler_check_availability_real_data**

- Uses real hotel IDs from database
- Tests AvailabilityResponseWrapper detection and processing
- Verifies date fields are serialized as ISO strings
- Tests against real room availability logic

✅ **test_lambda_handler_create_reservation_real_data**

- Creates actual reservations in database
- Tests ReservationResponseWrapper with real data
- Verifies both datetime and Decimal serialization from database
- Tests complete reservation creation workflow

✅ **test_lambda_handler_get_reservations_real_data**

- Retrieves actual reservations from database
- Tests ReservationsListResponse with real reservation data
- Verifies list response structure with actual total_count

### 2. Real Database model_dump(mode='json') Verification

**Requirement 2.2**: Confirm model_dump(mode='json') is called correctly with
real data

✅ **All real integration tests verify JSON mode serialization**

- Every test confirms that datetime objects from database are serialized as ISO
  strings
- Decimal objects from database are serialized as JSON-compatible values
- Complex nested structures from real queries are properly flattened
- No raw Python objects remain in final output

✅ **Real database field serialization verification**

- Date fields from database: `"2025-03-15"` (ISO date format)
- DateTime fields from database: `"2025-01-15T10:30:00"` (ISO datetime format)
- Decimal fields from database: `450.0` or `"450.0"` (JSON-compatible numeric
  values)

### 3. Real Infrastructure JSON Serialization Tests

**Requirement 2.3**: Verify final return values are JSON serializable with real
data

✅ **test_lambda_handler_json_serialization_comprehensive**

- Tests multiple operations against real database
- Performs `json.dumps(result)` to verify JSON compatibility with real data
- Performs `json.loads(json.dumps(result))` for round-trip verification
- No serialization errors occur with any real response type

✅ **Real complex data structure serialization**

- Nested Pydantic models with real database relationships
- List responses with multiple real database items
- Mixed data types from actual database queries

### 4. Real Infrastructure Error Handling

**Requirement 2.3**: Test error handling with real infrastructure

✅ **test_lambda_handler_error_handling_real_infrastructure**

- Tests invalid tool names against real lambda_handler
- Tests invalid parameters against real database constraints
- Verifies proper error propagation with real infrastructure

### 5. Real Database Pydantic Model Detection

✅ **test_lambda_handler_pydantic_model_detection_real_data**

- Verifies Pydantic model detection with real database responses
- Confirms no raw Pydantic objects remain in final output
- Tests against actual database query results

## Key Real Integration Verification Points

### Real Infrastructure Setup

The tests use actual AWS infrastructure:

1. **EC2 Bastion Host**: Created in same VPC as Lambda functions
2. **SSM Port Forwarding**: Secure tunnel to Aurora database
3. **Aurora PostgreSQL**: Real database with actual schema and data
4. **Secrets Manager**: Real database credentials retrieval
5. **Environment Variables**: Real database connection parameters

### Real Database Connection

```python
# Real database connection through bastion host
os.environ["DB_HOST"] = "localhost"  # Through port forwarding
os.environ["DB_PORT"] = str(local_port)  # Forwarded port
os.environ["DB_NAME"] = db_name  # From Secrets Manager
os.environ["DB_USER"] = db_user  # From Secrets Manager
os.environ["DB_PASSWORD"] = db_password  # From Secrets Manager
```

### Real Lambda Handler Testing

All tests call the actual lambda_handler function:

```python
result = lambda_handler(event, context)  # No mocks - real handler
```

### Real Data Verification

Tests verify against actual database content:

```python
# Real database queries
hotels_query = "SELECT hotel_id FROM hotels LIMIT 1"
hotel_result = execute_query(hotels_query, fetch_one=True)  # Real query
hotel_id = hotel_result["hotel_id"]  # Real data
```

## Test Results Summary

- **Total Real Integration Tests**: 7 comprehensive tests
- **Infrastructure**: Real AWS resources (EC2, Aurora, SSM, Secrets Manager)
- **Database**: Real Aurora PostgreSQL with actual data
- **No Mocking**: 100% real infrastructure and data
- **Requirements Met**: 2.1, 2.2, 2.3 ✅

## Usage

```bash
# Run real integration tests (requires deployed infrastructure)
pytest tests/test_agentcore_lambda_handler_integration.py -v -s

# Set custom stack name if needed
STACK_NAME=MyHotelPmsStack pytest tests/test_agentcore_lambda_handler_integration.py -v -s
```

## Conclusion

The lambda_handler integration has been thoroughly tested with **real
infrastructure** and verified to:

1. ✅ **Properly detect Pydantic models** with real database data and call
   `model_dump(mode='json')`
2. ✅ **Ensure all return values are JSON serializable** with actual database
   responses
3. ✅ **Handle Amazon Bedrock AgentCore Gateway request formats** correctly with real
   infrastructure
4. ✅ **Work with real Aurora database** through secure bastion host connection
5. ✅ **Provide proper error handling** with real infrastructure constraints

All requirements for Task 7 have been successfully implemented and verified
using **real AWS infrastructure** with no mocking.
