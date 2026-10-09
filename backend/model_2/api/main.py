from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import json
from datetime import datetime
import logging

from .schemas import IoTReading, LULCSummary
from .adapters.model1_adapter import Model1Adapter
from .adapters.gis_adapter import GISAdapter
from .adapters.model2_adapter import Model2Adapter
from .adapters.iot_inference_engine import LiveIoTInferenceEngine
from .adapters.geocoded_adapter import GeoCodedAdapter
from .adapters.water_quality_adapter import WaterQualityAdapter
from .adapters.reports_adapter import ReportsAdapter
from .adapters.crop_advisor_adapter import CropAdvisorAdapter

from .routes.watersheds import router as watersheds_router
from .routes.telemetry import router as telemetry_router
from .routes.evidence import router as evidence_router
from .routes.gis import router as gis_router
from .routes.water_quality import router as water_quality_router
from .routes.reports import router as reports_router
from .routes.database import router as database_router
from .routes.crops import router as crops_router
from .routes.ai import router as ai_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WatershedAPI")

BASE_DIR = Path(__file__).resolve().parent.parent
LIVE_DATA_PATH = BASE_DIR / "Data" / "live" / "iot_live_data.json"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load data adapters and trained models on startup.
    Keeps memory footprint efficient and ensures single load of models.
    """
    logger.info("Initializing Watershed Intelligence System adapters...")
    gis_inst = GISAdapter()
    m1_inst = Model1Adapter()
    m2_inst = Model2Adapter()
    iot_inst = LiveIoTInferenceEngine()
    geo_inst = GeoCodedAdapter()
    wq_inst = WaterQualityAdapter(gis_adapter=gis_inst, iot_engine=iot_inst)
    crop_inst = CropAdvisorAdapter(
        gis_adapter=gis_inst,
        model1_adapter=m1_inst,
        model2_adapter=m2_inst,
        water_quality_adapter=wq_inst,
    )
    rep_inst = ReportsAdapter(
        gis_adapter=gis_inst,
        model1_adapter=m1_inst,
        model2_adapter=m2_inst,
        water_quality_adapter=wq_inst,
        iot_engine=iot_inst,
        geocoded_adapter=geo_inst
    )

    app.state.adapters = {
        "model1": m1_inst,
        "gis": gis_inst,
        "model2": m2_inst,
        "iot_engine": iot_inst,
        "geocoded": geo_inst,
        "water_quality": wq_inst,
        "reports": rep_inst,
        "crop_advisor": crop_inst,
    }
    logger.info("All adapters and live inference engines loaded successfully.")
    yield
    logger.info("Shutting down Watershed Intelligence API.")

app = FastAPI(
    title="Shiggaon Watershed Intelligence API",
    description="Unified API integrating Sentinel-2 LULC (Model 1), Risk & Interventions (Model 2), GIS, Geo-Coded Evidence, Live IoT, and Water Quality.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Versioned Routers (/api/v1/...)
app.include_router(watersheds_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(gis_router, prefix="/api/v1")
app.include_router(water_quality_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(database_router, prefix="/api/v1")
app.include_router(crops_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")

@app.get("/api/v1/lulc/summary", response_model=LULCSummary, tags=["LULC"])
def get_lulc_summary_root(request: Request):
    """
    Returns authoritative Model 1 LULC classification summary, 66-MWS coverage, and confidence.
    """
    return request.app.state.adapters["model1"].get_lulc_summary()

@app.get("/")
def home():
    """System health check and overview."""
    return {
        "status": "online",
        "system": "Shiggaon Watershed Intelligence System API",
        "api_version": "v1",
        "endpoints": {
            "watersheds": "/api/v1/watersheds",
            "basin_summary": "/api/v1/watersheds/basin/summary",
            "crops": "/api/v1/crops/{id}",
            "crops_catalog": "/api/v1/crops/catalog",
            "telemetry_latest": "/api/v1/telemetry/latest",
            "telemetry_ingest": "POST /api/v1/telemetry",
            "telemetry_simulation": "POST /api/v1/telemetry/infer",
            "evidence": "/api/v1/evidence",
            "field_observations": "/api/v1/field-observations",
            "field_observation_id": "/api/v1/field-observations/{image_id}",
            "field_observation_mws": "/api/v1/field-observations/mws/{id}",
            "mws_boundaries": "/api/v1/gis/mws-boundaries",
            "study_area": "/api/v1/gis/study-area",
            "water_quality_summary": "/api/v1/water-quality/summary",
            "water_quality_mws": "/api/v1/water-quality/{id}",
            "reports_basin": "/api/v1/reports/basin",
            "reports_basin_csv": "/api/v1/reports/basin/csv",
            "reports_mws": "/api/v1/reports/mws/{id}",
            "reports_mws_csv": "/api/v1/reports/mws/{id}/csv",
            "database_health": "/api/v1/health/db",
            "database_summary": "/api/v1/db/summary",
            "database_watersheds": "/api/v1/db/watersheds",
            "ask_ai": "POST /api/v1/ai/ask",
            "legacy_iot": "POST /iot-data"
        }
    }

@app.post("/iot-data")
def receive_iot_data(reading: IoTReading):
    """
    Preserved legacy endpoint for backwards compatibility.
    Now actively executes Model 2 Isolation Forest inference in addition to persisting data.
    """
    data = reading.model_dump()
    now = datetime.now()
    data["year"] = reading.year or now.year
    data["month"] = reading.month or now.month
    data["timestamp"] = reading.timestamp or now.isoformat()

    LIVE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LIVE_DATA_PATH, "w") as f:
        json.dump(data, f, indent=4)

    # Actively run live Model 2 ML inference
    iot_engine = app.state.adapters["iot_engine"]
    gis = app.state.adapters["gis"]
    mws_code = gis.get_id_to_mws_map().get(reading.id)
    
    live_result = iot_engine.infer(reading, persist=True, mws_code=mws_code)

    return {
        "status": "success",
        "message": "IoT data received and live Model 2 inference executed successfully",
        "data": data,
        "inference": live_result.model_dump()
    }