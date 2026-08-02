"""
MongoDB connection for admin analytics.

Why MongoDB alongside PostgreSQL:
- PostgreSQL = source of truth for all financial data (transactions, wallets, withdrawals)
- MongoDB = analytics, admin dashboards, audit logs, aggregated stats
- MongoDB is schema-flexible which is perfect for analytics where
  the shape of data changes as we add new metrics
- We never store money or user credentials in MongoDB — only derived stats
"""

from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import settings
import logging

logger = logging.getLogger("fintech.mongodb")

_client = None
_db = None


def get_mongo_client() -> MongoClient:
    global _client
    if _client is None:
        if not settings.MONGODB_URL:
            logger.warning("MongoDB URL not configured — admin analytics disabled")
            return None
        try:
            _client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
            _client.admin.command("ping")
            logger.info("MongoDB connected successfully")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            return None
    return _client


def get_admin_db() -> Database:
    global _db
    client = get_mongo_client()
    if client is None:
        return None
    if _db is None:
        _db = client[settings.MONGODB_DB_NAME]
    return _db


def get_mongo_db():
    """FastAPI dependency for MongoDB."""
    return get_admin_db()