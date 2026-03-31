# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""API Gateway REST handler using AWS Lambda Powertools."""

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
)
from aws_lambda_powertools.logging import correlation_paths
from pydantic import ValidationError

from ..models.generated.api_models import (
    CheckoutRequest,
    HousekeepingRequest,
    ReservationUpdateRequest,
)
from ..models.generated.validators import (
    AvailabilityRequestWithValidation,
    QuoteRequestWithValidation,
    ReservationRequestWithValidation,
)
from ..tools.api_functions import (
    check_availability,
    checkout_guest,
    create_housekeeping_request,
    create_reservation,
    generate_quote,
    get_hotels,
    get_reservation,
    get_reservations,
    update_reservation,
)
from ..utils.validation_errors import format_validation_error

# Initialize Powertools
logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()


@app.post("/availability/check")
@tracer.capture_method
def check_availability_handler():
    """Check room availability for a hotel on specific dates."""
    try:
        body = app.current_event.json_body

        # Validate request using Pydantic model
        try:
            validated_request = AvailabilityRequestWithValidation(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Availability request validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            # Return the structured error response directly with 400 status
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing availability check",
            extra={"hotel_id": validated_request.hotel_id},
        )

        # Convert to dict for business logic (mode='json' serializes dates to strings)
        result = check_availability(**validated_request.model_dump(mode="json"))

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid availability request"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Availability check failed", extra={"error": str(e)})
        raise InternalServerError("Failed to check availability")


@app.post("/quotes/generate")
@tracer.capture_method
def generate_quote_handler():
    """Generate a detailed pricing quote and store in DynamoDB."""
    try:
        body = app.current_event.json_body

        # Validate request using Pydantic model
        try:
            validated_request = QuoteRequestWithValidation(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Quote request validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            # Return the structured error response directly with 400 status
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing quote generation",
            extra={"hotel_id": validated_request.hotel_id},
        )

        # Convert to dict for business logic (mode='json' serializes dates to strings)
        result = generate_quote(**validated_request.model_dump(mode="json"))

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid quote request"))

        # The generate_quote function now returns a quote_id that can be used for reservations
        logger.info(
            "Quote generated successfully",
            extra={
                "quote_id": result.get("quote_id"),
                "hotel_id": validated_request.hotel_id,
                "total_cost": result.get("total_cost"),
                "expires_at": result.get("expires_at"),
            },
        )

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Quote generation failed", extra={"error": str(e)})
        raise InternalServerError("Failed to generate quote")


@app.post("/reservations")
@tracer.capture_method
def create_reservation_handler():
    """Create a new hotel reservation."""
    try:
        body = app.current_event.json_body

        # Validate request using Pydantic model
        try:
            validated_request = ReservationRequestWithValidation(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Reservation request validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing reservation creation",
            extra={"quote_id": validated_request.quote_id},
        )

        # Convert to dict for business logic (mode='json' serializes dates to strings)
        result = create_reservation(**validated_request.model_dump(mode="json"))

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid reservation request"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Reservation creation failed", extra={"error": str(e)})
        raise InternalServerError("Failed to create reservation")


@app.get("/reservations")
@tracer.capture_method
def get_reservations_handler():
    """Retrieve reservations by hotel or guest email."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        logger.info("Processing reservations query", extra={"params": query_params})

        # Validate query parameters
        try:
            # Convert limit to int if provided
            if query_params.get("limit"):
                try:
                    query_params["limit"] = int(query_params["limit"])
                except ValueError:
                    raise ValidationError.from_exception_data(
                        "ValueError",
                        [
                            {
                                "type": "int_parsing",
                                "loc": ("limit",),
                                "msg": "Input should be a valid integer",
                                "input": query_params.get("limit"),
                            }
                        ],
                    )

            # Basic validation for limit range
            if "limit" in query_params:
                limit = query_params["limit"]
                if not isinstance(limit, int) or limit < 1 or limit > 100:
                    raise ValidationError.from_exception_data(
                        "ValueError",
                        [
                            {
                                "type": "int_range",
                                "loc": ("limit",),
                                "msg": "Input should be between 1 and 100",
                                "input": limit,
                            }
                        ],
                    )

        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Reservations query validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        result = get_reservations(**query_params)

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid reservations query"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Reservations query failed", extra={"error": str(e)})
        raise InternalServerError("Failed to retrieve reservations")


@app.get("/reservations/<reservation_id>")
@tracer.capture_method
def get_reservation_handler(reservation_id: str):
    """Get details of a specific reservation."""
    try:
        # Validate path parameter
        try:
            if (
                not reservation_id
                or not isinstance(reservation_id, str)
                or not reservation_id.strip()
            ):
                raise ValidationError.from_exception_data(
                    "ValueError",
                    [
                        {
                            "type": "string_type",
                            "loc": ("reservation_id",),
                            "msg": "Input should be a non-empty string",
                            "input": reservation_id,
                        }
                    ],
                )
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Reservation lookup validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing reservation lookup", extra={"reservation_id": reservation_id}
        )

        result = get_reservation(reservation_id=reservation_id)

        # Check if there was an error in the tool response
        if result.get("error"):
            if result.get("error_code") == "NOT_FOUND":
                raise NotFoundError("Reservation not found")
            else:
                raise BadRequestError(
                    result.get("message", "Invalid reservation lookup")
                )

        return result

    except NotFoundError:
        raise
    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Reservation lookup failed", extra={"error": str(e)})
        raise InternalServerError("Failed to retrieve reservation")


@app.put("/reservations/<reservation_id>")
@tracer.capture_method
def update_reservation_handler(reservation_id: str):
    """Update an existing reservation."""
    try:
        body = app.current_event.json_body

        # Validate path parameter
        try:
            if (
                not reservation_id
                or not isinstance(reservation_id, str)
                or not reservation_id.strip()
            ):
                raise ValidationError.from_exception_data(
                    "ValueError",
                    [
                        {
                            "type": "string_type",
                            "loc": ("reservation_id",),
                            "msg": "Input should be a non-empty string",
                            "input": reservation_id,
                        }
                    ],
                )
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Reservation update path validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        # Validate request body using Pydantic model
        try:
            validated_request = ReservationUpdateRequest(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Reservation update validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing reservation update", extra={"reservation_id": reservation_id}
        )

        # Convert to dict for business logic
        result = update_reservation(
            reservation_id=reservation_id,
            **validated_request.model_dump(exclude_none=True),
        )

        # Check if there was an error in the tool response
        if result.get("error"):
            if result.get("error_code") == "NOT_FOUND":
                raise NotFoundError("Reservation not found")
            else:
                raise BadRequestError(
                    result.get("message", "Invalid reservation update")
                )

        return result

    except NotFoundError:
        raise
    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Reservation update failed", extra={"error": str(e)})
        raise InternalServerError("Failed to update reservation")


@app.post("/reservations/<reservation_id>/checkout")
@tracer.capture_method
def checkout_guest_handler(reservation_id: str):
    """Process guest checkout and final billing."""
    try:
        body = app.current_event.json_body

        # Validate path parameter
        try:
            if (
                not reservation_id
                or not isinstance(reservation_id, str)
                or not reservation_id.strip()
            ):
                raise ValidationError.from_exception_data(
                    "ValueError",
                    [
                        {
                            "type": "string_type",
                            "loc": ("reservation_id",),
                            "msg": "Input should be a non-empty string",
                            "input": reservation_id,
                        }
                    ],
                )
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Checkout path validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        # Validate request body using Pydantic model
        try:
            validated_request = CheckoutRequest(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Checkout request validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing guest checkout", extra={"reservation_id": reservation_id}
        )

        # Convert to dict for business logic
        result = checkout_guest(
            reservation_id=reservation_id,
            **validated_request.model_dump(exclude_none=True),
        )

        # Check if there was an error in the tool response
        if result.get("error"):
            if result.get("error_code") == "NOT_FOUND":
                raise NotFoundError("Reservation not found")
            else:
                raise BadRequestError(result.get("message", "Invalid checkout request"))

        return result

    except NotFoundError:
        raise
    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Guest checkout failed", extra={"error": str(e)})
        raise InternalServerError("Failed to process checkout")


@app.get("/hotels")
@tracer.capture_method
def get_hotels_handler():
    """Get a list of all available hotels."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        logger.info("Processing hotels query")

        # Validate query parameters
        try:
            # Convert limit to int if provided
            if query_params.get("limit"):
                try:
                    query_params["limit"] = int(query_params["limit"])
                except ValueError:
                    raise ValidationError.from_exception_data(
                        "ValueError",
                        [
                            {
                                "type": "int_parsing",
                                "loc": ("limit",),
                                "msg": "Input should be a valid integer",
                                "input": query_params.get("limit"),
                            }
                        ],
                    )

            # Basic validation for limit range
            if "limit" in query_params:
                limit = query_params["limit"]
                if not isinstance(limit, int) or limit < 1 or limit > 100:
                    raise ValidationError.from_exception_data(
                        "ValueError",
                        [
                            {
                                "type": "int_range",
                                "loc": ("limit",),
                                "msg": "Input should be between 1 and 100",
                                "input": limit,
                            }
                        ],
                    )

        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Hotels query validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        result = get_hotels(**query_params)

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid hotels query"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Hotels query failed", extra={"error": str(e)})
        raise InternalServerError("Failed to retrieve hotels")


@app.post("/requests/housekeeping")
@tracer.capture_method
def create_housekeeping_request_handler():
    """Create a housekeeping or maintenance request."""
    try:
        body = app.current_event.json_body

        # Validate request using Pydantic model
        try:
            validated_request = HousekeepingRequest(**body)
        except ValidationError as e:
            error_response = format_validation_error(e)
            logger.warning(
                "Housekeeping request validation failed",
                extra={"validation_errors": error_response["details"]},
            )
            return Response(
                status_code=400, content_type="application/json", body=error_response
            )

        logger.info(
            "Processing housekeeping request",
            extra={"hotel_id": validated_request.hotel_id},
        )

        # Convert to dict for business logic (mode='json' serializes dates to strings)
        result = create_housekeeping_request(
            **validated_request.model_dump(mode="json")
        )

        # Check if there was an error in the tool response
        if result.get("error"):
            raise BadRequestError(result.get("message", "Invalid housekeeping request"))

        return result

    except BadRequestError:
        raise
    except Exception as e:
        logger.error("Housekeeping request failed", extra={"error": str(e)})
        raise InternalServerError("Failed to create housekeeping request")


# Lambda handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Main Lambda handler using Powertools."""
    return app.resolve(event, context)
