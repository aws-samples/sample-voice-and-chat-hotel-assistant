# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CloudWatch metrics utilities for business KPIs and operational monitoring."""

from decimal import Decimal

from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit


class HotelPMSMetrics:
    """Centralized metrics collection for Hotel PMS API."""

    def __init__(self, metrics: Metrics):
        self.metrics = metrics

    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float | None = None,
    ) -> None:
        """Record API request metrics."""
        # Basic request count
        self.metrics.add_metric(
            name="APIRequest",
            unit=MetricUnit.Count,
            value=1,
        )

        # Request by endpoint - use separate metrics for different endpoints
        self.metrics.add_metric(
            name=f"APIRequest_{endpoint.replace('/', '_').replace('-', '_')}",
            unit=MetricUnit.Count,
            value=1,
        )

        # Status code metrics
        if 200 <= status_code < 300:
            self.metrics.add_metric(name="APISuccess", unit=MetricUnit.Count, value=1)
        elif 400 <= status_code < 500:
            self.metrics.add_metric(
                name="APIClientError", unit=MetricUnit.Count, value=1
            )
        elif status_code >= 500:
            self.metrics.add_metric(
                name="APIServerError", unit=MetricUnit.Count, value=1
            )

        # Response time if provided
        if response_time_ms is not None:
            self.metrics.add_metric(
                name="APIResponseTime",
                unit=MetricUnit.Milliseconds,
                value=response_time_ms,
            )

    def record_availability_check(
        self,
        hotel_id: str,
        available_room_types: int,
        total_rooms_checked: int,
        nights: int,
    ) -> None:
        """Record availability check metrics."""
        self.metrics.add_metric(
            name="AvailabilityCheck",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name="AvailableRoomTypes",
            unit=MetricUnit.Count,
            value=available_room_types,
        )

        self.metrics.add_metric(
            name="RoomsChecked",
            unit=MetricUnit.Count,
            value=total_rooms_checked,
        )

        self.metrics.add_metric(
            name="NightsRequested",
            unit=MetricUnit.Count,
            value=nights,
        )

        # Availability rate
        if total_rooms_checked > 0:
            availability_rate = (available_room_types / total_rooms_checked) * 100
            self.metrics.add_metric(
                name="AvailabilityRate",
                unit=MetricUnit.Percent,
                value=availability_rate,
            )

    def record_quote_generation(
        self,
        hotel_id: str,
        room_type_id: str,
        total_amount: Decimal,
        nights: int,
        guests: int,
        package_type: str,
    ) -> None:
        """Record quote generation metrics."""
        self.metrics.add_metric(
            name="QuoteGenerated",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name="QuoteAmount",
            unit=MetricUnit.Count,
            value=float(total_amount),
        )

        self.metrics.add_metric(
            name="QuoteNights",
            unit=MetricUnit.Count,
            value=nights,
        )

        self.metrics.add_metric(
            name="QuoteGuests",
            unit=MetricUnit.Count,
            value=guests,
        )

        # Average nightly rate
        if nights > 0:
            avg_nightly_rate = float(total_amount) / nights
            self.metrics.add_metric(
                name="AverageNightlyRate",
                unit=MetricUnit.Count,
                value=avg_nightly_rate,
            )

        # Package type distribution
        self.metrics.add_metric(
            name=f"QuoteByPackageType_{package_type}",
            unit=MetricUnit.Count,
            value=1,
        )

    def record_reservation_creation(
        self,
        hotel_id: str,
        room_type_id: str,
        total_amount: Decimal,
        nights: int,
        guests: int,
        package_type: str,
        lead_time_days: int,
    ) -> None:
        """Record reservation creation metrics."""
        self.metrics.add_metric(
            name="ReservationCreated",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name="ReservationRevenue",
            unit=MetricUnit.Count,
            value=float(total_amount),
        )

        self.metrics.add_metric(
            name="ReservationNights",
            unit=MetricUnit.Count,
            value=nights,
        )

        self.metrics.add_metric(
            name="ReservationGuests",
            unit=MetricUnit.Count,
            value=guests,
        )

        self.metrics.add_metric(
            name="ReservationLeadTime",
            unit=MetricUnit.Count,
            value=lead_time_days,
        )

        # Revenue per night
        if nights > 0:
            revenue_per_night = float(total_amount) / nights
            self.metrics.add_metric(
                name="RevenuePerNight",
                unit=MetricUnit.Count,
                value=revenue_per_night,
            )

        # Package type distribution
        self.metrics.add_metric(
            name=f"ReservationByPackageType_{package_type}",
            unit=MetricUnit.Count,
            value=1,
        )

    def record_reservation_update(
        self,
        reservation_id: str,
        update_type: str,
        old_status: str | None = None,
        new_status: str | None = None,
    ) -> None:
        """Record reservation update metrics."""
        self.metrics.add_metric(
            name="ReservationUpdated",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"ReservationUpdateByType_{update_type}",
            unit=MetricUnit.Count,
            value=1,
        )

        if old_status and new_status:
            self.metrics.add_metric(
                name=f"ReservationStatusChange_{old_status}_to_{new_status}",
                unit=MetricUnit.Count,
                value=1,
            )

    def record_checkout(
        self,
        hotel_id: str,
        total_charges: Decimal,
        additional_charges: Decimal,
        payment_method: str,
        nights_stayed: int,
    ) -> None:
        """Record guest checkout metrics."""
        self.metrics.add_metric(
            name="GuestCheckout",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name="CheckoutRevenue",
            unit=MetricUnit.Count,
            value=float(total_charges),
        )

        if additional_charges > 0:
            self.metrics.add_metric(
                name="AdditionalCharges",
                unit=MetricUnit.Count,
                value=float(additional_charges),
            )

        self.metrics.add_metric(
            name=f"CheckoutByPaymentMethod_{payment_method}",
            unit=MetricUnit.Count,
            value=1,
        )

        # Revenue per night for completed stays
        if nights_stayed > 0:
            revenue_per_night = float(total_charges) / nights_stayed
            self.metrics.add_metric(
                name="ActualRevenuePerNight",
                unit=MetricUnit.Count,
                value=revenue_per_night,
            )

    def record_housekeeping_request(
        self,
        hotel_id: str,
        request_type: str,
        priority: str,
        room_number: str,
    ) -> None:
        """Record housekeeping request metrics."""
        self.metrics.add_metric(
            name="HousekeepingRequestCreated",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"HousekeepingByType_{request_type}",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"HousekeepingByPriority_{priority}",
            unit=MetricUnit.Count,
            value=1,
        )

    def record_database_operation(
        self,
        operation: str,
        table: str,
        success: bool,
        duration_ms: float | None = None,
    ) -> None:
        """Record database operation metrics."""
        self.metrics.add_metric(
            name=f"DatabaseOperation_{operation}_{table}",
            unit=MetricUnit.Count,
            value=1,
        )

        if success:
            self.metrics.add_metric(
                name="DatabaseOperationSuccess",
                unit=MetricUnit.Count,
                value=1,
            )
        else:
            self.metrics.add_metric(
                name="DatabaseOperationError",
                unit=MetricUnit.Count,
                value=1,
            )

        if duration_ms is not None:
            self.metrics.add_metric(
                name="DatabaseOperationDuration",
                unit=MetricUnit.Milliseconds,
                value=duration_ms,
            )

    def record_validation_error(
        self,
        error_type: str,
        field: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Record validation error metrics."""
        self.metrics.add_metric(
            name="ValidationError",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"ValidationErrorByType_{error_type}",
            unit=MetricUnit.Count,
            value=1,
        )

        if field:
            self.metrics.add_metric(
                name=f"ValidationErrorByField_{field}",
                unit=MetricUnit.Count,
                value=1,
            )

        if endpoint:
            self.metrics.add_metric(
                name=f"ValidationErrorByEndpoint_{endpoint.replace('/', '_')}",
                unit=MetricUnit.Count,
                value=1,
            )

    def record_business_logic_error(
        self,
        error_type: str,
        business_rule: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Record business logic error metrics."""
        self.metrics.add_metric(
            name="BusinessLogicError",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"BusinessLogicErrorByType_{error_type}",
            unit=MetricUnit.Count,
            value=1,
        )

        if business_rule:
            self.metrics.add_metric(
                name=f"BusinessLogicErrorByRule_{business_rule}",
                unit=MetricUnit.Count,
                value=1,
            )

        if endpoint:
            self.metrics.add_metric(
                name=f"BusinessLogicErrorByEndpoint_{endpoint.replace('/', '_')}",
                unit=MetricUnit.Count,
                value=1,
            )

    def record_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: MetricUnit = MetricUnit.Milliseconds,
    ) -> None:
        """Record custom performance metrics."""
        self.metrics.add_metric(
            name=metric_name,
            unit=unit,
            value=value,
        )

    def record_error_by_type(
        self,
        error_type: str,
        error_code: str,
        endpoint: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Record errors by type for detailed analysis."""
        # Create a sanitized metric name
        endpoint_name = (endpoint or "unknown").replace("/", "_").replace("-", "_")
        self.metrics.add_metric(
            name=f"ErrorByType_{error_type}_{endpoint_name}",
            unit=MetricUnit.Count,
            value=1,
        )

    def record_circuit_breaker_event(
        self,
        service: str,
        event_type: str,  # "open", "close", "half_open"
        failure_count: int | None = None,
    ) -> None:
        """Record circuit breaker events."""
        self.metrics.add_metric(
            name=f"CircuitBreakerEvent_{service}_{event_type}",
            unit=MetricUnit.Count,
            value=1,
        )

        if failure_count is not None:
            self.metrics.add_metric(
                name=f"CircuitBreakerFailureCount_{service}",
                unit=MetricUnit.Count,
                value=failure_count,
            )

    def record_retry_attempt(
        self,
        operation: str,
        attempt_number: int,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        """Record retry attempts for operations."""
        success_str = "success" if success else "failure"
        self.metrics.add_metric(
            name=f"RetryAttempt_{operation}_{success_str}",
            unit=MetricUnit.Count,
            value=1,
        )

        self.metrics.add_metric(
            name=f"RetryAttemptNumber_{operation}",
            unit=MetricUnit.Count,
            value=attempt_number,
        )

    def record_cache_operation(
        self,
        operation: str,  # "hit", "miss", "set", "delete"
        cache_type: str,
        key_pattern: str | None = None,
    ) -> None:
        """Record cache operations."""
        self.metrics.add_metric(
            name=f"CacheOperation_{cache_type}_{operation}",
            unit=MetricUnit.Count,
            value=1,
        )

    def record_external_service_call(
        self,
        service_name: str,
        operation: str,
        success: bool,
        response_time_ms: float | None = None,
        status_code: int | None = None,
    ) -> None:
        """Record external service calls."""
        success_str = "success" if success else "failure"
        self.metrics.add_metric(
            name=f"ExternalServiceCall_{service_name}_{operation}_{success_str}",
            unit=MetricUnit.Count,
            value=1,
        )

        if response_time_ms is not None:
            self.metrics.add_metric(
                name=f"ExternalServiceResponseTime_{service_name}_{operation}",
                unit=MetricUnit.Milliseconds,
                value=response_time_ms,
            )
