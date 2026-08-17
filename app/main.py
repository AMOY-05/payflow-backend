"""
Application entrypoint.
"""

import logging
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
from app.api.v1 import auth
from app.api.v1 import users
from app.api.v1 import wallet
from app.api.v1 import payout
from app.api.v1 import fx
from app.api.v1 import withdrawal
from app.api.v1 import ai
from app.api.v1 import webhooks
from app.api.v1 import banks
from app.api.v1 import admin
from app.api.v1 import kyc
from app.api.v1.virtual_account import router as virtual_account_router
import app.models

# Import all model files here so SQLAlchemy recognizes their metadata
from app.models import user, virtual_account

# Alembic owns the schema. Leave this disabled.
# create_all() builds tables directly from the models without recording
# anything in Alembic's version table, and it never alters a table that
# already exists. Running both means neither system knows what the other did.
# Base.metadata.create_all(bind=engine)

# Setup logging first
setup_logging()
logger = logging.getLogger("fintech.startup")


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

# Parse CORS origins from environment
cors_origins = []
if settings.CORS_ORIGINS:
    cors_origins = [
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ]

# Always include localhost for development
if settings.ENVIRONMENT != "production":
    cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ])

# An empty allow_origins list blocks every cross-origin browser request.
# In production that silently breaks the frontend with no server-side error.
if settings.ENVIRONMENT == "production" and not cors_origins:
    logger.warning(
        "CORS_ORIGINS is empty in production. "
        "All cross-origin browser requests will be blocked."
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Admin-Key",
        "x-admin-key",
        "Accept",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,
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
app.include_router(virtual_account_router)
app.include_router(payout.router)
app.include_router(fx.router)
app.include_router(withdrawal.router)
app.include_router(ai.router)
app.include_router(webhooks.router)
app.include_router(banks.router)
app.include_router(admin.router)
app.include_router(kyc.router)

# KYC uploads
#
# StaticFiles performs NO authentication. Anything mounted here is readable by
# anyone who knows or guesses a filename, and these files are government IDs and
# proof-of-address documents. The mount is therefore restricted to non-production
# until an authenticated download route exists in app/api/v1/admin.py that checks
# the admin key and streams the file.
#
# The directory also now matches the one that is checked and created at startup.
if settings.ENVIRONMENT != "production" and os.path.exists(
    settings.KYC_UPLOAD_DIR
):
    app.mount(
        "/uploads",
        StaticFiles(directory=settings.KYC_UPLOAD_DIR),
        name="uploads"
    )


@app.on_event("startup")
async def on_startup():
    os.makedirs(settings.KYC_UPLOAD_DIR, exist_ok=True)
    logger.info(f"PayFlow started in {settings.ENVIRONMENT} mode")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("PayFlow shutting down")


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