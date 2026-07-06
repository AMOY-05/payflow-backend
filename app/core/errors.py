"""
Global error handling.

In production you NEVER want raw Python exceptions
reaching the user. This catches everything and returns
clean, safe error messages.
"""

import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError, IntegrityError

logger = logging.getLogger("fintech.errors")


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
):
    """
    Handle Pydantic validation errors with clean messages.
    Instead of showing raw Pydantic output, we show
    friendly field-level errors.
    """
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Please check your input and try again",
            "details": errors
        }
    )


async def database_error_handler(
    request: Request,
    exc: OperationalError
):
    """
    Handle database errors without exposing DB details.
    """
    logger.error(f"Database error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Service temporarily unavailable",
            "message": (
                "We are experiencing technical difficulties. "
                "Please try again in a few minutes."
            )
        }
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError
):
    """
    Handle database integrity errors (duplicate keys etc).
    """
    logger.error(f"Integrity error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Conflict",
            "message": "A record with this information already exists."
        }
    )


async def generic_error_handler(
    request: Request,
    exc: Exception
):
    """
    Catch-all handler. Logs full error internally
    but returns safe message to user.
    """
    logger.error(
        f"Unhandled error on {request.url.path}: "
        f"{type(exc).__name__}: {str(exc)}",
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": (
                "Something went wrong on our end. "
                "Our team has been notified. "
                "Please try again or contact support."
            )
        }
    )