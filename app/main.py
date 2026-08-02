"""
Application entrypoint.
"""

import logging
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError, IntegrityError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    MaintenanceModeMiddleware
)
from app.core.errors import (
    validation_error_handler,
    database_error_handler,
    integrity_error_handler,
    generic_error_handler
)
from app.api.v1 import (
    auth, users, wallet, virtual_account,
    payout, fx, withdrawal, ai, webhooks, banks, admin, kyc
)
import app.models

# Setup logging first
setup_logging()
logger = logging.getLogger("fintech.startup")

# Initialize Sentry for error monitoring (production only)
if settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT
    )
    logger.info("Sentry error monitoring initialized")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "USD virtual accounts and cross-border payouts "
        "for African creators and freelancers."
    ),
    version="1.0.0",
    # Hide docs in production
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Security and logging middleware
# Order matters — first added = last executed
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MaintenanceModeMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "x-admin-key",
        "X-Admin-Key",
    ],
)

# Global error handlers
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(OperationalError, database_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(wallet.router)
app.include_router(virtual_account.router)
app.include_router(payout.router)
app.include_router(fx.router)
app.include_router(withdrawal.router)
app.include_router(ai.router)
app.include_router(webhooks.router)
app.include_router(banks.router)
app.include_router(admin.router)
app.include_router(kyc.router)

# Serve KYC uploads to admin only
if os.path.exists(settings.KYC_UPLOAD_DIR):
    app.mount(
        "/uploads",
        StaticFiles(directory="uploads"),
        name="uploads"
    )

@app.on_event("startup")
def on_startup():
    import os
    os.makedirs(settings.KYC_UPLOAD_DIR, exist_ok=True)
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)
    logger.info(
        f"{settings.APP_NAME} v1.0.0 started "
        f"in {settings.ENVIRONMENT} mode"
    )


@app.on_event("shutdown")
def on_shutdown():
    logger.info(f"{settings.APP_NAME} shutting down")


@app.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint.
    Used by load balancers and monitoring to check if
    the service is alive.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/detailed", tags=["System"])
def detailed_health_check():
    """
    Detailed health check that tests DB and Redis connections.
    Only available in non-production environments.
    """
    if settings.ENVIRONMENT == "production":
        return {"status": "ok"}

    health = {
        "api": "ok",
        "database": "unknown",
        "redis": "unknown"
    }

    # Check database
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health["database"] = "ok"
    except Exception as e:
        health["database"] = f"error: {str(e)}"

    # Check Redis
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health["redis"] = "ok"
    except Exception as e:
        health["redis"] = f"error: {str(e)}"

    overall = "ok" if all(
        v == "ok" for v in health.values()
    ) else "degraded"

    health["status"] = overall
    return health