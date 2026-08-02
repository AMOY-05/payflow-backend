"""
Production security middleware.

Adds security headers to every response to protect
against common web attacks.
"""

import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

logger = logging.getLogger("fintech.requests")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds comprehensive security headers to every response.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Force HTTPS
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=()"
        )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: https: fastapi.tiangolo.com; "
            "font-src 'self' data: cdn.jsdelivr.net; "
            "connect-src 'self' https://api.flutterwave.com "
            "https://v6.exchangerate-api.com"
        )

        # Prevent XSS
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Remove server info
        response.headers["Server"] = "PayFlow/1.0"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with timing information.
    Critical for debugging payment issues and auditing.
    """
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"- IP: {request.client.host}"
        )

        response = await call_next(request)

        duration = round((time.time() - start_time) * 1000, 2)

        # Log response with duration
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Duration: {duration}ms"
        )

        # Add request ID to response headers for debugging
        response.headers["X-Request-ID"] = request_id

        return response


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """
    Allows you to put the platform in maintenance mode
    without redeploying. Just set MAINTENANCE_MODE=True in .env
    """
    async def dispatch(self, request: Request, call_next):
        from app.core.config import settings

        # Always allow health checks even in maintenance mode
        if request.url.path == "/health":
            return await call_next(request)

        maintenance = getattr(settings, "MAINTENANCE_MODE", False)
        if maintenance:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Platform under maintenance",
                    "message": (
                        "We are performing scheduled maintenance. "
                        "We will be back shortly. "
                        "Contact support@yourplatform.com for urgent issues."
                    )
                }
            )

        return await call_next(request)