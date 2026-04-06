# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for simplified Hotel PMS tool interfaces using deployed DynamoDB tables."""

import os

import boto3
import pytest

from hotel_pms_simulation.tools.tools import HotelPMSTools


@pytest.mark.integration
class TestHotelPMSToolsIntegration:
    """Integration tests for HotelPMSTools using real DynamoDB tables."""

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
    def tools(self, table_names):
        """Create tools instance with CloudFormation-discovered table names."""
        # Set environment variables for the tools using CloudFormation outputs
        original_env = {}
        env_mappings = {
            "HOTELS_TABLE_NAME": table_names.get("hotels"),
            "ROOM_TYPES_TABLE_NAME": table_names.get("room_types"),
            "RATE_MODIFIERS_TABLE_NAME": table_names.get("rate_modifiers"),
            "RESERVATIONS_TABLE_NAME": table_names.get("reservations"),
            "REQUESTS_TABLE_NAME": table_names.get("requests"),
        }

        # Store original values and set new ones from CloudFormation
        for env_var, table_name in env_mappings.items():
            if table_name:
                original_env[env_var] = os.environ.get(env_var)
                os.environ[env_var] = table_name
                print(f"🔧 Set {env_var}={table_name}")

        # Verify required tables are available
        required_tables = ["hotels", "room_types", "reservations", "requests"]
        missing_tables = [
            table for table in required_tables if not table_names.get(table)
        ]
        if missing_tables:
            pytest.skip(
                f"Required tables not found in CloudFormation outputs: {missing_tables}"
            )

        tools = HotelPMSTools()

        yield tools

        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is not None:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)

    @pytest.fixture
    def test_hotel_id(self, tools):
        """Get a test hotel ID from the deployed hotels table."""
        result = tools.get_hotels(limit=1)
        if result.get("error") or not result.get("hotels"):
            pytest.skip("No hotels found in deployed table")
        return result["hotels"][0]["hotel_id"]

    @pytest.fixture
    def test_room_type_id(self, tools, test_hotel_id):
        """Get a test room type ID for the test hotel."""
        # Use the availability service to get room types for the hotel
        availability_result = tools.check_availability(
            hotel_id=test_hotel_id,
            check_in_date="2024-04-15",  # Use a date that should be available
            check_out_date="2024-04-17",
            guests=2,
        )

        if availability_result.get("error") or not availability_result.get(
            "available_room_types"
        ):
            pytest.skip("No room types found for test hotel")

        return availability_result["available_room_types"][0]["room_type_id"]

    def test_get_hotels_integration(self, tools):
        """Test get_hotels tool with real DynamoDB data."""
        print("\n🧪 Testing get_hotels tool integration...")

        result = tools.get_hotels()

        # Verify successful response
        assert "error" not in result or result.get("error") is False
        assert "hotels" in result
        assert "total_count" in result
        assert isinstance(result["hotels"], list)
        assert isinstance(result["total_count"], int)
        assert result["total_count"] >= 0

        if result["hotels"]:
            # Verify hotel structure
            hotel = result["hotels"][0]
            assert "hotel_id" in hotel
            assert "name" in hotel
            print(f"✅ Found {result['total_count']} hotels, first: {hotel['name']}")
        else:
            print("⚠️ No hotels found in table")

    def test_get_hotels_with_limit_integration(self, tools):
        """Test get_hotels tool with limit parameter."""
        print("\n🧪 Testing get_hotels tool with limit...")

        result = tools.get_hotels(limit=2)

        assert "error" not in result or result.get("error") is False
        assert "hotels" in result
        assert len(result["hotels"]) <= 2
        print(f"✅ Limited results to {len(result['hotels'])} hotels")

    def test_check_availability_integration(self, tools, test_hotel_id):
        """Test check_availability tool with real hotel data."""
        print(f"\n🧪 Testing check_availability tool with hotel {test_hotel_id}...")

        result = tools.check_availability(
            hotel_id=test_hotel_id,
            check_in_date="2024-04-15",  # Use a date that should be available
            check_out_date="2024-04-17",
            guests=2,
        )

        # Verify successful response
        assert "error" not in result or result.get("error") is False
        assert result["hotel_id"] == test_hotel_id
        assert result["check_in_date"] == "2024-04-15"
        assert result["check_out_date"] == "2024-04-17"
        assert result["guests"] == 2
        assert "available_room_types" in result
        assert isinstance(result["available_room_types"], list)

        if result["available_room_types"]:
            room_type = result["available_room_types"][0]
            assert "room_type_id" in room_type
            assert "available_rooms" in room_type
            assert "base_rate" in room_type
            print(
                f"✅ Found {len(result['available_room_types'])} available room types"
            )
        else:
            print("⚠️ No available room types found")

    def test_check_availability_blackout_dates_integration(self, tools, test_hotel_id):
        """Test check_availability tool with blackout dates (5th-7th of month)."""
        print("\n🧪 Testing check_availability tool with blackout dates...")

        result = tools.check_availability(
            hotel_id=test_hotel_id,
            check_in_date="2024-04-05",  # 5th of month - blackout date
            check_out_date="2024-04-07",
            guests=2,
        )

        # Should return unavailable due to blackout dates
        assert result.get("error") is True or "message" in result
        print("✅ Blackout date logic working correctly")

    def test_generate_quote_integration(self, tools, test_hotel_id, test_room_type_id):
        """Test generate_quote tool with real hotel and room type data."""
        print(
            f"\n🧪 Testing generate_quote tool with hotel {test_hotel_id}, room type {test_room_type_id}..."
        )

        result = tools.generate_quote(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
        )

        # Verify successful response
        assert "error" not in result or result.get("error") is False
        assert result["hotel_id"] == test_hotel_id
        assert result["room_type_id"] == test_room_type_id
        assert result["nights"] == 2
        assert "base_rate" in result
        assert "total_cost" in result
        assert isinstance(result["base_rate"], int | float)
        assert isinstance(result["total_cost"], int | float)
        assert result["total_cost"] > 0

        print(
            f"✅ Generated quote: ${result['total_cost']} for {result['nights']} nights"
        )

    def test_generate_quote_detailed_package_integration(
        self, tools, test_hotel_id, test_room_type_id
    ):
        """Test generate_quote tool with detailed package type."""
        print("\n🧪 Testing generate_quote tool with detailed package...")

        result = tools.generate_quote(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
            package_type="detailed",
        )

        # Verify successful response with detailed breakdown
        assert "error" not in result or result.get("error") is False
        assert "pricing_breakdown" in result
        assert "guest_multiplier" in result

        print("✅ Detailed pricing breakdown included")

    def test_create_and_manage_reservation_integration(
        self, tools, test_hotel_id, test_room_type_id
    ):
        """Test complete reservation lifecycle: create, get, update, checkout."""
        print("\n🧪 Testing reservation lifecycle integration...")

        # Create reservation
        create_result = tools.create_reservation(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            guest_name="Integration Test Guest",
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
            guest_email="test@example.com",
            guest_phone="555-0123",
        )

        assert "error" not in create_result or create_result.get("error") is False
        assert "reservation_id" in create_result
        assert create_result["status"] == "confirmed"
        reservation_id = create_result["reservation_id"]
        print(f"✅ Created reservation: {reservation_id}")

        # Get reservation by ID
        get_result = tools.get_reservation(reservation_id)
        assert "error" not in get_result or get_result.get("error") is False
        assert get_result["reservation_id"] == reservation_id
        assert get_result["guest_name"] == "Integration Test Guest"
        print(f"✅ Retrieved reservation: {reservation_id}")

        # Get reservations by hotel
        hotel_reservations = tools.get_reservations(hotel_id=test_hotel_id)
        assert (
            "error" not in hotel_reservations
            or hotel_reservations.get("error") is False
        )
        assert "reservations" in hotel_reservations
        assert hotel_reservations["total_count"] >= 1
        print(f"✅ Found {hotel_reservations['total_count']} reservations for hotel")

        # Get reservations by guest email
        guest_reservations = tools.get_reservations(guest_email="test@example.com")
        assert (
            "error" not in guest_reservations
            or guest_reservations.get("error") is False
        )
        assert guest_reservations["total_count"] >= 1
        print(f"✅ Found {guest_reservations['total_count']} reservations for guest")

        # Update reservation
        update_result = tools.update_reservation(
            reservation_id=reservation_id,
            guest_name="Updated Integration Test Guest",
            status="checked_in",
        )
        assert "error" not in update_result or update_result.get("error") is False
        assert update_result["guest_name"] == "Updated Integration Test Guest"
        assert update_result["status"] == "checked_in"
        print(f"✅ Updated reservation: {reservation_id}")

        # Checkout guest
        checkout_result = tools.checkout_guest(
            reservation_id=reservation_id,
            additional_charges=25.50,
            payment_method="card",
        )
        assert "error" not in checkout_result or checkout_result.get("error") is False
        assert checkout_result["status"] == "checked_out"
        assert checkout_result["payment_method"] == "card"
        print(f"✅ Checked out guest: {reservation_id}")

    def test_create_housekeeping_request_integration(self, tools, test_hotel_id):
        """Test create_housekeeping_request tool with real DynamoDB persistence."""
        print("\n🧪 Testing create_housekeeping_request tool integration...")

        result = tools.create_housekeeping_request(
            hotel_id=test_hotel_id,
            room_number="101",
            guest_name="Integration Test Guest",
            request_type="cleaning",
            description="Need fresh towels and room cleaning",
        )

        # Verify successful response
        assert "error" not in result or result.get("error") is False
        assert "request_id" in result
        assert result["hotel_id"] == test_hotel_id
        assert result["room_number"] == "101"
        assert result["request_type"] == "cleaning"
        assert result["status"] == "pending"
        assert result["guest_name"] == "Integration Test Guest"

        print(f"✅ Created housekeeping request: {result['request_id']}")

    def test_error_handling_integration(self, tools):
        """Test error handling with real AWS service failures."""
        print("\n🧪 Testing error handling integration...")

        # Test with invalid hotel ID
        result = tools.check_availability(
            hotel_id="INVALID-HOTEL-ID",
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
        )

        # Should handle gracefully - either return error or empty results
        if result.get("error"):
            assert "error_code" in result
            assert "message" in result
            print("✅ Invalid hotel ID handled with error response")
        else:
            # Service might return empty results instead of error
            assert "available_room_types" in result
            print("✅ Invalid hotel ID handled with empty results")

        # Test with invalid reservation ID
        get_result = tools.get_reservation("INVALID-RESERVATION-ID")
        assert get_result.get("error") is True
        assert get_result.get("error_code") == "NOT_FOUND"
        print("✅ Invalid reservation ID handled correctly")

    def test_validation_with_real_services_integration(self, tools):
        """Test input validation with real service integration."""
        print("\n🧪 Testing validation with real services...")

        # Test invalid date format
        result = tools.check_availability(
            hotel_id="H-TEST-001",
            check_in_date="invalid-date",
            check_out_date="2024-04-17",
            guests=2,
        )
        assert result.get("error") is True
        assert result.get("error_code") == "VALIDATION_ERROR"
        print("✅ Date validation working correctly")

        # Test invalid guests count
        result = tools.generate_quote(
            hotel_id="H-TEST-001",
            room_type_id="RT-TEST",
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=0,
        )
        assert result.get("error") is True
        assert result.get("error_code") == "VALIDATION_ERROR"
        print("✅ Guest count validation working correctly")

        # Test empty required fields
        result = tools.create_reservation(
            guest_name="Test Guest",
            guest_email="test@example.com",
            hotel_id="",
            room_type_id="RT-TEST",
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
        )
        assert result.get("error") is True
        assert result.get("error_code") == "VALIDATION_ERROR"
        print("✅ Required field validation working correctly")

    def test_quote_based_reservation_workflow_integration(
        self, tools, test_hotel_id, test_room_type_id
    ):
        """Test complete quote-based reservation workflow with real DynamoDB."""
        print("\n🧪 Testing quote-based reservation workflow integration...")

        # Step 1: Check availability
        print("Step 1: Checking availability...")
        availability_result = tools.check_availability(
            hotel_id=test_hotel_id,
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
        )
        assert not availability_result.get("error")
        assert availability_result.get("available_room_types")
        print(
            f"✅ Found {len(availability_result['available_room_types'])} available room types"
        )

        # Step 2: Generate quote
        print("Step 2: Generating quote...")
        quote_result = tools.generate_quote(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            check_in_date="2024-04-15",
            check_out_date="2024-04-17",
            guests=2,
        )
        assert not quote_result.get("error")
        assert "quote_id" in quote_result
        assert "expires_at" in quote_result
        assert "total_cost" in quote_result
        quote_id = quote_result["quote_id"]
        print(f"✅ Generated quote: {quote_id} (expires: {quote_result['expires_at']})")
        print(f"   Total cost: ${quote_result['total_cost']}")

        # Step 3: Create reservation using quote_id
        print("Step 3: Creating reservation with quote_id...")
        reservation_result = tools.create_reservation(
            quote_id=quote_id,
            guest_name="Integration Test Guest",
            guest_email="integration.test@example.com",
            guest_phone="+1-555-TEST-001",
        )
        assert not reservation_result.get("error")
        assert "reservation_id" in reservation_result
        assert reservation_result["status"] == "confirmed"
        assert reservation_result["hotel_id"] == test_hotel_id
        assert reservation_result["room_type_id"] == test_room_type_id
        assert reservation_result["check_in_date"] == "2024-04-15"
        assert reservation_result["check_out_date"] == "2024-04-17"
        assert reservation_result["guests"] == 2
        reservation_id = reservation_result["reservation_id"]
        print(f"✅ Created reservation: {reservation_id}")

        # Step 4: Verify reservation was created
        print("Step 4: Verifying reservation...")
        get_result = tools.get_reservation(reservation_id)
        assert not get_result.get("error")
        assert get_result["reservation_id"] == reservation_id
        assert get_result["guest_name"] == "Integration Test Guest"
        assert get_result["guest_email"] == "integration.test@example.com"
        print(f"✅ Verified reservation: {reservation_id}")

        # Step 5: Test error handling - invalid quote_id
        print("Step 5: Testing error handling with invalid quote_id...")
        error_result = tools.create_reservation(
            quote_id="Q-INVALID-QUOTE",
            guest_name="Test Guest",
            guest_email="test@example.com",
        )
        assert error_result.get("error") is True
        assert error_result.get("error_code") == "QUOTE_NOT_FOUND"
        print("✅ Invalid quote_id handled correctly")

        # Step 6: Cleanup - checkout the guest
        print("Step 6: Cleaning up - checking out guest...")
        checkout_result = tools.checkout_guest(
            reservation_id=reservation_id,
            additional_charges=50.0,
        )
        assert not checkout_result.get("error")
        assert checkout_result["status"] == "checked_out"
        print(f"✅ Checked out guest: {reservation_id}")

        print("\n✅ Complete quote-based reservation workflow test passed!")

    def test_quote_based_vs_traditional_reservation_integration(
        self, tools, test_hotel_id, test_room_type_id
    ):
        """Test that both quote-based and traditional reservation methods work."""
        print("\n🧪 Testing quote-based vs traditional reservation methods...")

        # Method 1: Traditional reservation (direct parameters)
        print("Method 1: Creating reservation with direct parameters...")
        traditional_result = tools.create_reservation(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            guest_name="Traditional Guest",
            guest_email="traditional@example.com",
            check_in_date="2024-05-15",
            check_out_date="2024-05-17",
            guests=2,
        )
        assert not traditional_result.get("error")
        assert traditional_result["status"] == "confirmed"
        traditional_reservation_id = traditional_result["reservation_id"]
        print(f"✅ Traditional reservation created: {traditional_reservation_id}")

        # Method 2: Quote-based reservation
        print("Method 2: Creating reservation with quote_id...")
        quote_result = tools.generate_quote(
            hotel_id=test_hotel_id,
            room_type_id=test_room_type_id,
            check_in_date="2024-05-20",
            check_out_date="2024-05-22",
            guests=2,
        )
        assert not quote_result.get("error")
        quote_id = quote_result["quote_id"]

        quote_based_result = tools.create_reservation(
            quote_id=quote_id,
            guest_name="Quote-Based Guest",
            guest_email="quotebased@example.com",
        )
        assert not quote_based_result.get("error")
        assert quote_based_result["status"] == "confirmed"
        quote_based_reservation_id = quote_based_result["reservation_id"]
        print(f"✅ Quote-based reservation created: {quote_based_reservation_id}")

        # Verify both reservations exist
        traditional_verify = tools.get_reservation(traditional_reservation_id)
        quote_based_verify = tools.get_reservation(quote_based_reservation_id)

        assert not traditional_verify.get("error")
        assert not quote_based_verify.get("error")
        print("✅ Both reservation methods work correctly")

        # Cleanup
        tools.checkout_guest(traditional_reservation_id)
        tools.checkout_guest(quote_based_reservation_id)
        print("✅ Cleaned up test reservations")
