# db/session.py - Database session factory with automatic SQLite WAL mode configuration
import os
import sys
import logging
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.models import Base

logger = logging.getLogger("DatabaseSession")

DEFAULT_DB_PATH = BASE_DIR / "healthcare.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Ensure db directory exists
if DATABASE_URL.startswith("sqlite"):
    db_file_path = DATABASE_URL.replace("sqlite:///", "")
    Path(db_file_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)

# Enable SQLite WAL (Write-Ahead Logging) mode and foreign keys for high-concurrency read/write
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine))

def init_db():
    """Initializes schema and tables."""
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at {DATABASE_URL} with WAL mode.")

@contextmanager
def get_db():
    """Context manager for scoped database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
