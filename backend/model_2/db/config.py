"""
JalDrishti Database V1 Configuration.

Reads PostgreSQL and PostGIS connection settings from environment variables.
Provides connection URL formatting, pooling parameters, and fallback safety.
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus


# Determine project root (.env location)
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"

# Load .env if present (without external dependencies like python-dotenv)
if ENV_FILE.exists():
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


class DatabaseSettings:
    """PostgreSQL + PostGIS connection configuration."""

    # Credentials & Connection
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "jaldrishti")

    # Direct database URL override (e.g. Supabase, Neon, AWS RDS, Docker)
    _DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

    # Connection pool tuning
    POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("true", "1", "yes")
    ECHO_SQL: bool = os.getenv("DB_ECHO_SQL", "false").lower() in ("true", "1", "yes")

    # Auto sync on startup (defaults to False to prevent blocking startup when DB is offline)
    AUTO_SYNC_ON_STARTUP: bool = os.getenv("DB_AUTO_SYNC_ON_STARTUP", "false").lower() in ("true", "1", "yes")

    @property
    def user(self) -> str:
        return os.getenv("POSTGRES_USER", self.POSTGRES_USER)

    @property
    def password(self) -> str:
        return os.getenv("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)

    @property
    def host(self) -> str:
        return os.getenv("POSTGRES_HOST", self.POSTGRES_HOST)

    @property
    def port(self) -> int:
        return int(os.getenv("POSTGRES_PORT", str(self.POSTGRES_PORT)))

    @property
    def database(self) -> str:
        return os.getenv("POSTGRES_DB", self.POSTGRES_DB)

    @property
    def database_url(self) -> str:
        """
        Returns authoritative SQLAlchemy connection URL.
        Defaults to standard postgresql+psycopg2 driver.
        """
        db_url = os.getenv("DATABASE_URL") or self._DATABASE_URL
        if db_url:
            # Normalize legacy 'postgres://' schema to 'postgresql://' for SQLAlchemy 1.4+
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
                db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return db_url

        escaped_password = quote_plus(self.password)
        return (
            f"postgresql+psycopg2://{self.user}:{escaped_password}@"
            f"{self.host}:{self.port}/{self.database}"
        )

    @property
    def safe_connection_info(self) -> dict:
        """Returns connection metadata with password redacted for health checks."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "driver": "postgresql+psycopg2",
            "pool_size": self.POOL_SIZE,
            "pool_pre_ping": self.POOL_PRE_PING,
        }


settings = DatabaseSettings()
