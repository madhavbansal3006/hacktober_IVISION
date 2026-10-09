from fastapi import APIRouter, HTTPException, Request, Query
from typing import Optional
from ..schemas import IoTReading, LiveRiskResult

router = APIRouter(prefix="/telemetry", tags=["IoT & Telemetry"])

def get_engine(request: Request):
    return request.app.state.adapters["iot_engine"]

def get_gis(request: Request):
    return request.app.state.adapters["gis"]

@router.get("/latest", response_model=Optional[LiveRiskResult])
def get_latest_telemetry(
    request: Request,
    watershed_id: Optional[str] = Query(None, description="Filter by micro-watershed GIS ID or display code"),
    mws_code: Optional[str] = Query(None, description="Filter by micro-watershed human code (e.g. 4D4F2m3)"),
    device_id: Optional[str] = Query(None, description="Filter by ESP32 device hardware ID")
):
    """
    Returns the latest live sensor telemetry and compound risk calculation.
    Supports filtering by specific micro-watershed or ESP32 device.
    Returns 404 if no physical hardware telemetry has arrived yet.
    """
    engine = get_engine(request)
    gis = get_gis(request)

    target_id = watershed_id
    if not target_id and mws_code:
        target_id = gis.get_mws_to_id_map().get(mws_code, mws_code)

    latest = engine.get_latest(watershed_id=target_id, device_id=device_id)
    if latest is None:
        raise HTTPException(
            status_code=404, 
            detail="No sensor telemetry currently available. Waiting for live telemetry."
        )
    return latest

@router.post("", response_model=LiveRiskResult)
def ingest_telemetry(reading: IoTReading, request: Request):
    """
    Ingests live sensor reading from ESP32, identifies device, resolves catchment,
    immediately executes Model 2 Isolation Forest ML anomaly scoring and
    compound event classification, and records latest production telemetry state.
    """
    engine = get_engine(request)
    gis = get_gis(request)

    # Resolve catchment identifier (handles id, mws_code, or defaults to golden catchment)
    raw_id = reading.id or reading.mws_code or "g_mws.240575"
    mws_code = gis.get_id_to_mws_map().get(raw_id)
    if mws_code:
        reading.id = raw_id
        reading.mws_code = mws_code
    else:
        actual_id = gis.get_mws_to_id_map().get(raw_id)
        if actual_id:
            mws_code = raw_id
            reading.id = actual_id
            reading.mws_code = mws_code
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown micro-watershed '{raw_id}'. Catchment not found in official catalog."
            )

    result = engine.infer(reading, persist=True, mws_code=mws_code)
    return result

@router.post("/infer", response_model=LiveRiskResult)
def simulate_telemetry_inference(reading: IoTReading, request: Request):
    """
    Executes live Model 2 ML inference on synthetic/simulation sensor inputs
    WITHOUT mutating the active production gateway telemetry state.
    Satisfies the requirement: Simulation mode uses real model pipeline with synthetic inputs.
    """
    engine = get_engine(request)
    gis = get_gis(request)

    raw_id = reading.id or reading.mws_code or "g_mws.240575"
    mws_code = gis.get_id_to_mws_map().get(raw_id)
    if mws_code:
        reading.id = raw_id
        reading.mws_code = mws_code
    else:
        actual_id = gis.get_mws_to_id_map().get(raw_id)
        if actual_id:
            mws_code = raw_id
            reading.id = actual_id
            reading.mws_code = mws_code
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown micro-watershed '{raw_id}'. Catchment not found in official catalog."
            )

    result = engine.infer(reading, persist=False, mws_code=mws_code)
    return result
