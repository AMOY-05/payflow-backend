from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging

logger = logging.getLogger("fintech.database")

# Build connection URL
database_url = settings.DATABASE_URL

# Fix postgres:// to postgresql:// for SQLAlchemy compatibility
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Connection arguments for production SSL
connect_args = {}
if "render.com" in database_url or "sslmode=require" in database_url:
    connect_args = {
        "sslmode": "require",
        "connect_timeout": 30,
    }

engine = create_engine(
    database_url,
    pool_pre_ping=True,          # Test connection before using
    pool_recycle=300,            # Recycle connections every 5 minutes
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
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()