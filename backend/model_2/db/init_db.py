"""
JalDrishti Database V1 Initialization Utility.

Handles:
1. Verifying database connection.
2. Enabling PostGIS extension on PostgreSQL (CREATE EXTENSION IF NOT EXISTS postgis).
3. Creating all SQLAlchemy tables for Database V1.
4. CLI execution with optional --sync flag to seed authoritative micro-watersheds.
"""

import sys
import argparse
import logging
from typing import Dict, Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import settings
from .session import engine
from .models import Base
from .sync import sync_authoritative_data

logger = logging.getLogger(__name__)


def init_database(target_engine=None, sync_data: bool = False) -> Dict[str, Any]:
    """
    Initializes the JalDrishti Database V1 schema.
    Creates PostGIS extension if running on PostgreSQL, and generates all tables.
    Optionally syncs authoritative micro-watershed data.
    """
    active_engine = target_engine or engine
    result: Dict[str, Any] = {
        "status": "success",
        "dialect": active_engine.dialect.name,
        "database": getattr(active_engine.url, "database", settings.POSTGRES_DB),
        "postgis_extension": False,
        "tables_created": [],
        "synced": False,
        "sync_stats": None,
        "error": None,
    }

    try:
        # 1. Enable PostGIS extension on PostgreSQL
        if active_engine.dialect.name == "postgresql":
            try:
                with active_engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                    conn.commit()
                result["postgis_extension"] = True
                logger.info("PostGIS extension confirmed/created successfully.")
            except Exception as e:
                logger.warning(f"Could not create PostGIS extension (may lack superuser or already exists): {e}")
                result["postgis_extension"] = False

        # 2. Create all tables
        Base.metadata.create_all(bind=active_engine)
        result["tables_created"] = list(Base.metadata.tables.keys())
        logger.info(f"Database tables initialized: {result['tables_created']}")

        # 3. Optional sync
        if sync_data:
            sync_res = sync_authoritative_data(target_engine=active_engine)
            result["synced"] = True
            result["sync_stats"] = sync_res

    except SQLAlchemyError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        logger.error(f"Failed to initialize database: {exc}")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Initialize JalDrishti Database V1")
    parser.add_argument("--sync", action="store_true", help="Sync authoritative micro-watershed data after initialization")
    args = parser.parse_args()

    res = init_database(sync_data=args.sync)
    print("\nDatabase V1 Initialization Result:")
    for k, v in res.items():
        print(f"  {k}: {v}")
    if res["status"] != "success":
        sys.exit(1)
