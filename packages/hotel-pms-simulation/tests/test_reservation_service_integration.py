# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for simplified reservation service using deployed DynamoDB tables."""

import os
import time
from datetime import datetime

import boto3
import pytest

from hotel_pms_simulation.services.reservation_service import (
    ReservationService,
)


@pytest.mark.integration
class TestReservationServiceIntegration:
    """Integration tests for ReservationService using real DynamoDB tables."""

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
        required_tables = ["reservations"]
        missing_tables = [
            table for table in required_tables if not table_names.get(table)
        ]
        if missing_tables:
            pytest.skip(
                f"Required tables not found in CloudFormation outputs: {missing_tables}"
            )

        service = ReservationService()

        yield service

        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is not None:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)
            print(f"🧹 Restored {env_var}")

    @pytest.fixture(scope="class")
    def verify_table_exists(self, service):
        """Verify that the reservations table exists and is accessible."""
        try:
            # Try to scan the table to verify it exists and is accessible
            service.reservations_table.scan(Limit=1)
            print("✅ Verified reservations table exists and is accessible")
            return True

        except Exception as e:
            pytest.skip(f"Could not access reservations table: {e}")

    @pytest.fixture
    def cleanup_test_reservations(self, service):
        """Clean up test reservations after each test."""
        created_reservation_ids = []

        def track_reservation(reservation_id):
            created_reservation_ids.append(reservation_id)

        yield track_reservation

        # Clean up created reservations
        for reservation_id in created_reservation_ids:
            try:
                service.reservations_table.delete_item(
                    Key={"reservation_id": reservation_id}
                )
                print(f"🧹 Cleaned up test reservation: {reservation_id}")
            except Exception as e:
                print(f"⚠️ Failed to clean up reservation {reservation_id}: {e}")

    def test_create_reservation_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test creating a reservation in the real DynamoDB table."""
        # Create a reservation with unique test data
        test_timestamp = int(time.time())
        reservation_data = {
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-TEST",
            "guest_name": f"Integration Test Guest {test_timestamp}",
            "guest_email": f"test{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-06-15",
            "check_out_date": "2024-06-17",
            "guests": 2,
            "package_type": "breakfast",
        }

        result = service.create_reservation(**reservation_data)

        # Track for cleanup
        cleanup_test_reservations(result["reservation_id"])

        # Verify reservation was created successfully
        assert result["status"] == "confirmed"
        assert result["guest_name"] == reservation_data["guest_name"]
        assert result["guest_email"] == reservation_data["guest_email"]
        assert result["hotel_id"] == reservation_data["hotel_id"]
        assert result["room_type_id"] == reservation_data["room_type_id"]
        assert result["check_in_date"] == reservation_data["check_in_date"]
        assert result["check_out_date"] == reservation_data["check_out_date"]
        assert result["guests"] == reservation_data["guests"]
        assert result["package_type"] == reservation_data["package_type"]
        assert "reservation_id" in result
        assert result["reservation_id"].startswith("CONF-")
        assert "created_at" in result

        # Verify the reservation exists in DynamoDB
        stored_reservation = service.reservations_table.get_item(
            Key={"reservation_id": result["reservation_id"]}
        )
        assert "Item" in stored_reservation
        assert (
            stored_reservation["Item"]["guest_name"] == reservation_data["guest_name"]
        )

    def test_get_reservation_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test retrieving a reservation from the real DynamoDB table."""
        # First create a reservation
        test_timestamp = int(time.time())
        reservation_data = {
            "hotel_id": "H-TEST-002",
            "room_type_id": "RT-TEST",
            "guest_name": f"Get Test Guest {test_timestamp}",
            "guest_email": f"gettest{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-06-20",
            "check_out_date": "2024-06-22",
            "guests": 3,
            "package_type": "all_inclusive",
        }

        created_reservation = service.create_reservation(**reservation_data)
        reservation_id = created_reservation["reservation_id"]
        cleanup_test_reservations(reservation_id)

        # Now retrieve the reservation
        retrieved_reservation = service.get_reservation(reservation_id)

        # Verify retrieved reservation matches created reservation
        assert retrieved_reservation is not None
        assert retrieved_reservation["reservation_id"] == reservation_id
        assert retrieved_reservation["guest_name"] == reservation_data["guest_name"]
        assert retrieved_reservation["guest_email"] == reservation_data["guest_email"]
        assert retrieved_reservation["hotel_id"] == reservation_data["hotel_id"]
        assert retrieved_reservation["room_type_id"] == reservation_data["room_type_id"]
        assert (
            retrieved_reservation["check_in_date"] == reservation_data["check_in_date"]
        )
        assert (
            retrieved_reservation["check_out_date"]
            == reservation_data["check_out_date"]
        )
        assert retrieved_reservation["guests"] == reservation_data["guests"]
        assert retrieved_reservation["package_type"] == reservation_data["package_type"]
        assert retrieved_reservation["status"] == "confirmed"

    def test_get_reservation_not_found_with_real_table(
        self, service, verify_table_exists
    ):
        """Test retrieving a non-existent reservation from the real DynamoDB table."""
        # Try to get a reservation that doesn't exist
        nonexistent_id = f"CONF-{int(time.time() * 1000)}999"
        result = service.get_reservation(nonexistent_id)

        # Verify None is returned for non-existent reservation
        assert result is None

    def test_get_reservations_by_hotel_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test retrieving reservations by hotel ID from the real DynamoDB table."""
        # Create multiple reservations for the same hotel
        test_timestamp = int(time.time())
        hotel_id = f"H-HOTEL-TEST-{test_timestamp}"

        reservations_data = [
            {
                "hotel_id": hotel_id,
                "room_type_id": "RT-TEST-1",
                "guest_name": f"Hotel Test Guest 1 {test_timestamp}",
                "guest_email": f"hoteltest1_{test_timestamp}@example.com",
                "guest_phone": "+1234567890",
                "check_in_date": "2024-07-01",
                "check_out_date": "2024-07-03",
                "guests": 2,
                "package_type": "simple",
            },
            {
                "hotel_id": hotel_id,
                "room_type_id": "RT-TEST-2",
                "guest_name": f"Hotel Test Guest 2 {test_timestamp}",
                "guest_email": f"hoteltest2_{test_timestamp}@example.com",
                "guest_phone": "+1234567891",
                "check_in_date": "2024-07-05",
                "check_out_date": "2024-07-07",
                "guests": 4,
                "package_type": "breakfast",
            },
        ]

        created_reservation_ids = []
        for reservation_data in reservations_data:
            created_reservation = service.create_reservation(**reservation_data)
            created_reservation_ids.append(created_reservation["reservation_id"])
            cleanup_test_reservations(created_reservation["reservation_id"])

        # Retrieve reservations by hotel ID
        hotel_reservations = service.get_reservations_by_hotel(hotel_id)

        # Verify we got the expected reservations
        assert len(hotel_reservations) >= 2  # At least our test reservations

        # Find our test reservations in the results
        found_reservations = [
            res
            for res in hotel_reservations
            if res["reservation_id"] in created_reservation_ids
        ]
        assert len(found_reservations) == 2

        # Verify reservation details
        for reservation in found_reservations:
            assert reservation["hotel_id"] == hotel_id
            assert reservation["status"] == "confirmed"
            assert reservation["guest_name"].startswith("Hotel Test Guest")

    def test_get_reservations_by_guest_email_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test retrieving reservations by guest email from the real DynamoDB table."""
        # Create multiple reservations for the same guest email
        test_timestamp = int(time.time())
        guest_email = f"emailtest{test_timestamp}@example.com"

        reservations_data = [
            {
                "hotel_id": "H-EMAIL-TEST-1",
                "room_type_id": "RT-TEST-1",
                "guest_name": f"Email Test Guest {test_timestamp}",
                "guest_email": guest_email,
                "guest_phone": "+1234567890",
                "check_in_date": "2024-08-01",
                "check_out_date": "2024-08-03",
                "guests": 2,
                "package_type": "simple",
            },
            {
                "hotel_id": "H-EMAIL-TEST-2",
                "room_type_id": "RT-TEST-2",
                "guest_name": f"Email Test Guest {test_timestamp}",
                "guest_email": guest_email,
                "guest_phone": "+1234567890",
                "check_in_date": "2024-08-10",
                "check_out_date": "2024-08-12",
                "guests": 3,
                "package_type": "all_inclusive",
            },
        ]

        created_reservation_ids = []
        for reservation_data in reservations_data:
            created_reservation = service.create_reservation(**reservation_data)
            created_reservation_ids.append(created_reservation["reservation_id"])
            cleanup_test_reservations(created_reservation["reservation_id"])

        # Retrieve reservations by guest email
        email_reservations = service.get_reservations_by_guest_email(guest_email)

        # Verify we got the expected reservations
        assert len(email_reservations) >= 2  # At least our test reservations

        # Find our test reservations in the results
        found_reservations = [
            res
            for res in email_reservations
            if res["reservation_id"] in created_reservation_ids
        ]
        assert len(found_reservations) == 2

        # Verify reservation details
        for reservation in found_reservations:
            assert reservation["guest_email"] == guest_email
            assert reservation["status"] == "confirmed"
            assert reservation["guest_name"] == f"Email Test Guest {test_timestamp}"

    def test_update_reservation_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test updating a reservation in the real DynamoDB table."""
        # First create a reservation
        test_timestamp = int(time.time())
        reservation_data = {
            "hotel_id": "H-UPDATE-TEST",
            "room_type_id": "RT-TEST",
            "guest_name": f"Update Test Guest {test_timestamp}",
            "guest_email": f"updatetest{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-09-01",
            "check_out_date": "2024-09-03",
            "guests": 2,
            "package_type": "simple",
        }

        created_reservation = service.create_reservation(**reservation_data)
        reservation_id = created_reservation["reservation_id"]
        cleanup_test_reservations(reservation_id)

        # Update the reservation
        update_fields = {
            "guest_name": f"Updated Guest Name {test_timestamp}",
            "guest_phone": "+0987654321",
            "guests": 3,
            "package_type": "breakfast",
        }

        updated_reservation = service.update_reservation(reservation_id, update_fields)

        # Verify update was successful
        assert updated_reservation is not None
        assert updated_reservation["reservation_id"] == reservation_id
        assert updated_reservation["guest_name"] == update_fields["guest_name"]
        assert updated_reservation["guest_phone"] == update_fields["guest_phone"]
        assert updated_reservation["guests"] == update_fields["guests"]
        assert updated_reservation["package_type"] == update_fields["package_type"]

        # Verify unchanged fields remain the same
        assert updated_reservation["guest_email"] == reservation_data["guest_email"]
        assert updated_reservation["hotel_id"] == reservation_data["hotel_id"]
        assert updated_reservation["check_in_date"] == reservation_data["check_in_date"]
        assert (
            updated_reservation["check_out_date"] == reservation_data["check_out_date"]
        )

        # Verify updated_at timestamp was changed
        assert updated_reservation["updated_at"] != created_reservation["created_at"]

        # Verify the update persisted in DynamoDB
        retrieved_reservation = service.get_reservation(reservation_id)
        assert retrieved_reservation["guest_name"] == update_fields["guest_name"]
        assert retrieved_reservation["guest_phone"] == update_fields["guest_phone"]

    def test_update_nonexistent_reservation_with_real_table(
        self, service, verify_table_exists
    ):
        """Test updating a non-existent reservation in the real DynamoDB table."""
        # Try to update a reservation that doesn't exist
        nonexistent_id = f"CONF-{int(time.time() * 1000)}999"
        update_fields = {"guest_name": "Should Not Work"}

        result = service.update_reservation(nonexistent_id, update_fields)

        # Verify None is returned for non-existent reservation
        assert result is None

    def test_checkout_guest_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test checking out a guest in the real DynamoDB table."""
        # First create a reservation
        test_timestamp = int(time.time())
        reservation_data = {
            "hotel_id": "H-CHECKOUT-TEST",
            "room_type_id": "RT-TEST",
            "guest_name": f"Checkout Test Guest {test_timestamp}",
            "guest_email": f"checkouttest{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-10-01",
            "check_out_date": "2024-10-03",
            "guests": 2,
            "package_type": "all_inclusive",
        }

        created_reservation = service.create_reservation(**reservation_data)
        reservation_id = created_reservation["reservation_id"]
        cleanup_test_reservations(reservation_id)

        # Checkout the guest with final billing
        final_amount = 450.75
        checked_out_reservation = service.checkout_guest(reservation_id, final_amount)

        # Verify checkout was successful
        assert checked_out_reservation is not None
        assert checked_out_reservation["reservation_id"] == reservation_id
        assert checked_out_reservation["status"] == "checked_out"
        assert checked_out_reservation["final_amount"] == final_amount
        assert checked_out_reservation["payment_status"] == "completed"
        assert "checkout_time" in checked_out_reservation

        # Verify checkout time is recent
        checkout_time = datetime.fromisoformat(checked_out_reservation["checkout_time"])
        now = datetime.now()
        time_diff = (now - checkout_time).total_seconds()
        assert time_diff < 60  # Should be within the last minute

        # Verify the checkout persisted in DynamoDB
        retrieved_reservation = service.get_reservation(reservation_id)
        assert retrieved_reservation["status"] == "checked_out"
        assert retrieved_reservation["final_amount"] == final_amount
        assert retrieved_reservation["payment_status"] == "completed"

    def test_checkout_guest_without_final_amount_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test checking out a guest without final amount in the real DynamoDB table."""
        # First create a reservation
        test_timestamp = int(time.time())
        reservation_data = {
            "hotel_id": "H-CHECKOUT-NO-AMOUNT-TEST",
            "room_type_id": "RT-TEST",
            "guest_name": f"Checkout No Amount Test Guest {test_timestamp}",
            "guest_email": f"checkoutnoamount{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-11-01",
            "check_out_date": "2024-11-03",
            "guests": 1,
            "package_type": "simple",
        }

        created_reservation = service.create_reservation(**reservation_data)
        reservation_id = created_reservation["reservation_id"]
        cleanup_test_reservations(reservation_id)

        # Checkout the guest without final billing
        checked_out_reservation = service.checkout_guest(reservation_id)

        # Verify checkout was successful
        assert checked_out_reservation is not None
        assert checked_out_reservation["reservation_id"] == reservation_id
        assert checked_out_reservation["status"] == "checked_out"
        assert "checkout_time" in checked_out_reservation

        # Verify no final amount or payment status was set
        assert (
            "final_amount" not in checked_out_reservation
            or checked_out_reservation.get("final_amount") is None
        )
        assert checked_out_reservation.get("payment_status") != "completed"

    def test_checkout_nonexistent_guest_with_real_table(
        self, service, verify_table_exists
    ):
        """Test checking out a non-existent guest in the real DynamoDB table."""
        # Try to checkout a reservation that doesn't exist
        nonexistent_id = f"CONF-{int(time.time() * 1000)}999"
        result = service.checkout_guest(nonexistent_id, 100.0)

        # Verify None is returned for non-existent reservation
        assert result is None

    def test_confirmation_id_uniqueness_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test that confirmation IDs are unique when creating multiple reservations."""
        test_timestamp = int(time.time())
        base_reservation_data = {
            "hotel_id": "H-UNIQUE-TEST",
            "room_type_id": "RT-TEST",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-12-01",
            "check_out_date": "2024-12-03",
            "guests": 2,
            "package_type": "simple",
        }

        created_reservation_ids = []

        # Create multiple reservations quickly
        for i in range(5):
            reservation_data = base_reservation_data.copy()
            reservation_data["guest_name"] = f"Unique Test Guest {test_timestamp} #{i}"
            reservation_data["guest_email"] = (
                f"uniquetest{test_timestamp}_{i}@example.com"
            )

            created_reservation = service.create_reservation(**reservation_data)
            created_reservation_ids.append(created_reservation["reservation_id"])
            cleanup_test_reservations(created_reservation["reservation_id"])

            # Small delay to ensure different timestamps
            time.sleep(0.001)

        # Verify all confirmation IDs are unique
        assert len(set(created_reservation_ids)) == 5

        # Verify all IDs follow the expected format
        for reservation_id in created_reservation_ids:
            assert reservation_id.startswith("CONF-")
            assert len(reservation_id) > 10  # Should have timestamp digits

    def test_complete_reservation_lifecycle_with_real_table(
        self, service, verify_table_exists, cleanup_test_reservations
    ):
        """Test complete reservation lifecycle from creation to checkout using real DynamoDB table."""
        test_timestamp = int(time.time())

        # Step 1: Create reservation
        reservation_data = {
            "hotel_id": "H-LIFECYCLE-TEST",
            "room_type_id": "RT-LIFECYCLE",
            "guest_name": f"Lifecycle Test Guest {test_timestamp}",
            "guest_email": f"lifecycletest{test_timestamp}@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2025-01-15",
            "check_out_date": "2025-01-18",
            "guests": 2,
            "package_type": "breakfast",
        }

        created_reservation = service.create_reservation(**reservation_data)
        reservation_id = created_reservation["reservation_id"]
        cleanup_test_reservations(reservation_id)

        assert created_reservation["status"] == "confirmed"
        assert created_reservation["guest_name"] == reservation_data["guest_name"]

        # Step 2: Retrieve reservation
        retrieved_reservation = service.get_reservation(reservation_id)
        assert retrieved_reservation is not None
        assert retrieved_reservation["reservation_id"] == reservation_id
        assert retrieved_reservation["guest_email"] == reservation_data["guest_email"]

        # Step 3: Update reservation details
        update_fields = {
            "guest_phone": "+0987654321",
            "guests": 3,
            "package_type": "all_inclusive",
        }
        updated_reservation = service.update_reservation(reservation_id, update_fields)
        assert updated_reservation["guest_phone"] == "+0987654321"
        assert updated_reservation["guests"] == 3
        assert updated_reservation["package_type"] == "all_inclusive"

        # Step 4: Verify update persisted
        retrieved_after_update = service.get_reservation(reservation_id)
        assert retrieved_after_update["guest_phone"] == "+0987654321"
        assert retrieved_after_update["guests"] == 3

        # Step 5: Checkout guest
        final_amount = 875.50
        checked_out_reservation = service.checkout_guest(reservation_id, final_amount)
        assert checked_out_reservation["status"] == "checked_out"
        assert checked_out_reservation["final_amount"] == final_amount
        assert checked_out_reservation["payment_status"] == "completed"

        # Step 6: Verify final state
        final_reservation = service.get_reservation(reservation_id)
        assert final_reservation["status"] == "checked_out"
        assert final_reservation["final_amount"] == final_amount
        assert final_reservation["payment_status"] == "completed"
        assert final_reservation["guest_phone"] == "+0987654321"  # Update persisted
        assert final_reservation["guests"] == 3  # Update persisted

    def test_service_initialization_with_environment_variables(self, table_names):
        """Test that service initializes correctly with environment variables."""
        # Test with custom environment variables
        custom_env = {
            "RESERVATIONS_TABLE_NAME": table_names.get(
                "reservations", "custom-reservations-table"
            ),
            "HOTELS_TABLE_NAME": table_names.get("hotels", "custom-hotels-table"),
            "ROOM_TYPES_TABLE_NAME": table_names.get(
                "room_types", "custom-room-types-table"
            ),
        }

        original_env = {}
        for key, value in custom_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            service = ReservationService()

            # Verify table names are set correctly
            assert (
                service.reservations_table_name == custom_env["RESERVATIONS_TABLE_NAME"]
            )
            assert service.hotels_table_name == custom_env["HOTELS_TABLE_NAME"]
            assert service.room_types_table_name == custom_env["ROOM_TYPES_TABLE_NAME"]

        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                else:
                    os.environ.pop(key, None)

    def test_error_handling_with_invalid_table_access(self):
        """Test error handling when DynamoDB table access fails."""
        # Set invalid table name to trigger error
        original_env = os.environ.get("RESERVATIONS_TABLE_NAME")
        os.environ["RESERVATIONS_TABLE_NAME"] = "nonexistent-table-name"

        try:
            service = ReservationService()

            # This should fail with a proper error message
            with pytest.raises(Exception) as exc_info:
                service.create_reservation(
                    hotel_id="H-ERROR-TEST",
                    room_type_id="RT-ERROR",
                    guest_name="Error Test Guest",
                    guest_email="errortest@example.com",
                    guest_phone="+1234567890",
                    check_in_date="2025-02-01",
                    check_out_date="2025-02-03",
                    guests=2,
                    package_type="simple",
                )

            # Verify error message contains expected information
            assert "Failed to create reservation" in str(exc_info.value)

        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["RESERVATIONS_TABLE_NAME"] = original_env
            else:
                os.environ.pop("RESERVATIONS_TABLE_NAME", None)
