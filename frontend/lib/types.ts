export type DataStatus = 'available' | 'loading' | 'unavailable' | 'invalid' | 'no_data'

export interface WatershedSummary {
  id: string // Primary internal/system/GIS join key (e.g. g_mws.240575)
  MWS: string // Human-readable hydrological display code (e.g. 4D4F2m3)
  area_km2: number | null
  dominant_class: string | null
  final_risk_score: number | null
  risk_score?: number | null
  risk_category: string | null
  primary_driver?: string
  driver_score?: number | null
  intervention_priority?: string
  primary_intervention?: string | null
  stream_len_km?: number | null
  health_index: number | null
  status: DataStatus
}

export interface WatershedLULC {
  id: string
  MWS: string
  forest_pct: number
  agriculture_pct: number
  water_pct: number
  builtup_pct: number
  barren_pct: number
  coverage_category: string
  coverage_pct: number | null
  valid_pixel_count: number
  dominant_class: string
  status: DataStatus
}

export interface LulcConfidenceStats {
  mean_confidence: number
  high_confidence_pct: number
  medium_confidence_pct: number
  low_confidence_pct: number
}

export interface LulcModelMetadata {
  classifier: string
  resolution_m: number
  crs: string
  bands_used: string[]
  indices: string[]
  accuracy: number
  macro_f1: number
  weighted_f1: number
}

export interface LulcBasinSummary {
  total_watersheds: number
  coverage_distribution: Record<string, number>
  full_scene_distribution: Record<string, number>
  confidence_stats: LulcConfidenceStats
  model_metadata: LulcModelMetadata
  status: DataStatus
}

export interface WatershedRisk {
  id: string
  MWS: string
  water_stress_score: number
  flood_risk_score: number
  ecosystem_risk_score: number
  base_risk_score: number
  ml_anomaly_score: number
  final_risk_score: number
  risk_category: string
  primary_risk_driver: string
  primary_driver?: string
  status: DataStatus
}

export interface WatershedInterventions {
  id: string
  MWS: string
  risk_category: string
  primary_intervention: string | null
  secondary_intervention: string | null
  long_term_intervention: string | null
  iot_sensors: string | null
  monitoring_focus: string | null
  status: DataStatus
}

export interface MonthlyHealthPoint {
  month: string
  year: number
  health_index: number
  risk_score: number
}

export interface WatershedDetail {
  id: string
  MWS: string
  area_km2: number | null
  lulc: WatershedLULC | null
  risk: WatershedRisk | null
  interventions: WatershedInterventions | null
  elevation_mean: number | null
  slope_mean: number | null
  stream_length_km: number | null
  drainage_density: number | null
  rainfall_mm?: number | null
  rainfall_anomaly?: number | null
  ndvi?: number | null
  ndvi_anomaly?: number | null
  monthly_trend?: MonthlyHealthPoint[]
  status: DataStatus
}

export interface BasinSummary {
  watershed_count: number
  total_area_km2: number
  basin_health_index: number
  average_risk_score: number
  critical_count: number
  high_count: number
  moderate_count: number
  low_count: number
  risk_distribution?: Record<string, number>
  primary_risk_drivers?: Record<string, number>
  monthly_trend?: MonthlyHealthPoint[]
  avg_slope_mean?: number | null
  avg_elevation_mean?: number | null
  avg_drainage_density?: number | null
  avg_stream_length_km?: number | null
  avg_ndvi?: number | null
  avg_rainfall_mm?: number | null
  avg_rainfall_anomaly?: number | null
  data_mode: 'simulation' | 'live'
  status: DataStatus
}

export interface IoTReading {
  id?: string
  mws_code?: string
  device_id?: string
  rainfall_mm?: number
  rainfall_mm_hr?: number
  rainfall?: number
  soil_moisture_pct?: number
  soil_moisture?: number
  water_level_cm?: number
  water_level?: number
  turbidity_ntu?: number
  turbidity?: number
  air_temperature_c?: number
  humidity_pct?: number
  water_temperature_c?: number
  ph?: number
  year?: number
  month?: number
  timestamp?: string
}

export interface LiveRiskResult {
  id: string
  MWS: string | null
  device_id?: string | null
  year: number
  month: number
  timestamp?: string
  rainfall?: number
  rainfall_mm?: number
  rainfall_mm_hr?: number
  soil_moisture?: number
  soil_moisture_pct?: number
  water_level?: number
  water_level_cm?: number
  turbidity?: number
  turbidity_ntu?: number
  base_risk_score: number
  rainfall_z_score: number
  live_ml_anomaly_score: number
  ml_anomaly_score?: number
  iot_disturbance_score: number
  live_risk_score: number
  live_risk_category: string
  risk_category?: string
  live_risk_drivers: string
  compound_event_detected: boolean
  compound_event_type: string | null
  event_classification?: string | null
  compound_alert_level: string | null
  compound_alert?: string | null
  recommended_action: string | null
  is_stale?: boolean
  connection_status?: 'CONNECTING' | 'CONNECTED' | 'OFFLINE / NO DATA' | string
  source?: 'live' | 'simulation'
  status: DataStatus
}

export interface EvidenceItem {
  image_id: string | null
  filename: string
  file_name?: string
  timestamp: string | null
  capture_datetime?: string | null
  processing_timestamp?: string | null
  latitude: number | null
  longitude: number | null
  id: string | null
  MWS: string | null
  mws_id?: string | null
  mws_code?: string | null
  boundary_status: string | null
  study_area_status?: string | null
  coordinate_status: string | null
  watershed_status?: string | null
  lulc_class: string | null
  lulc_value?: number | null
  observation_status: string | null
  processing_status?: string | null
  gps_source: string | null
  gps_accuracy_m: number | null
  source: string
  status: DataStatus
}

export type Screen =
  | 'Dashboard'
  | 'Micro-Watershed Profile'
  | 'Crop Intelligence'
  | 'GIS Explorer'
  | 'LULC Analysis'
  | 'Water Quality'
  | 'IoT Network'
  | 'Field Observations'
  | 'Reports & Exports'

export interface ObservationMarkerData {
  latitude: number
  longitude: number
  MWS?: string | null
  id?: string | null
  filename?: string | null
  lulc_class?: string | null
}

export interface ProcessedPhotoResult {
  filename: string
  status: string
  state_category: 'processed' | 'missing_gps' | 'outside_boundary' | 'mws_unresolved' | 'rejected' | 'error' | string
  error_reason?: string | null
  image_id?: string | null
  latitude?: number | null
  longitude?: number | null
  coordinate_status?: string | null
  study_area_status?: string | null
  micro_watershed_id?: string | null
  mws_code?: string | null
  lulc_class?: string | null
  lulc_value?: number | null
  timestamp?: string | null
}

export interface BatchUploadResponse {
  total_received: number
  total_processed: number
  valid_geotagged: number
  inside_boundary: number
  mws_resolved: number
  rejected_missing_gps: number
  outside_boundary: number
  mws_unresolved: number
  failed_or_invalid: number
  summary_message: string
  results: ProcessedPhotoResult[]
  ledger: EvidenceItem[]
  status: DataStatus
}

export interface ApiResponse<T> {
  data: T | null
  status: DataStatus
  error?: string
}

export interface MwsGeoJsonProperties {
  id: string
  MWS: string
  area_km2: number | null
  risk_score: number | null
  risk_category: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW' | string
  health_index: number | null
  primary_driver: string
  intervention_priority: string
  forest_pct: number
  agriculture_pct: number
  water_pct: number
  builtup_pct: number
  barren_pct: number
  stream_len_km: number
  drainage_density: number
  max_strahler: number
}

export interface MwsGeoJsonFeature {
  type: 'Feature'
  geometry: {
    type: 'Polygon' | 'MultiPolygon'
    coordinates: number[][][] | number[][][][]
  }
  properties: MwsGeoJsonProperties
}

export interface MwsGeoJsonCollection {
  type: 'FeatureCollection'
  total_features: number
  risk_distribution: Record<string, number>
  primary_drivers: Record<string, number>
  features: MwsGeoJsonFeature[]
}

export interface WaterQualityRecord {
  id: string
  MWS: string
  timestamp: string
  ph: number
  tds: number
  turbidity: number
  temperature: number
  wqi: number
  quality_category: 'Excellent' | 'Good' | 'Poor' | 'Very Poor' | 'Unsuitable for Drinking' | string
  source: 'simulation' | 'historical' | 'live'
  status?: DataStatus
}

export interface WaterQualitySummary {
  total_monitored_mws: number
  data_mode: 'simulation' | 'live'
  category_distribution: Record<string, number>
  mean_wqi: number
  parameter_standards: Record<string, { ideal: number; standard: number }>
  watersheds: WaterQualityRecord[]
  status?: DataStatus
}

export interface MwsReport {
  report_type: 'mws'
  id: string
  MWS: string
  area_km2: number | null
  stream_len_km: number | null
  drainage_density: number | null
  max_strahler: number | null
  generated_at: string
  risk: {
    risk_score: number
    risk_category: string
    health_index: number | null
    primary_driver: string
    sub_scores: Record<string, number>
  }
  lulc: {
    forest_pct: number
    agriculture_pct: number
    water_pct: number
    builtup_pct: number
    barren_pct: number
    dominant_class: string
    lulc_coverage: string
  }
  water_quality: {
    ph: number
    tds: number
    turbidity: number
    temperature: number
    wqi: number
    quality_category: string
    timestamp: string
    source: 'simulation' | string
  }
  live_iot: {
    available: boolean
    status: string
    rainfall_mm?: number | null
    soil_moisture_pct?: number | null
    water_level_cm?: number | null
    turbidity_ntu?: number | null
    ml_anomaly_score?: number | null
    compound_alert_level?: string | null
    timestamp?: string | null
    source: string
  }
  field_evidence: {
    count: number
    status: string
    latest_observations: Array<{
      id: string
      title?: string
      category: string
      date?: string
      has_photo: boolean
    }>
  }
  interventions: {
    intervention_priority: string
    primary_driver: string
    primary_intervention: string
    secondary_intervention: string
    long_term_intervention: string
    iot_sensors: string
    monitoring_focus: string
  }
  provenance: Record<string, string>
  status: DataStatus
}

export interface BasinReport {
  report_type: 'basin'
  basin_name: string
  total_mws: number
  total_area_km2: number
  basin_health_index: number
  average_risk_score: number
  generated_at: string
  risk_distribution: Record<string, number>
  primary_drivers: Record<string, number>
  lulc_distribution: Record<string, number>
  lulc_coverage: Record<string, number>
  water_quality_summary: {
    total_monitored_mws: number
    mean_wqi: number
    category_distribution: Record<string, number>
    data_mode: string
  }
  live_iot_summary: {
    monitored_gateways: number
    active_live_nodes: number
    status: string
    latest_stream?: string | null
  }
  field_evidence_summary: {
    total_observations: number
    status: string
  }
  intervention_summary: Record<string, number>
  provenance: Record<string, string>
  status: DataStatus
}

export type CropSuitabilityTier =
  | 'OPTIMAL'
  | 'HIGHLY_SUITABLE'
  | 'MODERATELY_SUITABLE'
  | 'CONDITIONAL'
  | 'NOT_RECOMMENDED'

export interface CropRecommendation {
  crop_name: string
  local_name: string
  category: string
  season: string
  suitability_score: number
  suitability_tier: CropSuitabilityTier
  water_requirement_mm: string
  water_tier: 'VERY_LOW' | 'LOW' | 'LOW_MODERATE' | 'MODERATE' | 'HIGH' | 'VERY_HIGH'
  water_stress_rationale: string
  recommended_irrigation: string
  salinity_tolerance: string
  risk_management_tips: string
  key_advantages: string[]
}

export interface CropCaution {
  crop_name: string
  risk_level: 'CRITICAL_RISK' | 'HIGH_RISK' | 'MODERATE_RISK'
  water_deficit_hazard: string
  depletion_impact: string
  alternative_suggestion: string
}

export interface WatershedWaterSummary {
  water_stress_score: number
  water_stress_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
  flood_risk_score: number
  flood_risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
  rainfall_mm?: number | null
  rainfall_anomaly_sigma?: number | null
  wqi?: number | null
  wqi_category?: string | null
  tds_mg_l?: number | null
  ph?: number | null
  slope_mean_deg?: number | null
  dominant_lulc?: string | null
  irrigation_advisory: string
}

export interface WatershedCropAdvisory {
  id: string
  MWS: string
  generated_at: string
  water_summary: WatershedWaterSummary
  recommended_crops: CropRecommendation[]
  caution_crops: CropCaution[]
  conservation_practices: string[]
  status: DataStatus
}
