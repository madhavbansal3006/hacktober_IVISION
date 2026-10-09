from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Dict, Optional
from ..schemas import (
    WatershedSummary,
    WatershedDetail,
    WatershedLULC,
    WatershedRisk,
    WatershedInterventions,
    BasinSummary,
    LULCSummary,
    WatershedCropAdvisory,
)

router = APIRouter(prefix="/watersheds", tags=["Watersheds"])

def get_adapters(request: Request):
    return request.app.state.adapters

@router.get("", response_model=List[WatershedSummary])
def list_watersheds(request: Request):
    """
    Returns all 66 micro-watersheds with summary metrics and health indices.
    Enforces MWS Contract: id is GIS join key, MWS is display code.
    """
    adapters = get_adapters(request)
    gis_adapter = adapters["gis"]
    model1_adapter = adapters["model1"]
    model2_adapter = adapters["model2"]

    id_to_mws = gis_adapter.get_id_to_mws_map()
    all_gis_meta = gis_adapter.get_all_mws_meta()
    all_lulc = model1_adapter.get_all()
    all_risk = model2_adapter.get_all_risk()

    summaries = []
    # Loop over all 66 official MWS
    for mws_id, mws_code in id_to_mws.items():
        meta = all_gis_meta.get(mws_id, {})
        lulc = all_lulc.get(mws_id)
        risk = all_risk.get(mws_id)
        features = model2_adapter.get_features(mws_id)

        area_km2 = meta.get("area_km2")
        dominant_class = lulc.dominant_class if lulc else None
        final_risk = risk.final_risk_score if risk else None
        risk_cat = risk.risk_category if risk else None
        health_index = round(100.0 - final_risk, 1) if final_risk is not None else None
        primary_driver = (
            risk.primary_risk_driver
            if risk and risk.primary_risk_driver and risk.primary_risk_driver != "None"
            else meta.get("primary_driver")
        )
        intervention_priority = meta.get("intervention_priority") or risk_cat
        stream_len = (
            features.get("stream_length_km")
            if features and features.get("stream_length_km") is not None
            else meta.get("stream_len_km")
        )

        iv = model2_adapter.get_interventions(mws_id)
        primary_intervention = iv.primary_intervention if iv else None

        driver_score = None
        if risk and primary_driver:
            drv_lower = primary_driver.lower()
            if "water" in drv_lower or "stress" in drv_lower:
                driver_score = risk.water_stress_score
            elif "flood" in drv_lower or "runoff" in drv_lower:
                driver_score = risk.flood_risk_score
            elif "eco" in drv_lower:
                driver_score = risk.ecosystem_risk_score
            elif "anomaly" in drv_lower or "ml" in drv_lower:
                driver_score = risk.ml_anomaly_score

        summaries.append(
            WatershedSummary(
                id=mws_id,
                MWS=mws_code,
                area_km2=area_km2,
                dominant_class=dominant_class,
                final_risk_score=final_risk,
                risk_category=risk_cat,
                health_index=health_index,
                primary_driver=primary_driver,
                driver_score=driver_score,
                intervention_priority=intervention_priority,
                primary_intervention=primary_intervention,
                stream_len_km=stream_len,
                status="available" if risk is not None else "loading"
            )
        )
    return summaries

@router.get("/basin/summary", response_model=BasinSummary)
def get_basin_summary(request: Request):
    """
    Returns high-level executive basin overview metrics for Shiggaon Taluk.
    """
    adapters = get_adapters(request)
    return adapters["model2"].get_basin_summary()

@router.get("/basin/lulc-summary", response_model=LULCSummary)
def get_basin_lulc_summary(request: Request):
    """
    Returns authoritative basin-wide Sentinel-2 LULC classification summary and model confidence.
    """
    adapters = get_adapters(request)
    return adapters["model1"].get_lulc_summary()

@router.get("/{mws_id}", response_model=WatershedDetail)
def get_watershed_profile(mws_id: str, request: Request):
    """
    Returns comprehensive profile for a micro-watershed.
    Accepts either id (e.g. g_mws.240575) or MWS display code (e.g. 4D4F2m3).
    """
    adapters = get_adapters(request)
    gis_adapter = adapters["gis"]
    model1_adapter = adapters["model1"]
    model2_adapter = adapters["model2"]

    # Resolve id <-> MWS
    id_to_mws = gis_adapter.get_id_to_mws_map()
    mws_to_id = gis_adapter.get_mws_to_id_map()

    if mws_id in id_to_mws:
        actual_id = mws_id
        actual_mws = id_to_mws[mws_id]
    elif mws_id in mws_to_id:
        actual_id = mws_to_id[mws_id]
        actual_mws = mws_id
    else:
        raise HTTPException(status_code=404, detail=f"Micro-watershed '{mws_id}' not found among official 66 units.")

    gis_meta = gis_adapter.get_mws_meta(actual_id) or {}
    lulc = model1_adapter.get_by_id(actual_id)
    risk = model2_adapter.get_risk(actual_id)
    interventions = model2_adapter.get_interventions(actual_id)
    features = model2_adapter.get_features(actual_id)
    monthly_trend = model2_adapter.get_monthly_trend(actual_id)

    # Ensure MWS field is populated on risk & interventions
    if risk:
        risk.MWS = actual_mws
    if interventions:
        interventions.MWS = actual_mws

    return WatershedDetail(
        id=actual_id,
        MWS=actual_mws,
        area_km2=gis_meta.get("area_km2"),
        lulc=lulc,
        risk=risk,
        interventions=interventions,
        elevation_mean=features.get("elevation_mean"),
        slope_mean=features.get("slope_mean"),
        stream_length_km=features.get("stream_length_km") or gis_meta.get("stream_len_km"),
        drainage_density=features.get("drainage_density") or gis_meta.get("drainage_density"),
        rainfall_mm=features.get("rainfall_mm"),
        rainfall_anomaly=features.get("rainfall_anomaly"),
        ndvi=features.get("ndvi"),
        ndvi_anomaly=features.get("ndvi_anomaly"),
        monthly_trend=monthly_trend,
        status="available"
    )

@router.get("/{mws_id}/lulc", response_model=WatershedLULC)
def get_watershed_lulc(mws_id: str, request: Request):
    adapters = get_adapters(request)
    lulc = adapters["model1"].get_by_id(mws_id)
    if not lulc:
        raise HTTPException(status_code=404, detail=f"LULC stats not available for '{mws_id}'")
    return lulc

@router.get("/{mws_id}/risk", response_model=WatershedRisk)
def get_watershed_risk(mws_id: str, request: Request):
    adapters = get_adapters(request)
    gis_adapter = adapters["gis"]
    mws_to_id = gis_adapter.get_mws_to_id_map()
    actual_id = mws_to_id.get(mws_id, mws_id)

    risk = adapters["model2"].get_risk(actual_id)
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risk data not available for '{mws_id}'")
    risk.MWS = gis_adapter.get_id_to_mws_map().get(actual_id, "")
    return risk

@router.get("/{mws_id}/interventions", response_model=WatershedInterventions)
def get_watershed_interventions(mws_id: str, request: Request):
    adapters = get_adapters(request)
    gis_adapter = adapters["gis"]
    mws_to_id = gis_adapter.get_mws_to_id_map()
    actual_id = mws_to_id.get(mws_id, mws_id)

    interv = adapters["model2"].get_interventions(actual_id)
    if not interv:
        raise HTTPException(status_code=404, detail=f"Intervention recommendations not available for '{mws_id}'")
    interv.MWS = gis_adapter.get_id_to_mws_map().get(actual_id, "")
    return interv

@router.get("/{mws_id}/crops", response_model=WatershedCropAdvisory)
def get_watershed_crops(mws_id: str, request: Request):
    """
    Returns calibrated crop recommendations, water condition analysis, caution crops,
    and conservation practices for the micro-watershed.
    """
    adapters = get_adapters(request)
    crop_adapter = adapters.get("crop_advisor")
    if not crop_adapter:
        raise HTTPException(status_code=500, detail="Crop advisor adapter not initialized")

    advisory = crop_adapter.get_crop_advisory(mws_id)
    if not advisory:
        raise HTTPException(status_code=404, detail=f"Micro-watershed '{mws_id}' not found in official catalog")
    return advisory
