# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CDK construct for Hotel PMS DynamoDB tables with native data import."""

from aws_cdk import (
    RemovalPolicy,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_s3_assets as assets,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class HotelPMSDynamoDBConstruct(Construct):
    """Construct for Hotel PMS DynamoDB tables with native data import."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 assets for CSV data files (paths relative to workspace root)
        self.hotels_asset = assets.Asset(self, "HotelsAsset", path="../../hotel_data/hotel_pms_data/hotels.csv")

        self.room_types_asset = assets.Asset(
            self, "RoomTypesAsset", path="../../hotel_data/hotel_pms_data/room_types.csv"
        )

        self.rate_modifiers_asset = assets.Asset(
            self, "RateModifiersAsset", path="../../hotel_data/hotel_pms_data/rate_modifiers.csv"
        )

        # Static tables with data import (using Table construct)

        # Hotels table
        self.hotels_table = dynamodb.Table(
            self,
            "HotelsTable",
            partition_key=dynamodb.Attribute(name="hotel_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            import_source=dynamodb.ImportSourceSpecification(
                input_format=dynamodb.InputFormat.csv(),
                bucket=self.hotels_asset.bucket,
                key_prefix=self.hotels_asset.s3_object_key,
            ),
        )

        # Room types table
        self.room_types_table = dynamodb.Table(
            self,
            "RoomTypesTable",
            partition_key=dynamodb.Attribute(name="room_type_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            import_source=dynamodb.ImportSourceSpecification(
                input_format=dynamodb.InputFormat.csv(),
                bucket=self.room_types_asset.bucket,
                key_prefix=self.room_types_asset.s3_object_key,
            ),
        )

        # Add GSI for hotel_id
        self.room_types_table.add_global_secondary_index(
            index_name="hotel-id-index",
            partition_key=dynamodb.Attribute(name="hotel_id", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Rate modifiers table
        self.rate_modifiers_table = dynamodb.Table(
            self,
            "RateModifiersTable",
            partition_key=dynamodb.Attribute(name="modifier_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            import_source=dynamodb.ImportSourceSpecification(
                input_format=dynamodb.InputFormat.csv(),
                bucket=self.rate_modifiers_asset.bucket,
                key_prefix=self.rate_modifiers_asset.s3_object_key,
            ),
        )

        # Add GSI for hotel_id
        self.rate_modifiers_table.add_global_secondary_index(
            index_name="hotel-id-index",
            partition_key=dynamodb.Attribute(name="hotel_id", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Dynamic tables (using TableV2, no import source)

        # Reservations table
        self.reservations_table = dynamodb.TableV2(
            self,
            "ReservationsTable",
            partition_key=dynamodb.Attribute(name="reservation_id", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Add GSI for hotel_id
        self.reservations_table.add_global_secondary_index(
            index_name="hotel-id-index",
            partition_key=dynamodb.Attribute(name="hotel_id", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Add GSI for guest_email
        self.reservations_table.add_global_secondary_index(
            index_name="guest-email-index",
            partition_key=dynamodb.Attribute(name="guest_email", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Requests table
        self.requests_table = dynamodb.TableV2(
            self,
            "RequestsTable",
            partition_key=dynamodb.Attribute(name="request_id", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Add GSI for hotel_id
        self.requests_table.add_global_secondary_index(
            index_name="hotel-id-index",
            partition_key=dynamodb.Attribute(name="hotel_id", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Quotes table (dynamic table for temporary quote storage)
        self.quotes_table = dynamodb.TableV2(
            self,
            "QuotesTable",
            partition_key=dynamodb.Attribute(name="quote_id", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at",  # Enable TTL for automatic quote expiration
        )

        # Suppress Point-in-Time Recovery warnings for static data tables
        # These tables contain only static reference data that is imported from CSV files
        # and does not require point-in-time recovery for demo/development purposes
        NagSuppressions.add_resource_suppressions(
            self.hotels_table,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "Point-in-time recovery not required for static hotel reference data imported from CSV. "
                    "This table contains simulated demo data that can be easily recreated from source files.",
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.room_types_table,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "Point-in-time recovery not required for static room type reference data imported "
                    "from CSV. This table contains simulated demo data that can be easily recreated from source files.",
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.rate_modifiers_table,
            [
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "Point-in-time recovery not required for static rate modifier reference data imported "
                    "from CSV. This table contains simulated demo data that can be easily recreated from source files.",
                }
            ],
        )

    @property
    def environment_variables(self) -> dict:
        """Get environment variables for Lambda functions."""
        return {
            "HOTELS_TABLE_NAME": self.hotels_table.table_name,
            "ROOM_TYPES_TABLE_NAME": self.room_types_table.table_name,
            "RATE_MODIFIERS_TABLE_NAME": self.rate_modifiers_table.table_name,
            "RESERVATIONS_TABLE_NAME": self.reservations_table.table_name,
            "REQUESTS_TABLE_NAME": self.requests_table.table_name,
            "QUOTES_TABLE_NAME": self.quotes_table.table_name,
        }

    def grant_read(self, grantee: iam.IGrantable) -> None:
        """Grant read access to all tables."""
        self.hotels_table.grant_read_data(grantee)
        self.room_types_table.grant_read_data(grantee)
        self.rate_modifiers_table.grant_read_data(grantee)
        self.reservations_table.grant_read_data(grantee)
        self.requests_table.grant_read_data(grantee)
        self.quotes_table.grant_read_data(grantee)

    def grant_write(self, grantee: iam.IGrantable) -> None:
        """Grant write access to dynamic tables (reservations, requests, and quotes)."""
        self.reservations_table.grant_read_write_data(grantee)
        self.requests_table.grant_read_write_data(grantee)
        self.quotes_table.grant_read_write_data(grantee)

    def grant(self, grantee: iam.IGrantable) -> None:
        """Grant full access to all tables."""
        self.hotels_table.grant_read_write_data(grantee)
        self.room_types_table.grant_read_write_data(grantee)
        self.rate_modifiers_table.grant_read_write_data(grantee)
        self.reservations_table.grant_read_write_data(grantee)
        self.requests_table.grant_read_write_data(grantee)
        self.quotes_table.grant_read_write_data(grantee)

    @property
    def table_names(self) -> dict:
        """Get all table names."""
        return {
            "hotels": self.hotels_table.table_name,
            "room_types": self.room_types_table.table_name,
            "rate_modifiers": self.rate_modifiers_table.table_name,
            "reservations": self.reservations_table.table_name,
            "requests": self.requests_table.table_name,
            "quotes": self.quotes_table.table_name,
        }

    @property
    def table_arns(self) -> dict:
        """Get all table ARNs."""
        return {
            "hotels": self.hotels_table.table_arn,
            "room_types": self.room_types_table.table_arn,
            "rate_modifiers": self.rate_modifiers_table.table_arn,
            "reservations": self.reservations_table.table_arn,
            "requests": self.requests_table.table_arn,
            "quotes": self.quotes_table.table_arn,
        }
