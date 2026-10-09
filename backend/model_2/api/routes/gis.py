from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter(prefix="/gis", tags=["GIS Layers"])

@router.get("/mws-boundaries")
def get_mws_boundaries(request: Request) -> Dict[str, Any]:
    """
    Returns GeoJSON FeatureCollection of all 66 micro-watershed boundary polygons in WGS84.
    """
    return request.app.state.adapters["gis"].get_mws_geojson()

@router.get("/study-area")
def get_study_area(request: Request) -> Dict[str, Any]:
    """
    Returns GeoJSON FeatureCollection of the official Shiggaon Taluk boundary in WGS84.
    """
    return request.app.state.adapters["gis"].get_boundary_geojson()
