"""
Structured JSON logging for production.

Why JSON logs:
- Every log line is parseable by log aggregators (Datadog, CloudWatch, Papertrail)
- You can search logs by user_id, reference, amount, provider
- Critical for fintech — every money movement must be traceable
"""

import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)

    if settings.ENVIRONMENT == "production":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Pre-configured loggers for each module
auth_logger = get_logger("fintech.auth")
wallet_logger = get_logger("fintech.wallet")
withdrawal_logger = get_logger("fintech.withdrawal")
fx_logger = get_logger("fintech.fx")
webhook_logger = get_logger("fintech.webhook")
security_logger = get_logger("fintech.security")