"""
Database connection layer.

Design decision: we use SQLAlchemy's traditional (sync) engine for Phase 1
for simplicity and easier debugging. We will revisit async SQLAlchemy in
Phase 10 (Production Readiness) once we need higher concurrency throughput,
since switching ORMs/engines mid-project is risky for a fintech app where
correctness of transactions matters more than premature optimization.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # avoids "server closed the connection unexpectedly" errors
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a DB session per request and always
    closes it — critical to avoid connection leaks under load.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()