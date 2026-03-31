# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for simplified availability service using deployed DynamoDB tables."""

import os

import boto3
import pytest

from hotel_pms_simulation.services.availability_service import (
    AvailabilityService,
)


@pytest.mark.integration
class TestAvailabilityServiceIntegration:
    """Integration tests for AvailabilityService using real DynamoDB tables."""

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
            "QuotesTableName": "quotes",
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
            "ROOM_TYPES_TABLE_NAME": table_names.get("room_types"),
            "RATE_MODIFIERS_TABLE_NAME": table_names.get("rate_modifiers"),
            "RESERVATIONS_TABLE_NAME": table_names.get("reservations"),
            "REQUESTS_TABLE_NAME": table_names.get("requests"),
            "QUOTES_TABLE_NAME": table_names.get("quotes"),
        }

        # Store original values and set new ones from CloudFormation
        for env_var, table_name in env_mappings.items():
            if table_name:
                original_env[env_var] = os.environ.get(env_var)
                os.environ[env_var] = table_name
                print(f"🔧 Set {env_var}={table_name}")

        # Verify required tables are available
        required_tables = ["hotels", "room_types"]
        missing_tables = [
            table for table in required_tables if not table_names.get(table)
        ]
        if missing_tables:
            pytest.skip(
                f"Required tables not found in CloudFormation outputs: {missing_tables}"
            )

        service = AvailabilityService()

        yield service

        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is not None:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)
            print(f"🧹 Restored {env_var}")

    @pytest.fixture(scope="class")
    def verify_data_exists(self, service):
        """Verify that test data exists in the deployed tables."""
        try:
            # Check if hotels exist
            hotels_response = service.hotels_table.scan(Limit=1)
            if not hotels_response.get("Items"):
                pytest.skip("No hotels found in deployed DynamoDB table")

            # Check if room types exist
            room_types_response = service.room_types_table.scan(Limit=1)
            if not room_types_response.get("Items"):
                pytest.skip("No room types found in deployed DynamoDB table")

            print("✅ Verified test data exists in deployed tables")
            return True

        except Exception as e:
            pytest.skip(f"Could not verify test data in deployed tables: {e}")

    def test_check_availability_with_real_data_available_dates(
        self, service, verify_data_exists
    ):
        """Test availability check with real hotel data for available dates."""
        # Use a real hotel ID from the CSV data
        hotel_id = "H-PVR-002"  # Paraíso Vallarta Resort & Spa

        # Use dates that are not blackout dates (avoid 5th-7th of month)
        check_in_date = "2024-03-15"
        check_out_date = "2024-03-17"
        guests = 2

        result = service.check_availability(
            hotel_id=hotel_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        # Verify successful availability check
        assert result["available"] is True
        assert result["hotel_id"] == hotel_id
        assert "available_room_types" in result
        assert len(result["available_room_types"]) > 0

        # Verify room type structure
        for room_type in result["available_room_types"]:
            assert "room_type_id" in room_type
            assert "available_rooms" in room_type
            assert "base_rate" in room_type
            assert room_type["available_rooms"] > 0
            assert room_type["base_rate"] > 0

    def test_check_availability_with_real_data_blackout_dates(
        self, service, verify_data_exists
    ):
        """Test availability check with real hotel data for blackout dates."""
        # Use a real hotel ID from the CSV data
        hotel_id = "H-GPR-001"  # Grand Paraíso Resort & Spa

        # Use dates that include blackout dates (5th-7th of month)
        check_in_date = "2024-03-05"
        check_out_date = "2024-03-07"
        guests = 2

        result = service.check_availability(
            hotel_id=hotel_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        # Verify blackout date handling
        assert result["available"] is False
        assert result["hotel_id"] == hotel_id
        assert "Fully booked" in result["message"]

    def test_check_availability_nonexistent_hotel(self, service, verify_data_exists):
        """Test availability check with nonexistent hotel ID."""
        result = service.check_availability(
            hotel_id="NONEXISTENT-HOTEL",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error handling
        assert result["available"] is False
        assert "not found" in result["message"]

    def test_check_availability_different_guest_counts(
        self, service, verify_data_exists
    ):
        """Test availability check with different guest counts using real data."""
        hotel_id = "H-PTL-003"  # Paraíso Tulum Eco-Luxury Resort
        check_in_date = "2024-03-20"
        check_out_date = "2024-03-22"

        # Test with 2 guests (should get most room types)
        result_2_guests = service.check_availability(
            hotel_id=hotel_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=2,
        )

        # Test with 6 guests (should get fewer room types)
        result_6_guests = service.check_availability(
            hotel_id=hotel_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=6,
        )

        # Verify both are available but 6 guests has fewer options
        assert result_2_guests["available"] is True
        assert result_6_guests["available"] is True

        # Should have fewer room types available for 6 guests
        assert len(result_6_guests["available_room_types"]) <= len(
            result_2_guests["available_room_types"]
        )

    def test_generate_quote_with_real_data(self, service, verify_data_exists):
        """Test quote generation with real hotel and room type data."""
        # Use real hotel and room type IDs from CSV data
        hotel_id = "H-PVR-002"  # Paraíso Vallarta Resort & Spa
        room_type_id = "JSVG-PVR"  # Junior Suite Vista Jardín

        check_in_date = "2024-03-15"
        check_out_date = "2024-03-18"  # 3 nights
        guests = 2

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        # Verify quote structure
        assert "error" not in result
        assert result["hotel_id"] == hotel_id
        assert result["room_type_id"] == room_type_id
        assert result["nights"] == 3
        assert result["guests"] == guests
        assert result["guest_multiplier"] == 1.0  # No extra charge for 2 guests

        # Verify pricing calculations
        assert result["base_rate"] > 0
        assert result["total_cost"] == result["base_rate"] * 3 * 1.0

        # Verify pricing breakdown
        breakdown = result["pricing_breakdown"]
        assert breakdown["base_rate_per_night"] == result["base_rate"]
        assert breakdown["nights"] == 3
        assert breakdown["guest_multiplier"] == 1.0
        assert breakdown["subtotal"] == result["base_rate"] * 3
        assert breakdown["total_with_guest_adjustment"] == result["total_cost"]

    def test_generate_quote_with_guest_multiplier_real_data(
        self, service, verify_data_exists
    ):
        """Test quote generation with guest multiplier using real data."""
        # Use a room type that can accommodate more guests
        hotel_id = "H-GPR-001"  # Grand Paraíso Resort & Spa
        room_type_id = "FAMS-GPR"  # Family Suite (2 Habitaciones) - max 6 guests

        check_in_date = "2024-03-20"
        check_out_date = "2024-03-22"  # 2 nights
        guests = 4  # 2 additional guests beyond base 2

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        # Verify guest multiplier calculation
        assert result["guests"] == 4
        assert result["guest_multiplier"] == 1.5  # 1.0 + (2 * 0.25)
        assert result["nights"] == 2

        # Verify total cost includes guest multiplier
        expected_total = result["base_rate"] * 2 * 1.5
        assert result["total_cost"] == expected_total

    def test_generate_quote_wrong_hotel_real_data(self, service, verify_data_exists):
        """Test quote generation with room type from wrong hotel."""
        # Use room type from one hotel with different hotel ID
        hotel_id = "H-PVR-002"  # Paraíso Vallarta Resort & Spa
        room_type_id = "JVIL-PTL"  # Jungle Villa (belongs to H-PTL-003)

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error handling
        assert result["error"] is True
        assert "does not belong to the specified hotel" in result["message"]

    def test_generate_quote_nonexistent_room_type(self, service, verify_data_exists):
        """Test quote generation with nonexistent room type."""
        hotel_id = "H-PVR-002"
        room_type_id = "NONEXISTENT-ROOM"

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error handling
        assert result["error"] is True
        assert "not found" in result["message"]

    def test_blackout_date_detection_across_months(self, service, verify_data_exists):
        """Test blackout date detection across different months."""
        hotel_id = "H-PLC-004"  # Paraíso Los Cabos Desert & Ocean Resort
        guests = 2

        # Test different months with blackout dates
        blackout_test_cases = [
            ("2024-01-05", "2024-01-07"),  # January 5th-7th
            ("2024-02-06", "2024-02-08"),  # February 6th-8th
            ("2024-12-07", "2024-12-09"),  # December 7th-9th
        ]

        for check_in, check_out in blackout_test_cases:
            result = service.check_availability(
                hotel_id=hotel_id,
                check_in_date=check_in,
                check_out_date=check_out,
                guests=guests,
            )

            assert result["available"] is False
            assert "Fully booked" in result["message"]

    def test_availability_with_all_hotels(self, service, verify_data_exists):
        """Test availability check with all hotels from real data."""
        # Test with all hotel IDs from the CSV data
        hotel_ids = ["H-GPR-001", "H-PVR-002", "H-PTL-003", "H-PLC-004"]

        check_in_date = "2024-03-20"  # Not a blackout date
        check_out_date = "2024-03-22"
        guests = 2

        for hotel_id in hotel_ids:
            result = service.check_availability(
                hotel_id=hotel_id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                guests=guests,
            )

            # All hotels should be available for non-blackout dates
            assert result["available"] is True
            assert result["hotel_id"] == hotel_id
            assert len(result["available_room_types"]) > 0

    def test_demo_availability_counts_by_room_type(self, service, verify_data_exists):
        """Test that demo availability counts work correctly with real room types."""
        hotel_id = "H-PVR-002"
        check_in_date = "2024-03-15"
        check_out_date = "2024-03-17"
        guests = 2

        result = service.check_availability(
            hotel_id=hotel_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        assert result["available"] is True

        # Verify availability counts are reasonable (demo logic)
        for room_type in result["available_room_types"]:
            room_type_id = room_type["room_type_id"]
            available_count = room_type["available_rooms"]

            # Verify counts are positive and reasonable
            assert available_count > 0
            assert available_count <= 10  # Demo logic caps at reasonable numbers

            # Verify different room types get different counts based on naming
            if "JSV" in room_type_id:  # Junior Suites
                assert available_count in [2, 3, 5]  # Expected demo values
            elif "FAM" in room_type_id:  # Family suites
                assert available_count in [2, 3, 5]
            elif "PRES" in room_type_id:  # Presidential suites
                assert available_count in [1, 2]  # Should be limited

    def test_pricing_with_real_rates(self, service, verify_data_exists):
        """Test that pricing uses real base rates from DynamoDB."""
        # Test with a known room type and verify the rate matches CSV data
        hotel_id = "H-GPR-001"
        room_type_id = (
            "JSVG-GPR"  # Junior Suite Vista Jardín - base_rate: 8500 from CSV
        )

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date="2024-03-15",
            check_out_date="2024-03-16",  # 1 night
            guests=2,
        )

        # Verify the base rate matches the expected value from CSV
        # Note: The actual value might be stored as Decimal in DynamoDB
        assert result["base_rate"] == 8500.0  # From CSV data
        assert result["total_cost"] == 8500.0  # 1 night, 2 guests (no multiplier)

    def test_service_initialization_with_environment_variables(self, table_names):
        """Test that service initializes correctly with environment variables."""
        # Test with custom environment variables
        custom_env = {
            "HOTELS_TABLE_NAME": table_names.get("hotels", "custom-hotels-table"),
            "ROOM_TYPES_TABLE_NAME": table_names.get(
                "room_types", "custom-room-types-table"
            ),
            "QUOTES_TABLE_NAME": table_names.get("quotes", "custom-quotes-table"),
        }

        original_env = {}
        for key, value in custom_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            service = AvailabilityService()

            # Verify table names are set correctly
            assert service.hotels_table_name == custom_env["HOTELS_TABLE_NAME"]
            assert service.room_types_table_name == custom_env["ROOM_TYPES_TABLE_NAME"]
            assert service.quotes_table_name == custom_env["QUOTES_TABLE_NAME"]

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                else:
                    os.environ.pop(key, None)

    def test_generate_quote_with_dynamodb_storage(self, service, verify_data_exists):
        """Test quote generation stores data in DynamoDB and returns quote_id."""
        hotel_id = "H-PVR-002"  # Paraíso Vallarta Resort & Spa
        room_type_id = "JSVG-PVR"  # Junior Suite Vista Jardín

        check_in_date = "2024-03-15"
        check_out_date = "2024-03-18"  # 3 nights
        guests = 2

        result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
        )

        # Verify quote structure includes quote_id and expires_at
        assert "error" not in result
        assert "quote_id" in result
        assert "expires_at" in result
        assert result["quote_id"].startswith("Q-")
        assert len(result["quote_id"]) > 10  # Should have date and UUID

        # Verify quote data is still present
        assert result["hotel_id"] == hotel_id
        assert result["room_type_id"] == room_type_id
        assert result["nights"] == 3
        assert result["guests"] == guests

        # Verify the quote was stored in DynamoDB by retrieving it
        stored_quote = service.get_quote(result["quote_id"])
        assert stored_quote is not None
        assert stored_quote["quote_id"] == result["quote_id"]
        assert stored_quote["hotel_id"] == hotel_id
        assert stored_quote["total_cost"] == result["total_cost"]

    def test_get_quote_retrieval(self, service, verify_data_exists):
        """Test quote retrieval by quote_id."""
        # First generate a quote
        hotel_id = "H-GPR-001"
        room_type_id = "JSVG-GPR"

        quote_result = service.generate_quote(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in_date="2024-03-20",
            check_out_date="2024-03-22",
            guests=2,
        )

        quote_id = quote_result["quote_id"]

        # Test retrieving the quote
        retrieved_quote = service.get_quote(quote_id)

        assert retrieved_quote is not None
        assert retrieved_quote["quote_id"] == quote_id
        assert retrieved_quote["hotel_id"] == hotel_id
        assert retrieved_quote["room_type_id"] == room_type_id
        assert retrieved_quote["check_in_date"] == "2024-03-20"
        assert retrieved_quote["check_out_date"] == "2024-03-22"
        assert retrieved_quote["guests"] == 2
        assert "expires_at" in retrieved_quote
        assert "created_at" in retrieved_quote

    def test_get_quote_nonexistent(self, service, verify_data_exists):
        """Test retrieving a nonexistent quote returns None."""
        nonexistent_quote_id = "Q-20240101-NONEXIST"

        result = service.get_quote(nonexistent_quote_id)

        assert result is None

    def test_quote_unique_ids(self, service, verify_data_exists):
        """Test that multiple quotes generate unique IDs."""
        hotel_id = "H-PTL-003"
        room_type_id = "JVIL-PTL"

        # Generate multiple quotes
        quote_ids = []
        for _i in range(3):
            result = service.generate_quote(
                hotel_id=hotel_id,
                room_type_id=room_type_id,
                check_in_date="2024-03-25",
                check_out_date="2024-03-27",
                guests=2,
            )
            assert "quote_id" in result
            quote_ids.append(result["quote_id"])

        # Verify all quote IDs are unique
        assert len(set(quote_ids)) == 3

        # Verify all quotes can be retrieved
        for quote_id in quote_ids:
            retrieved_quote = service.get_quote(quote_id)
            assert retrieved_quote is not None
            assert retrieved_quote["quote_id"] == quote_id
