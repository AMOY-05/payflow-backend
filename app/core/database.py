from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
import logging

logger = logging.getLogger("fintech.database")

# Build connection URL
database_url = settings.DATABASE_URL

# Fix postgres:// to postgresql:// for SQLAlchemy compatibility
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Connection arguments for production SSL
#
# NOTE: Render's *internal* database hostname has no domain suffix, so it does
# not contain "render.com" and this branch will not fire for it. That is
# correct for SSL, since internal traffic stays inside Render's network, but it
# also means connect_timeout is not applied there. Add "?sslmode=require" to
# the URL itself if you ever need this to trigger regardless of hostname.
connect_args = {}
if "render.com" in database_url or "sslmode=require" in database_url:
    connect_args = {
        "sslmode": "require",
        "connect_timeout": 30,
    }

engine = create_engine(
    database_url,
    pool_pre_ping=True,          # Test connection before using
    pool_recycle=1800,           # Recycle connections every 30 minutes
    pool_size=5,                 # Maximum connections in pool
    max_overflow=10,             # Extra connections when pool is full
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    except HTTPException:
        # An ordinary API outcome: 409 on a duplicate email, 401 on a bad
        # password, 422 on validation. Roll back any partial work, but do not
        # log it as a database fault. Logging these at ERROR buries the real
        # failures underneath thousands of routine ones.
        db.rollback()
        raise
    except Exception:
        # exc_info gives the full traceback rather than str(e), which on a
        # database error is a single line missing the frames that matter.
        logger.error("Database session error", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()