from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional

from ..schemas import WaterQualityRecord, WaterQualitySummary

router = APIRouter(prefix="/water-quality", tags=["Water Quality"])

@router.get("/summary", response_model=WaterQualitySummary)
def get_water_quality_summary(request: Request, mode: Optional[str] = None):
    """
    Returns basin-wide water quality summary across all 66 micro-watersheds,
    including WQI category distributions and parameter standards.
    When mode == 'live', incorporates active real-time ESP32 IoT node telemetry.
    """
    adapter = request.app.state.adapters.get("water_quality")
    if not adapter:
        raise HTTPException(status_code=500, detail="Water Quality adapter not initialized")
    return adapter.get_water_quality_summary(mode=mode)

@router.get("/{mws_identifier}", response_model=WaterQualityRecord)
def get_water_quality_mws(mws_identifier: str, request: Request, mode: Optional[str] = None):
    """
    Returns water-quality readings and Weighted Arithmetic WQI evaluation for a given micro-watershed.
    When mode == 'live', streams live sensor readings from physical ESP32 hardware when connected.
    """
    adapter = request.app.state.adapters.get("water_quality")
    if not adapter:
        raise HTTPException(status_code=500, detail="Water Quality adapter not initialized")

    record = adapter.get_mws_reading(mws_identifier, mode=mode)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Micro-watershed '{mws_identifier}' not found in official 66 MWS catalog"
        )
    return record
