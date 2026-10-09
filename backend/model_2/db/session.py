"""
JalDrishti Database V1 Session & Connection Management.

Provides connection pooling, FastAPI dependency injection, and health verification.
"""

import time
import logging
from typing import Generator, Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .config import settings
from .models import Base, MicroWatershed, RiskHistory, IoTReading, Intervention, Alert

logger = logging.getLogger(__name__)

# Create PostgreSQL connection engine with robust pool settings
try:
    engine = create_engine(
        settings.database_url,
        pool_size=settings.POOL_SIZE,
        max_overflow=settings.MAX_OVERFLOW,
        pool_timeout=settings.POOL_TIMEOUT,
        pool_pre_ping=settings.POOL_PRE_PING,
        echo=settings.ECHO_SQL,
    )
except Exception as e:
    logger.warning(f"Database engine initialization deferred or fallback: {e}")
    # Create fallback engine that does not immediately crash
    engine = create_engine("sqlite:///:memory:", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields an independent database session per request
    and ensures clean closure upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection(target_engine=None) -> Dict[str, Any]:
    """
    Performs a non-blocking diagnostic health check against the PostgreSQL database.
    Verifies connection latency, PostGIS extension status, and table record counts.
    Returns structured health metadata without raising exceptions.
    """
    check_engine = target_engine or engine
    start_time = time.perf_counter()
    info: Dict[str, Any] = {
        "status": "disconnected",
        "database": getattr(check_engine.url, "database", settings.database),
        "host": getattr(check_engine.url, "host", settings.host),
        "port": getattr(check_engine.url, "port", settings.port),
        "driver": getattr(check_engine.url, "drivername", "postgresql+psycopg2"),
        "postgis_enabled": False,
        "postgis_version": None,
        "counts": {
            "micro_watersheds": 0,
            "risk_history": 0,
            "iot_readings": 0,
            "interventions": 0,
            "alerts": 0,
        },
        "connection_latency_ms": None,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with check_engine.connect() as conn:
            # 1. Basic Ping
            conn.execute(text("SELECT 1;"))
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            info["status"] = "online"
            info["connection_latency_ms"] = latency_ms

            # 2. Check PostGIS extension (for PostgreSQL)
            if check_engine.dialect.name == "postgresql":
                try:
                    pgis_res = conn.execute(text("SELECT PostGIS_Version();")).scalar()
                    if pgis_res:
                        info["postgis_enabled"] = True
                        info["postgis_version"] = str(pgis_res)
                except Exception:
                    # Fallback check on pg_available_extensions
                    try:
                        ext_res = conn.execute(
                            text("SELECT installed_version FROM pg_available_extensions WHERE name = 'postgis';")
                        ).scalar()
                        if ext_res:
                            info["postgis_enabled"] = True
                            info["postgis_version"] = f"postgis {ext_res}"
                    except Exception:
                        info["postgis_enabled"] = False

            # 3. Retrieve Record Counts
            for table_key, model_cls in [
                ("micro_watersheds", MicroWatershed),
                ("risk_history", RiskHistory),
                ("iot_readings", IoTReading),
                ("interventions", Intervention),
                ("alerts", Alert),
            ]:
                try:
                    count_val = conn.execute(
                        text(f"SELECT COUNT(*) FROM {model_cls.__tablename__};")
                    ).scalar()
                    info["counts"][table_key] = int(count_val) if count_val is not None else 0
                except Exception:
                    # Table may not have been created yet
                    info["counts"][table_key] = 0

    except (OperationalError, SQLAlchemyError, Exception) as exc:
        info["status"] = "disconnected"
        info["error"] = str(exc)
        logger.debug(f"Database health check failed (offline or uninitialized): {exc}")

    return info
