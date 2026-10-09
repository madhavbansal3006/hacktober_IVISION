from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any

from ..schemas import WatershedCropAdvisory, CropRecommendation
from ..adapters.crop_advisor_adapter import REGIONAL_CROPS

router = APIRouter(prefix="/crops", tags=["Crop Intelligence"])

@router.get("/catalog")
def get_crop_catalog():
    """
    Returns the authoritative regional crop catalog for the Shiggaon / Haveri basin,
    detailing water requirements, drought resistance, salinity tolerances, and GI credentials.
    """
    return {
        "region": "Shiggaon Taluk, Haveri District (Karnataka Zone 8)",
        "total_crops": len(REGIONAL_CROPS),
        "crops": REGIONAL_CROPS
    }

@router.get("/{mws_identifier}", response_model=WatershedCropAdvisory)
def get_watershed_crop_suggestions(mws_identifier: str, request: Request):
    """
    Returns calibrated crop recommendations, water condition assessment, caution crops,
    and conservation practices for a micro-watershed (by canonical ID or display code).
    """
    adapter = request.app.state.adapters.get("crop_advisor")
    if not adapter:
        raise HTTPException(status_code=500, detail="Crop advisor adapter not initialized")

    advisory = adapter.get_crop_advisory(mws_identifier)
    if not advisory:
        raise HTTPException(
            status_code=404,
            detail=f"Micro-watershed '{mws_identifier}' not found in official catalog"
        )
    return advisory
