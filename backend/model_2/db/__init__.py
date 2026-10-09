"""
JalDrishti Database V1 Module.
PostgreSQL + PostGIS integration for Shiggaon Watershed Intelligence System.
"""

from .config import settings, DatabaseSettings
from .models import (
    Base,
    MicroWatershed,
    RiskHistory,
    IoTReading,
    Intervention,
    Alert,
    WatershedGeometry,
)
from .session import engine, SessionLocal, get_db, check_db_connection
from .init_db import init_database
from .sync import sync_authoritative_data

__all__ = [
    "settings",
    "DatabaseSettings",
    "Base",
    "MicroWatershed",
    "RiskHistory",
    "IoTReading",
    "Intervention",
    "Alert",
    "WatershedGeometry",
    "engine",
    "SessionLocal",
    "get_db",
    "check_db_connection",
    "init_database",
    "sync_authoritative_data",
]
