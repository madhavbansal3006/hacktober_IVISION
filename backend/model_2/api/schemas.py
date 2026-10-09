from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator

# Explicit data lifecycle and health states
DataStatus = Literal["available", "loading", "unavailable", "invalid", "no_data"]

class BaseResponse(BaseModel):
    status: DataStatus = "available"
    message: Optional[str] = None

class WatershedSummary(BaseModel):
    id: str = Field(description="Primary internal/system/GIS join key (e.g. g_mws.240575)")
    MWS: str = Field(description="Human-readable hydrological display code (e.g. 4D4F2m3)")
    area_km2: Optional[float] = None
    dominant_class: Optional[str] = None
    final_risk_score: Optional[float] = None
    risk_category: Optional[str] = None
    health_index: Optional[float] = Field(None, description="Inverted normalized health score: 100 - risk")
    primary_driver: Optional[str] = None
    driver_score: Optional[float] = Field(None, description="Score of the primary risk driver (e.g. 78.8 for Water Stress)")
    intervention_priority: Optional[str] = None
    primary_intervention: Optional[str] = Field(None, description="Authoritative primary intervention recommendation")
    stream_len_km: Optional[float] = None
    status: DataStatus = "available"

class WatershedLULC(BaseModel):
    id: str
    MWS: str
    forest_pct: float
    agriculture_pct: float
    water_pct: float
    builtup_pct: float
    barren_pct: float
    coverage_category: str
    coverage_pct: Optional[float] = None
    valid_pixel_count: int
    dominant_class: str
    status: DataStatus = "available"

class LULCConfidenceStats(BaseModel):
    mean_confidence: float
    high_confidence_pct: float
    medium_confidence_pct: float
    low_confidence_pct: float

class LULCModelMetadata(BaseModel):
    classifier: str
    resolution_m: float
    crs: str
    bands_used: List[str]
    indices: List[str]
    accuracy: float
    macro_f1: float
    weighted_f1: float

class LULCSummary(BaseModel):
    total_watersheds: int
    coverage_distribution: Dict[str, int]
    full_scene_distribution: Dict[str, float]
    confidence_stats: LULCConfidenceStats
    model_metadata: LULCModelMetadata
    status: DataStatus = "available"

class WatershedRisk(BaseModel):
    id: str
    MWS: str
    water_stress_score: float
    flood_risk_score: float
    ecosystem_risk_score: float
    base_risk_score: float
    ml_anomaly_score: float
    final_risk_score: float
    risk_category: str
    primary_risk_driver: str
    status: DataStatus = "available"

class WatershedInterventions(BaseModel):
    id: str
    MWS: str
    risk_category: str
    primary_intervention: Optional[str] = None
    secondary_intervention: Optional[str] = None
    long_term_intervention: Optional[str] = None
    iot_sensors: Optional[str] = None
    monitoring_focus: Optional[str] = None
    status: DataStatus = "available"

class MonthlyHealthPoint(BaseModel):
    month: str
    year: int
    health_index: float
    risk_score: float

class WatershedDetail(BaseModel):
    id: str
    MWS: str
    area_km2: Optional[float] = None
    lulc: Optional[WatershedLULC] = None
    risk: Optional[WatershedRisk] = None
    interventions: Optional[WatershedInterventions] = None
    elevation_mean: Optional[float] = None
    slope_mean: Optional[float] = None
    stream_length_km: Optional[float] = None
    drainage_density: Optional[float] = None
    rainfall_mm: Optional[float] = None
    rainfall_anomaly: Optional[float] = None
    ndvi: Optional[float] = None
    ndvi_anomaly: Optional[float] = None
    monthly_trend: Optional[List[MonthlyHealthPoint]] = None
    status: DataStatus = "available"

class IoTReading(BaseModel):
    id: Optional[str] = Field(None, description="Micro-watershed ID (e.g. g_mws.240575)")
    mws_code: Optional[str] = Field(None, description="Hydrological display code (e.g. 4D4F2m3)")
    device_id: Optional[str] = Field(default="ESP32_SHIGGAON_NODE_01", description="ESP32 hardware device identifier")
    rainfall_mm: Optional[float] = Field(None, ge=0.0, description="Rainfall in mm")
    rainfall_mm_hr: Optional[float] = Field(None, ge=0.0, description="Rainfall intensity in mm/hr")
    soil_moisture_pct: float = Field(..., ge=0.0, le=100.0, description="Soil moisture percentage (0-100%)")
    water_level_cm: float = Field(..., ge=0.0, description="Water level in cm")
    turbidity_ntu: float = Field(..., ge=0.0, description="Turbidity in NTU")
    air_temperature_c: float = Field(default=27.0, description="Air temperature in Celsius")
    humidity_pct: float = Field(default=80.0, ge=0.0, le=100.0, description="Relative humidity percentage")
    water_temperature_c: float = Field(default=25.0, description="Water temperature in Celsius")
    ph: float = Field(default=7.0, ge=0.0, le=14.0, description="Water pH value")
    year: Optional[int] = None
    month: Optional[int] = None
    timestamp: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Rainfall aliases (rainfall, rainfall_mm, rainfall_mm_hr)
            if "rainfall_mm_hr" in data and ("rainfall_mm" not in data or data.get("rainfall_mm") is None):
                data["rainfall_mm"] = data["rainfall_mm_hr"]
            elif "rainfall_mm" in data and ("rainfall_mm_hr" not in data or data.get("rainfall_mm_hr") is None):
                data["rainfall_mm_hr"] = data["rainfall_mm"]
            elif "rainfall" in data:
                if "rainfall_mm" not in data or data.get("rainfall_mm") is None:
                    data["rainfall_mm"] = data["rainfall"]
                if "rainfall_mm_hr" not in data or data.get("rainfall_mm_hr") is None:
                    data["rainfall_mm_hr"] = data["rainfall"]

            if data.get("rainfall_mm") is None and data.get("rainfall_mm_hr") is None:
                data["rainfall_mm"] = 0.0
                data["rainfall_mm_hr"] = 0.0

            alias_map = {
                "soil_moisture": "soil_moisture_pct",
                "water_level": "water_level_cm",
                "turbidity": "turbidity_ntu",
                "air_temperature": "air_temperature_c",
                "humidity": "humidity_pct",
                "water_temperature": "water_temperature_c",
            }
            for alias, canonical in alias_map.items():
                if alias in data and canonical not in data:
                    data[canonical] = data[alias]

            # Catchment resolution: if id missing but mws_code provided
            if not data.get("id") and data.get("mws_code"):
                data["id"] = data["mws_code"]
            elif not data.get("id") and not data.get("mws_code"):
                data["id"] = "g_mws.240575"
        return data

class LiveRiskResult(BaseModel):
    id: str
    MWS: Optional[str] = None
    device_id: Optional[str] = None
    year: int
    month: int
    timestamp: Optional[str] = None
    rainfall: Optional[float] = None
    rainfall_mm: Optional[float] = None
    rainfall_mm_hr: Optional[float] = None
    soil_moisture: Optional[float] = None
    soil_moisture_pct: Optional[float] = None
    water_level: Optional[float] = None
    water_level_cm: Optional[float] = None
    turbidity: Optional[float] = None
    turbidity_ntu: Optional[float] = None
    ph: Optional[float] = None
    air_temperature_c: Optional[float] = None
    water_temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    base_risk_score: float
    rainfall_z_score: float
    live_ml_anomaly_score: float
    ml_anomaly_score: Optional[float] = None
    iot_disturbance_score: float
    live_risk_score: float
    live_risk_category: str
    risk_category: Optional[str] = None
    live_risk_drivers: str
    compound_event_detected: bool
    compound_event_type: Optional[str] = None
    event_classification: Optional[str] = None
    compound_alert_level: Optional[str] = None
    compound_alert: Optional[str] = None
    recommended_action: Optional[str] = None
    is_stale: Optional[bool] = False
    connection_status: Optional[str] = "CONNECTED"
    source: Literal["live", "simulation"] = "live"
    status: DataStatus = "available"

class EvidenceItem(BaseModel):
    image_id: Optional[str] = None
    filename: str = Field(default="unknown", description="Image file name")
    file_name: Optional[str] = None
    timestamp: Optional[str] = None
    capture_datetime: Optional[str] = None
    processing_timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    id: Optional[str] = Field(None, description="Primary canonical/system/GIS join key (e.g. g_mws.240575)")
    MWS: Optional[str] = Field(None, description="Human-readable hydrological display code (e.g. 4D4F2m3)")
    mws_id: Optional[str] = Field(None, description="GIS join key alias (e.g. g_mws.240575)")
    mws_code: Optional[str] = Field(None, description="SLUSI display code alias (e.g. 4D4F2m3)")
    boundary_status: Optional[str] = None
    study_area_status: Optional[str] = None
    coordinate_status: Optional[str] = None
    watershed_status: Optional[str] = None
    lulc_class: Optional[str] = None
    lulc_value: Optional[int] = None
    observation_status: Optional[str] = None
    processing_status: Optional[str] = None
    gps_source: Optional[str] = None
    gps_accuracy_m: Optional[float] = None
    source: str = "geocoded_pipeline"
    status: DataStatus = "available"

    @model_validator(mode="before")
    @classmethod
    def harmonize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Filename aliases
            fn = data.get("filename") or data.get("file_name") or data.get("image_name") or "unknown"
            data["filename"] = fn
            data["file_name"] = fn

            # Canonical MWS aliases
            canonical_id = data.get("id") or data.get("mws_id") or data.get("micro_watershed_id")
            if canonical_id is not None:
                data["id"] = str(canonical_id)
                data["mws_id"] = str(canonical_id)
            display_mws = data.get("MWS") or data.get("mws_code")
            if display_mws is not None:
                data["MWS"] = str(display_mws)
                data["mws_code"] = str(display_mws)

            # Timestamp aliases
            ts = data.get("timestamp") or data.get("capture_datetime") or data.get("processing_timestamp")
            if ts is not None:
                data["timestamp"] = str(ts)
                data["capture_datetime"] = str(ts)
                data["processing_timestamp"] = str(ts)

            # Boundary / Study Area status
            bs = data.get("boundary_status") or data.get("study_area_status")
            if bs is not None:
                data["boundary_status"] = str(bs)
                data["study_area_status"] = str(bs)

            # Observation / Coordinate status
            obs = data.get("observation_status") or data.get("coordinate_status") or data.get("status")
            if obs is not None and obs not in ("available", "loading", "unavailable", "invalid", "no_data"):
                data["observation_status"] = str(obs)
            if data.get("coordinate_status") is None and data.get("observation_status") is not None:
                data["coordinate_status"] = data["observation_status"]
        return data

class ProcessedPhotoResult(BaseModel):
    filename: str
    status: str
    state_category: str  # "processed" | "missing_gps" | "outside_boundary" | "mws_unresolved" | "rejected" | "error"
    error_reason: Optional[str] = None
    image_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_status: Optional[str] = None
    study_area_status: Optional[str] = None
    micro_watershed_id: Optional[str] = None
    mws_code: Optional[str] = None
    lulc_class: Optional[str] = None
    lulc_value: Optional[int] = None
    timestamp: Optional[str] = None

class BatchUploadResponse(BaseModel):
    total_received: int
    total_processed: int
    valid_geotagged: int
    inside_boundary: int
    mws_resolved: int
    rejected_missing_gps: int
    outside_boundary: int
    mws_unresolved: int
    failed_or_invalid: int
    summary_message: str
    results: List[ProcessedPhotoResult]
    ledger: List[EvidenceItem]
    status: DataStatus = "available"

class BasinSummary(BaseModel):
    watershed_count: int
    total_area_km2: float
    basin_health_index: float
    average_risk_score: float
    critical_count: int
    high_count: int
    moderate_count: int
    low_count: int
    risk_distribution: Optional[Dict[str, int]] = None
    primary_risk_drivers: Optional[Dict[str, int]] = None
    monthly_trend: Optional[List[MonthlyHealthPoint]] = None
    avg_slope_mean: Optional[float] = None
    avg_elevation_mean: Optional[float] = None
    avg_drainage_density: Optional[float] = None
    avg_stream_length_km: Optional[float] = None
    avg_ndvi: Optional[float] = None
    avg_rainfall_mm: Optional[float] = None
    avg_rainfall_anomaly: Optional[float] = None
    data_mode: Literal["simulation", "live"] = "simulation"
    status: DataStatus = "available"

class WaterQualityRecord(BaseModel):
    id: str = Field(description="Primary canonical/system/GIS join key (e.g. g_mws.240575)")
    MWS: str = Field(description="Human-readable hydrological display code (e.g. 4D4F2m3)")
    timestamp: str
    ph: float
    tds: float
    turbidity: float
    temperature: float
    wqi: float
    quality_category: str
    source: str = "simulation"
    status: DataStatus = "available"

class WaterQualitySummary(BaseModel):
    total_monitored_mws: int
    data_mode: str = "simulation"
    category_distribution: Dict[str, int]
    mean_wqi: float
    parameter_standards: Dict[str, Dict[str, float]]
    watersheds: List[WaterQualityRecord]
    status: DataStatus = "available"

class MwsReport(BaseModel):
    report_type: Literal["mws"] = "mws"
    id: str = Field(description="Primary canonical/system/GIS join key (e.g. g_mws.240575)")
    MWS: str = Field(description="Human-readable hydrological display code (e.g. 4D4F2m3)")
    area_km2: Optional[float] = None
    stream_len_km: Optional[float] = None
    drainage_density: Optional[float] = None
    max_strahler: Optional[int] = None
    generated_at: str
    risk: Dict[str, Any]
    lulc: Dict[str, Any]
    water_quality: Dict[str, Any]
    live_iot: Dict[str, Any]
    field_evidence: Dict[str, Any]
    interventions: Dict[str, Any]
    provenance: Dict[str, str]
    status: DataStatus = "available"

class BasinReport(BaseModel):
    report_type: Literal["basin"] = "basin"
    basin_name: str = "Shiggaon Taluk Watershed Basin"
    total_mws: int = 66
    total_area_km2: float
    basin_health_index: float
    average_risk_score: float
    generated_at: str
    risk_distribution: Dict[str, int]
    primary_drivers: Dict[str, int]
    lulc_distribution: Dict[str, float]
    lulc_coverage: Dict[str, int]
    water_quality_summary: Dict[str, Any]
    live_iot_summary: Dict[str, Any]
    field_evidence_summary: Dict[str, Any]
    intervention_summary: Dict[str, int]
    provenance: Dict[str, str]
    status: DataStatus = "available"

class CropRecommendation(BaseModel):
    crop_name: str
    local_name: str
    category: str
    season: str
    suitability_score: float
    suitability_tier: str  # "OPTIMAL" | "HIGHLY_SUITABLE" | "MODERATELY_SUITABLE" | "CONDITIONAL" | "NOT_RECOMMENDED"
    water_requirement_mm: str
    water_tier: str  # "VERY_LOW" | "LOW" | "LOW_MODERATE" | "MODERATE" | "HIGH" | "VERY_HIGH"
    water_stress_rationale: str
    recommended_irrigation: str
    salinity_tolerance: str
    risk_management_tips: str
    key_advantages: List[str]

class CropCaution(BaseModel):
    crop_name: str
    risk_level: str  # "CRITICAL_RISK" | "HIGH_RISK" | "MODERATE_RISK"
    water_deficit_hazard: str
    depletion_impact: str
    alternative_suggestion: str

class WatershedWaterSummary(BaseModel):
    water_stress_score: float
    water_stress_level: str
    flood_risk_score: float
    flood_risk_level: str
    rainfall_mm: Optional[float] = None
    rainfall_anomaly_sigma: Optional[float] = None
    wqi: Optional[float] = None
    wqi_category: Optional[str] = None
    tds_mg_l: Optional[float] = None
    ph: Optional[float] = None
    slope_mean_deg: Optional[float] = None
    dominant_lulc: Optional[str] = None
    irrigation_advisory: str

class WatershedCropAdvisory(BaseModel):
    id: str
    MWS: str
    generated_at: str
    water_summary: WatershedWaterSummary
    recommended_crops: List[CropRecommendation]
    caution_crops: List[CropCaution]
    conservation_practices: List[str]
    status: DataStatus = "available"

