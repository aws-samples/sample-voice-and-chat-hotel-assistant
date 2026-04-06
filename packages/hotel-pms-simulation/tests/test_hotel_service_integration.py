# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for simplified hotel service using deployed DynamoDB tables."""

import os
import time

import boto3
import pytest

from hotel_pms_simulation.services.hotel_service import HotelService


@pytest.mark.integration
class TestHotelServiceIntegration:
    """Integration tests for HotelService using real DynamoDB tables."""

    @pytest.fixture(scope="class")
    def stack_outputs(self):
        """Get CloudFormation stack outputs to find table names."""
        cf_client = boto3.client("cloudformation")

        # Try multiple possible stack names following CDK naming conventions
        possible_stack_names = [
            os.environ.get("HOTEL_PMS_STACK_NAME", "HotelPmsStack"),
            "HotelPmsStack",
            "hotel-pms-stack",
            "HotelPmsStack",
        ]

        for stack_name in possible_stack_names:
            try:
                response = cf_client.describe_stacks(StackName=stack_name)
                outputs = response["Stacks"][0]["Outputs"]

                output_dict = {}
                for output in outputs:
                    output_dict[output["OutputKey"]] = output["OutputValue"]

                print(f"✅ Found CloudFormation stack: {stack_name}")
                return output_dict

            except Exception as e:
                print(f"⚠️ Stack {stack_name} not found: {e}")
                continue

        pytest.skip(
            f"Could not find HotelPMS CloudFormation stack. Tried: {possible_stack_names}"
        )

    @pytest.fixture(scope="class")
    def table_names(self, stack_outputs):
        """Extract table names from stack outputs following CDK output naming conventions."""
        table_names = {}

        # Map CDK output keys to our expected table names
        # Following the pattern from hotel_pms_stack.py CfnOutput definitions
        key_mappings = {
            "HotelsTableName": "hotels",
            "RoomTypesTableName": "room_types",
            "RateModifiersTableName": "rate_modifiers",
            "ReservationsTableName": "reservations",
            "RequestsTableName": "requests",
        }

        for output_key, table_type in key_mappings.items():
            if output_key in stack_outputs:
                table_names[table_type] = stack_outputs[output_key]
                print(f"✅ Found table {table_type}: {stack_outputs[output_key]}")

        if not table_names:
            available_outputs = list(stack_outputs.keys())
            pytest.skip(
                f"No DynamoDB table names found in stack outputs. Available outputs: {available_outputs}"
            )

        return table_names

    @pytest.fixture(scope="class")
    def service(self, table_names):
        """Create service instance with CloudFormation-discovered table names."""
        # Set environment variables for the service using CloudFormation outputs
        original_env = {}
        env_mappings = {
            "HOTELS_TABLE_NAME": table_names.get("hotels"),
            "REQUESTS_TABLE_NAME": table_names.get("requests"),
        }

        # Store original values and set new ones from CloudFormation
        for env_var, table_name in env_mappings.items():
            if table_name:
                original_env[env_var] = os.environ.get(env_var)
                os.environ[env_var] = table_name
                print(f"🔧 Set {env_var}={table_name}")

        # Verify required tables are available
        required_tables = ["hotels", "requests"]
        missing_tables = [
            table for table in required_tables if not table_names.get(table)
        ]
        if missing_tables:
            pytest.skip(
                f"Required tables not found in CloudFormation outputs: {missing_tables}"
            )

        service = HotelService()

        yield service

        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is not None:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)
            print(f"🧹 Restored {env_var}")

    @pytest.fixture(scope="class")
    def verify_tables_exist(self, service):
        """Verify that the hotels and requests tables exist and are accessible."""
        try:
            # Try to scan both tables to verify they exist and are accessible
            service.hotels_table.scan(Limit=1)
            service.requests_table.scan(Limit=1)
            print("✅ Verified hotels and requests tables exist and are accessible")
            return True

        except Exception as e:
            pytest.skip(f"Could not access required tables: {e}")

    @pytest.fixture
    def cleanup_test_requests(self, service):
        """Clean up test housekeeping requests after each test."""
        created_request_ids = []

        def track_request(request_id):
            created_request_ids.append(request_id)

        yield track_request

        # Clean up created requests
        for request_id in created_request_ids:
            try:
                service.requests_table.delete_item(Key={"request_id": request_id})
                print(f"🧹 Cleaned up test request: {request_id}")
            except Exception as e:
                print(f"⚠️ Failed to clean up request {request_id}: {e}")

    def test_get_hotels_with_real_table(self, service, verify_tables_exist):
        """Test retrieving hotels from the real DynamoDB table."""
        result = service.get_hotels()

        # Verify result structure
        assert "hotels" in result
        assert "total_count" in result
        assert "limit_applied" in result

        # Verify we got some hotels (should have seed data)
        assert isinstance(result["hotels"], list)
        assert result["total_count"] >= 0
        assert result["limit_applied"] is False

        # If we have hotels, verify their structure
        if result["hotels"]:
            hotel = result["hotels"][0]
            assert "hotel_id" in hotel
            assert "name" in hotel
            print(f"✅ Found {result['total_count']} hotels in table")

            # Verify hotels are sorted by hotel_id
            hotel_ids = [h["hotel_id"] for h in result["hotels"]]
            assert hotel_ids == sorted(hotel_ids)

    def test_get_hotels_with_limit_real_table(self, service, verify_tables_exist):
        """Test retrieving hotels with limit from the real DynamoDB table."""
        # First get all hotels to know how many exist
        all_hotels = service.get_hotels()
        total_count = all_hotels["total_count"]

        if total_count > 0:
            # Test with limit smaller than total
            limit = min(2, total_count)
            result = service.get_hotels(limit=limit)

            assert len(result["hotels"]) <= limit
            assert result["limit_applied"] is True
            print(f"✅ Limited results to {len(result['hotels'])} hotels")

    def test_create_housekeeping_request_with_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test creating a housekeeping request in the real DynamoDB table."""
        # Create a request with unique test data
        test_timestamp = int(time.time())
        request_data = {
            "hotel_id": "H-TEST-001",
            "room_number": f"TEST-{test_timestamp}",
            "request_type": "cleaning",
            "description": f"Integration test request {test_timestamp}",
            "priority": "normal",
            "guest_name": f"Test Guest {test_timestamp}",
        }

        result = service.create_housekeeping_request(**request_data)

        # Track for cleanup
        cleanup_test_requests(result["request_id"])

        # Verify request was created successfully
        assert result["status"] == "pending"
        assert result["hotel_id"] == request_data["hotel_id"]
        assert result["room_number"] == request_data["room_number"]
        assert result["request_type"] == request_data["request_type"]
        assert result["description"] == request_data["description"]
        assert result["priority"] == request_data["priority"]
        assert result["guest_name"] == request_data["guest_name"]
        assert "request_id" in result
        assert result["request_id"].startswith("REQ-")
        assert "created_at" in result

        # Verify the request exists in DynamoDB
        stored_request = service.requests_table.get_item(
            Key={"request_id": result["request_id"]}
        )
        assert "Item" in stored_request
        assert stored_request["Item"]["hotel_id"] == request_data["hotel_id"]
        assert stored_request["Item"]["room_number"] == request_data["room_number"]

    def test_create_housekeeping_request_minimal_data_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test creating a housekeeping request with minimal data in the real DynamoDB table."""
        test_timestamp = int(time.time())
        request_data = {
            "hotel_id": "H-TEST-MINIMAL",
            "room_number": f"MIN-{test_timestamp}",
            "request_type": "maintenance",
        }

        result = service.create_housekeeping_request(**request_data)

        # Track for cleanup
        cleanup_test_requests(result["request_id"])

        # Verify request was created with defaults
        assert result["status"] == "pending"
        assert result["hotel_id"] == request_data["hotel_id"]
        assert result["room_number"] == request_data["room_number"]
        assert result["request_type"] == request_data["request_type"]
        assert result["description"] == ""  # Default empty string
        assert result["priority"] == "normal"  # Default priority
        assert result["guest_name"] is None  # Not provided

    def test_get_housekeeping_request_with_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test retrieving a housekeeping request from the real DynamoDB table."""
        # First create a request
        test_timestamp = int(time.time())
        request_data = {
            "hotel_id": "H-TEST-GET",
            "room_number": f"GET-{test_timestamp}",
            "request_type": "amenities",
            "description": f"Get test request {test_timestamp}",
            "priority": "high",
            "guest_name": f"Get Test Guest {test_timestamp}",
        }

        created_request = service.create_housekeeping_request(**request_data)
        request_id = created_request["request_id"]
        cleanup_test_requests(request_id)

        # Now retrieve the request
        retrieved_request = service.get_housekeeping_request(request_id)

        # Verify retrieved request matches created request
        assert retrieved_request is not None
        assert retrieved_request["request_id"] == request_id
        assert retrieved_request["hotel_id"] == request_data["hotel_id"]
        assert retrieved_request["room_number"] == request_data["room_number"]
        assert retrieved_request["request_type"] == request_data["request_type"]
        assert retrieved_request["description"] == request_data["description"]
        assert retrieved_request["priority"] == request_data["priority"]
        assert retrieved_request["guest_name"] == request_data["guest_name"]
        assert retrieved_request["status"] == "pending"

    def test_get_housekeeping_request_not_found_real_table(
        self, service, verify_tables_exist
    ):
        """Test retrieving a non-existent housekeeping request from the real DynamoDB table."""
        # Try to get a request that doesn't exist
        nonexistent_id = f"REQ-{int(time.time() * 1000)}999"
        result = service.get_housekeeping_request(nonexistent_id)

        # Verify None is returned for non-existent request
        assert result is None

    def test_get_housekeeping_requests_by_hotel_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test retrieving housekeeping requests by hotel ID from the real DynamoDB table."""
        # Create multiple requests for the same hotel
        test_timestamp = int(time.time())
        hotel_id = f"H-HOTEL-TEST-{test_timestamp}"

        requests_data = [
            {
                "hotel_id": hotel_id,
                "room_number": f"HOTEL-1-{test_timestamp}",
                "request_type": "cleaning",
                "description": f"Hotel test request 1 {test_timestamp}",
                "priority": "normal",
                "guest_name": f"Hotel Test Guest 1 {test_timestamp}",
            },
            {
                "hotel_id": hotel_id,
                "room_number": f"HOTEL-2-{test_timestamp}",
                "request_type": "maintenance",
                "description": f"Hotel test request 2 {test_timestamp}",
                "priority": "high",
                "guest_name": f"Hotel Test Guest 2 {test_timestamp}",
            },
        ]

        created_request_ids = []
        for request_data in requests_data:
            created_request = service.create_housekeeping_request(**request_data)
            created_request_ids.append(created_request["request_id"])
            cleanup_test_requests(created_request["request_id"])

        # Retrieve requests by hotel ID
        hotel_requests = service.get_housekeeping_requests_by_hotel(hotel_id)

        # Verify we got the expected requests
        assert len(hotel_requests) >= 2  # At least our test requests

        # Find our test requests in the results
        found_requests = [
            req for req in hotel_requests if req["request_id"] in created_request_ids
        ]
        assert len(found_requests) == 2

        # Verify request details
        for request in found_requests:
            assert request["hotel_id"] == hotel_id
            assert request["status"] == "pending"
            assert request["guest_name"].startswith("Hotel Test Guest")

        # Verify requests are sorted by created_at (most recent first)
        if len(hotel_requests) > 1:
            created_times = [req["created_at"] for req in hotel_requests]
            assert created_times == sorted(created_times, reverse=True)

    def test_get_housekeeping_requests_by_hotel_with_limit_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test retrieving housekeeping requests by hotel with limit from the real DynamoDB table."""
        # Create multiple requests for the same hotel
        test_timestamp = int(time.time())
        hotel_id = f"H-LIMIT-TEST-{test_timestamp}"

        # Create 3 requests
        for i in range(3):
            request_data = {
                "hotel_id": hotel_id,
                "room_number": f"LIMIT-{i}-{test_timestamp}",
                "request_type": "cleaning",
                "description": f"Limit test request {i} {test_timestamp}",
            }
            created_request = service.create_housekeeping_request(**request_data)
            cleanup_test_requests(created_request["request_id"])

        # Retrieve with limit
        limited_requests = service.get_housekeeping_requests_by_hotel(hotel_id, limit=2)

        # Should get at most 2 requests
        assert len(limited_requests) <= 2

        # All returned requests should be for the correct hotel
        for request in limited_requests:
            assert request["hotel_id"] == hotel_id

    def test_different_request_types_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test creating different types of housekeeping requests in the real DynamoDB table."""
        test_timestamp = int(time.time())
        request_types = ["cleaning", "maintenance", "amenities", "laundry", "other"]

        created_request_ids = []
        for i, request_type in enumerate(request_types):
            request_data = {
                "hotel_id": f"H-TYPE-TEST-{test_timestamp}",
                "room_number": f"TYPE-{i}-{test_timestamp}",
                "request_type": request_type,
                "description": f"Test {request_type} request {test_timestamp}",
            }

            created_request = service.create_housekeeping_request(**request_data)
            created_request_ids.append(created_request["request_id"])
            cleanup_test_requests(created_request["request_id"])

            # Verify request type was set correctly
            assert created_request["request_type"] == request_type

        # Verify all requests were created with unique IDs
        assert len(set(created_request_ids)) == len(request_types)

    def test_different_priority_levels_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test creating housekeeping requests with different priority levels in the real DynamoDB table."""
        test_timestamp = int(time.time())
        priorities = ["low", "normal", "high", "urgent"]

        created_request_ids = []
        for i, priority in enumerate(priorities):
            request_data = {
                "hotel_id": f"H-PRIORITY-TEST-{test_timestamp}",
                "room_number": f"PRIORITY-{i}-{test_timestamp}",
                "request_type": "cleaning",
                "description": f"Test {priority} priority request {test_timestamp}",
                "priority": priority,
            }

            created_request = service.create_housekeeping_request(**request_data)
            created_request_ids.append(created_request["request_id"])
            cleanup_test_requests(created_request["request_id"])

            # Verify priority was set correctly
            assert created_request["priority"] == priority

        # Verify all requests were created with unique IDs
        assert len(set(created_request_ids)) == len(priorities)

    def test_request_id_uniqueness_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test that request IDs are unique when creating multiple requests in the real DynamoDB table."""
        test_timestamp = int(time.time())
        base_request_data = {
            "hotel_id": f"H-UNIQUE-TEST-{test_timestamp}",
            "request_type": "cleaning",
            "description": f"Uniqueness test request {test_timestamp}",
        }

        created_request_ids = []

        # Create multiple requests quickly
        for i in range(5):
            request_data = base_request_data.copy()
            request_data["room_number"] = f"UNIQUE-{i}-{test_timestamp}"

            created_request = service.create_housekeeping_request(**request_data)
            created_request_ids.append(created_request["request_id"])
            cleanup_test_requests(created_request["request_id"])

            # Small delay to ensure different timestamps
            time.sleep(0.001)

        # Verify all request IDs are unique
        assert len(set(created_request_ids)) == 5

        # Verify all IDs follow the expected format
        for request_id in created_request_ids:
            assert request_id.startswith("REQ-")
            assert len(request_id) > 10  # Should have timestamp digits

    def test_complete_hotel_service_workflow_real_table(
        self, service, verify_tables_exist, cleanup_test_requests
    ):
        """Test complete hotel service workflow from listing hotels to creating requests using real DynamoDB table."""
        test_timestamp = int(time.time())

        # Step 1: List available hotels
        hotels_result = service.get_hotels()
        assert "hotels" in hotels_result
        assert "total_count" in hotels_result

        # Step 2: Create requests for different hotels (use test hotel IDs if no real ones)
        test_hotel_ids = ["H-WORKFLOW-TEST-1", "H-WORKFLOW-TEST-2"]
        if hotels_result["hotels"]:
            # Use real hotel IDs if available
            test_hotel_ids = [
                hotel["hotel_id"] for hotel in hotels_result["hotels"][:2]
            ]

        created_request_ids = []
        for i, hotel_id in enumerate(test_hotel_ids):
            request_data = {
                "hotel_id": hotel_id,
                "room_number": f"WORKFLOW-{i}-{test_timestamp}",
                "request_type": "cleaning",
                "description": f"Workflow test request {i} {test_timestamp}",
                "priority": "normal",
                "guest_name": f"Workflow Test Guest {i} {test_timestamp}",
            }

            created_request = service.create_housekeeping_request(**request_data)
            created_request_ids.append(created_request["request_id"])
            cleanup_test_requests(created_request["request_id"])

            # Verify request was created successfully
            assert created_request["hotel_id"] == hotel_id
            assert created_request["status"] == "pending"

        # Step 3: Retrieve requests by hotel
        for hotel_id in test_hotel_ids:
            hotel_requests = service.get_housekeeping_requests_by_hotel(hotel_id)

            # Find our test requests in the results
            found_requests = [
                req
                for req in hotel_requests
                if req["request_id"] in created_request_ids
            ]

            # Should find at least one request for this hotel
            assert len(found_requests) >= 1

        # Step 4: Retrieve individual requests
        for request_id in created_request_ids:
            retrieved_request = service.get_housekeeping_request(request_id)
            assert retrieved_request is not None
            assert retrieved_request["request_id"] == request_id
            assert retrieved_request["status"] == "pending"

    def test_service_initialization_with_environment_variables(self, table_names):
        """Test that service initializes correctly with environment variables."""
        # Test with custom environment variables
        custom_env = {
            "HOTELS_TABLE_NAME": table_names.get("hotels", "custom-hotels-table"),
            "REQUESTS_TABLE_NAME": table_names.get("requests", "custom-requests-table"),
        }

        original_env = {}
        for key, value in custom_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            service = HotelService()

            # Verify table names are set correctly
            assert service.hotels_table_name == custom_env["HOTELS_TABLE_NAME"]
            assert service.requests_table_name == custom_env["REQUESTS_TABLE_NAME"]

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                else:
                    os.environ.pop(key, None)

    def test_error_handling_with_invalid_table_access(self):
        """Test error handling when DynamoDB table access fails."""
        # Set invalid table names to trigger errors
        original_hotels_env = os.environ.get("HOTELS_TABLE_NAME")
        original_requests_env = os.environ.get("REQUESTS_TABLE_NAME")

        os.environ["HOTELS_TABLE_NAME"] = "nonexistent-hotels-table"
        os.environ["REQUESTS_TABLE_NAME"] = "nonexistent-requests-table"

        try:
            service = HotelService()

            # Test hotels table access error
            with pytest.raises(Exception) as exc_info:
                service.get_hotels()
            assert "Failed to retrieve hotels" in str(exc_info.value)

            # Test requests table access error
            with pytest.raises(Exception) as exc_info:
                service.create_housekeeping_request(
                    hotel_id="H-ERROR-TEST",
                    room_number="ERROR-ROOM",
                    request_type="cleaning",
                )
            assert "Failed to create housekeeping request" in str(exc_info.value)

        finally:
            # Restore original environment
            if original_hotels_env is not None:
                os.environ["HOTELS_TABLE_NAME"] = original_hotels_env
            else:
                os.environ.pop("HOTELS_TABLE_NAME", None)

            if original_requests_env is not None:
                os.environ["REQUESTS_TABLE_NAME"] = original_requests_env
            else:
                os.environ.pop("REQUESTS_TABLE_NAME", None)
