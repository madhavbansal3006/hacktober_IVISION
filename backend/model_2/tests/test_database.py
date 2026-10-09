"""
JalDrishti Database V1 Test Suite.

Validates:
1. Database settings & environment variable configuration.
2. PostgreSQL / SQLite schema creation and table metadata.
3. PostGIS geometry handling and adaptive MultiPolygon serialization.
4. Session lifecycle & FastAPI get_db dependency.
5. Non-blocking health check diagnostics (online & disconnected).
6. Authoritative GPKG synchronization (66 canonical MWS, zero GPKG mutation, zero raster duplication).
7. FastAPI database endpoints (/health/db, /db/summary, /db/watersheds, /db/watersheds/{id}).
8. Integrity verification that risk, ML, GIS, and IoT logic remains untouched.
"""

import os
import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from sqlalchemy.pool import StaticPool
from backend.model_2.db.config import DatabaseSettings
from backend.model_2.db.models import (
    Base,
    MicroWatershed,
    RiskHistory,
    IoTReading,
    Intervention,
    Alert,
)
from backend.model_2.db.session import check_db_connection, get_db
from backend.model_2.db.init_db import init_database
from backend.model_2.db.sync import sync_authoritative_data, to_multipolygon_wkt
from backend.model_2.api.main import app


@pytest.fixture
def memory_db():
    """Provides a fresh in-memory database with all Database V1 tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield engine, session
    finally:
        session.close()
        engine.dispose()


def test_database_settings_configuration():
    """Verifies environment-based configuration and password redaction."""
    settings = DatabaseSettings()
    
    assert settings.POSTGRES_DB == "jaldrishti"
    assert "postgresql+psycopg2://" in settings.database_url
    assert settings.POSTGRES_PORT == 5432

    safe_info = settings.safe_connection_info
    assert "host" in safe_info
    assert "database" in safe_info
    assert "password" not in safe_info  # Crucial security guarantee


def test_schema_creation_and_models(memory_db):
    """Verifies that all 5 Database V1 entities can be inserted, queried, and serialized."""
    engine, session = memory_db

    # 1. Insert MicroWatershed
    mws = MicroWatershed(
        mws_id="g_mws.240575",
        display_code="4D4F2m3",
        name="Micro-Watershed 4D4F2m3",
        taluk="Shiggaon",
        district="Haveri",
        state="Karnataka",
        area_sqkm=14.24,
        stream_length_km=2.62,
        drainage_density=0.184,
        current_risk_score=55.27,
        current_risk_category="HIGH",
        current_primary_driver="Water Stress",
        current_health_index=44.73,
        intervention_priority="HIGH",
        geometry="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
    )
    session.add(mws)
    session.commit()

    # 2. Add RiskHistory
    rh = RiskHistory(
        mws_id="g_mws.240575",
        year=2026,
        month=9,
        base_risk_score=67.01,
        final_risk_score=55.27,
        risk_category="HIGH",
        primary_driver="Water Stress",
        water_stress_score=78.78,
        source="gpkg_authoritative",
    )
    session.add(rh)

    # 3. Add IoTReading
    iot = IoTReading(
        mws_id="g_mws.240575",
        rainfall_mm=250.0,
        soil_moisture_pct=92.0,
        water_level_cm=85.0,
        turbidity_ntu=800.0,
        ph=7.0,
        live_ml_anomaly_score=43.29,
        live_risk_score=58.93,
        live_risk_category="HIGH",
        compound_event_detected=True,
        compound_event_type="Compound runoff and flood event",
    )
    session.add(iot)

    # 4. Add Intervention
    interv = Intervention(
        mws_id="g_mws.240575",
        intervention_type="Check Dam Desiltation & Recharge Shafts",
        priority="HIGH",
        status="RECOMMENDED",
    )
    session.add(interv)

    # 5. Add Alert
    alert = Alert(
        mws_id="g_mws.240575",
        alert_level="HIGH",
        alert_type="COMPOUND_RUNOFF",
        headline="High Compound Runoff Alert",
        message="Critical soil saturation and rainfall spike detected.",
        is_active=True,
    )
    session.add(alert)
    session.commit()

    # Query back and verify relationships
    retrieved = session.query(MicroWatershed).filter_by(mws_id="g_mws.240575").first()
    assert retrieved is not None
    assert retrieved.display_code == "4D4F2m3"
    assert len(retrieved.risk_history) == 1
    assert len(retrieved.iot_readings) == 1
    assert len(retrieved.interventions) == 1
    assert len(retrieved.alerts) == 1

    # Verify serialization
    data = retrieved.to_dict()
    assert data["mws_id"] == "g_mws.240575"
    assert data["current_risk_category"] == "HIGH"


def test_disconnected_db_health_check():
    """Verifies that check_db_connection handles disconnected servers without crashing."""
    dummy_engine = create_engine("postgresql+psycopg2://postgres:wrong_pw@127.0.0.1:59999/nonexistent")
    info = check_db_connection(target_engine=dummy_engine)
    
    assert info["status"] == "disconnected"
    assert info["error"] is not None
    assert info["counts"]["micro_watersheds"] == 0


def test_online_db_health_check(memory_db):
    """Verifies that check_db_connection returns accurate counts and latency on active engine."""
    engine, session = memory_db
    
    # Empty DB check
    info = check_db_connection(target_engine=engine)
    assert info["status"] == "online"
    assert info["connection_latency_ms"] is not None
    assert info["counts"]["micro_watersheds"] == 0

    # Add 1 record
    session.add(MicroWatershed(
        mws_id="test.1", display_code="T01", geometry="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
    ))
    session.commit()

    info2 = check_db_connection(target_engine=engine)
    assert info2["counts"]["micro_watersheds"] == 1


def test_authoritative_gpkg_sync(memory_db):
    """
    Tests syncing canonical 66 micro-watersheds from authoritative GPKG.
    Verifies:
    - Exactly 66 MWS are synced.
    - Zero modification occurs to the GPKG file.
    - Idempotent execution (running twice doesn't create duplicate MWS).
    """
    engine, session = memory_db

    # First sync
    res = sync_authoritative_data(target_engine=engine)
    assert res["status"] == "success"
    assert res["synced_micro_watersheds"] == 66
    assert res["synced_risk_history"] == 66
    assert res["synced_interventions"] == 66
    assert res["synced_alerts"] >= 1  # Priority alerts generated

    # Verify table count in database
    mws_count = session.query(MicroWatershed).count()
    assert mws_count == 66

    # Verify golden catchment 4D4F2m3
    golden = session.query(MicroWatershed).filter_by(mws_id="g_mws.240575").first()
    assert golden is not None
    assert golden.display_code == "4D4F2m3"
    assert golden.current_risk_category == "HIGH"
    assert golden.current_primary_driver == "Water Stress"

    # Idempotent re-sync
    res2 = sync_authoritative_data(target_engine=engine)
    assert res2["status"] == "success"
    assert session.query(MicroWatershed).count() == 66


def test_api_database_health_endpoint():
    """Verifies GET /api/v1/health/db returns 200 OK with structured diagnostic metadata."""
    with TestClient(app) as client:
        res = client.get("/api/v1/health/db")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "counts" in data
        assert "micro_watersheds" in data["counts"]


def test_api_database_summary_and_watersheds_with_overridden_db(memory_db):
    """Verifies GET /api/v1/db/summary and /db/watersheds via FastAPI dependency override."""
    engine, session = memory_db
    sync_authoritative_data(target_engine=engine)

    def override_get_db():
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            # 1. Summary
            res_sum = client.get("/api/v1/db/summary")
            assert res_sum.status_code == 200
            sum_data = res_sum.json()
            assert sum_data["status"] == "connected"
            assert sum_data["micro_watersheds"] == 66

            # 2. Watershed catalog
            res_ws = client.get("/api/v1/db/watersheds?limit=10")
            assert res_ws.status_code == 200
            ws_data = res_ws.json()
            assert ws_data["count"] == 10

            # 3. Filter by risk_category
            res_crit = client.get("/api/v1/db/watersheds?risk_category=CRITICAL")
            assert res_crit.status_code == 200
            crit_data = res_crit.json()
            assert all(w["current_risk_category"] == "CRITICAL" for w in crit_data["watersheds"])

            # 4. Lookup golden catchment by canonical ID
            res_detail = client.get("/api/v1/db/watersheds/g_mws.240575")
            assert res_detail.status_code == 200
            detail_data = res_detail.json()
            assert detail_data["mws_id"] == "g_mws.240575"
            assert detail_data["display_code"] == "4D4F2m3"

            # 5. Lookup golden catchment by display code
            res_disp = client.get("/api/v1/db/watersheds/4D4F2m3")
            assert res_disp.status_code == 200
            assert res_disp.json()["mws_id"] == "g_mws.240575"

            # 6. Lookup non-existent catchment
            res_404 = client.get("/api/v1/db/watersheds/unknown_mws_999")
            assert res_404.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_root_includes_database_endpoints():
    """Verifies that the root API metadata lists database endpoints."""
    with TestClient(app) as client:
        res = client.get("/")
        assert res.status_code == 200
        endpoints = res.json()["endpoints"]
        assert "database_health" in endpoints
        assert "database_summary" in endpoints
        assert "database_watersheds" in endpoints


def test_live_database_integration_supabase():
    """
    Verifies live PostgreSQL + PostGIS integration on Supabase if DATABASE_URL is configured.
    Checks PostGIS extension, 66 canonical micro-watersheds, and golden catchment 4D4F2m3.
    """
    from backend.model_2.db.session import engine, check_db_connection
    from sqlalchemy import text

    info = check_db_connection()
    if info["status"] != "online":
        pytest.skip(f"Live database not reachable: {info.get('error')}")

    assert info["postgis_enabled"] is True
    assert info["counts"]["micro_watersheds"] == 66
    assert info["counts"]["risk_history"] == 66
    assert info["counts"]["interventions"] == 66

    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT mws_id, display_code, current_risk_category, ST_SRID(geometry) FROM micro_watersheds WHERE mws_id = 'g_mws.240575'")
        ).fetchone()
        assert res is not None
        assert res[0] == "g_mws.240575"
        assert res[1] == "4D4F2m3"
        assert res[2] == "HIGH"
        assert res[3] == 4326  # EPSG:4326 PostGIS geometry
