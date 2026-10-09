from fastapi import APIRouter, Request, Query, HTTPException, Path, UploadFile, File
from typing import List, Optional
import logging
from ..schemas import EvidenceItem, BatchUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Field Observations"])

@router.post(
    "/field-observations/upload",
    response_model=BatchUploadResponse,
    summary="Upload and ingest geotagged field photos"
)
@router.post(
    "/field-observations/ingest",
    response_model=BatchUploadResponse,
    include_in_schema=False
)
async def upload_field_photos(
    request: Request,
    files: List[UploadFile] = File(..., description="Geotagged field photographs (JPG, JPEG, PNG)")
):
    """
    Ingests and validates batch field photos through the Geo-Coded pipeline:
    EXIF GPS extraction -> coordinate validation -> Shiggaon boundary check ->
    66-MWS polygon lookup -> Sentinel-2 LULC query -> flat-file persistence.
    Returns per-image results, status category breakdown, and updated ledger.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    geo_adapter = request.app.state.adapters["geocoded"]

    file_tuples = []
    for file in files:
        content = await file.read()
        file_tuples.append((file.filename or "unknown.jpg", content))

    response = geo_adapter.upload_and_process_photos(file_tuples)
    return response

@router.get("/field-observations", response_model=List[EvidenceItem], summary="List processed field observations")
@router.get("/evidence", response_model=List[EvidenceItem], include_in_schema=False)
def list_field_observations(
    request: Request,
    watershed_id: Optional[str] = Query(None, description="Optional filter by micro-watershed canonical id (e.g. g_mws.240575) or display code (e.g. 4D4F2m3)")
):
    """
    Returns processed field observations with EXIF coordinates, boundary checks,
    canonical MWS lookup, and LULC contextual classifications.
    Returns honest empty list when no field surveys have been conducted.
    """
    geo_adapter = request.app.state.adapters["geocoded"]
    gis_adapter = request.app.state.adapters["gis"]

    if watershed_id:
        # Validate that the requested watershed exists in the official GIS catalog
        mws_meta = gis_adapter.get_mws_meta(watershed_id)
        if not mws_meta:
            raise HTTPException(
                status_code=404,
                detail=f"Micro-watershed '{watershed_id}' not found in official GIS catalog."
            )
        return geo_adapter.get_by_watershed(watershed_id)

    return geo_adapter.get_all()

@router.get("/field-observations/mws/{id}", response_model=List[EvidenceItem], summary="Get observations for a specific micro-watershed")
def get_field_observations_for_mws(
    id: str,
    request: Request
):
    """
    Returns observations linked to a specific micro-watershed by canonical id (e.g. g_mws.240575)
    or display code (e.g. 4D4F2m3). Returns 404 if MWS is unknown in the GIS catalog.
    """
    gis_adapter = request.app.state.adapters["gis"]
    geo_adapter = request.app.state.adapters["geocoded"]

    mws_meta = gis_adapter.get_mws_meta(id)
    if not mws_meta:
        raise HTTPException(
            status_code=404,
            detail=f"Micro-watershed '{id}' not found in official GIS catalog."
        )
    return geo_adapter.get_by_watershed(id)

@router.get("/field-observations/{image_id}", response_model=EvidenceItem, summary="Get single field observation by image ID")
def get_field_observation_by_id(
    image_id: str,
    request: Request
):
    """
    Returns single field observation record by permanent ledger image ID (e.g. IMG_0001).
    Returns 404 if observation does not exist.
    """
    geo_adapter = request.app.state.adapters["geocoded"]
    item = geo_adapter.get_by_image_id(image_id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"Field observation '{image_id}' not found."
        )
    return item
