# Stage 2H — Reports & Exports Integration

This document specifies the integration of the authoritative Reports & Exports decision-support layer into the Shiggaon Watershed Intelligence System backend and frontend.

---

## 1. Objective & Scope

Stage 2H is the final application integration stage of Phase 2. It builds a read-only decision-support synthesis and export capability combining all previously integrated subsystems:
- Authoritative 66-Micro-Watershed GIS spatial layer (`Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg`)
- Model 1 Sentinel-2 10m Land Use / Land Cover (LULC) Classification
- Model 2 Calibrated Risk Engine V4 (Risk scores, health indices, and decision intervention matrix)
- Water Quality Synthetic Simulator (Explicitly labeled `SIMULATION`)
- Live IoT Telemetry (Explicitly labeled `LIVE` when gateway streams exist, or honest `UNAVAILABLE`)
- Geo-Coded Field Observations (`GEOCODED PIPELINE` ground-truth records)

### Architectural Constraints Preserved
- No new ML models or retraining.
- Model 1 checksums remain unmodified and verified.
- Model 2 risk calculation algorithms remain unchanged.
- Water Quality core algorithms and simulator remain intact.
- Live IoT inference algorithms remain intact.
- Geo-Coded image analysis pipeline remains intact.
- Strict No-Database rule: System uses flat-file GeoPackage, CSV, and in-memory adapter composition.
- Strict Data Honesty Contract: Zero mock data or synthetic substitutions in live reports; missing data clearly marked as `"—"`.

---

## 2. Primary Flow & Architecture

```
Authoritative GIS GPKG (66 MWS)
Model 1 LULC Statistics (10m)
Model 2 Risk Engine V4 Output
Water Quality Simulator (SIMULATION)
Live IoT Telemetry Engine (ESP32)
Geo-Coded Image Pipeline (EXIF Ground-Truth)
                  │
                  ▼
         ReportsAdapter
  (In-Memory Composition & Formatting)
                  │
                  ▼
          FastAPI Router
  (/api/v1/reports/basin, /reports/mws/{id})
  (/api/v1/reports/basin/csv, /reports/mws/{id}/csv)
                  │
                  ▼
       Frontend V0 Screen
    (Reports & Exports Screen)
  [Basin Matrix · MWS Dossier · Vector Map · CSV/JSON Exports]
```

---

## 3. Canonical Identity Contract

All endpoints adhere strictly to the project's canonical MWS contract:
- **`id`**: Primary internal/system/GIS join key (e.g. `g_mws.240575`).
- **`MWS`**: Human-readable hydrological display code (e.g. `4D4F2m3`).
- **Bidirectional Resolution**: Endpoints accepting `{id}` resolve both the canonical GIS ID (`g_mws.240575`) and the display code (`4D4F2m3`) to the canonical record.
- **Error Handling**: Non-existent micro-watershed identifiers return HTTP 404 (Never fallback or fabrication).

---

## 4. Data Honesty & Provenance Contract

| Pipeline Feed | Provenance Tag | Behavior when Absent / Inactive |
| :--- | :--- | :--- |
| **GIS Boundaries** | `Authoritative 66-MWS GeoPackage` | Hard failure / 404 on invalid unit |
| **Risk Engine V4** | `Model 2 Risk Engine V4 (GPKG)` | Canonical precomputed risk profile |
| **LULC Partition** | `Model 1 Sentinel-2 10m Classification` | Model 1 zonal percentages or `"—"` |
| **Water Quality** | `SIMULATION (Water Quality Synthetic Simulator)` | Explicitly declares `source: "simulation"` in all JSON and CSV exports |
| **Live IoT** | `LIVE (ESP32 Gateway Telemetry)` | Reports `status: "unavailable"`, `"No live sensor telemetry available"` (zero synthetic fallback) |
| **Field Evidence** | `GEOCODED PIPELINE` | Reports `count: 0`, `"No field observations available"` (zero mock images) |

---

## 5. API Endpoints & Specifications

### 1. `GET /api/v1/reports/basin`
Returns full basin-level decision report synthesizing all 66 official micro-watersheds.

```json
{
  "report_type": "basin",
  "basin_name": "Shiggaon Taluk Watershed Basin",
  "total_mws": 66,
  "total_area_km2": 627.5,
  "basin_health_index": 50.0,
  "average_risk_score": 50.0,
  "generated_at": "2026-09-07T04:36:00Z",
  "risk_distribution": {
    "CRITICAL": 5,
    "HIGH": 15,
    "MODERATE": 17,
    "LOW": 29
  },
  "primary_drivers": {
    "Water Stress": 38,
    "ML Anomaly": 20,
    "Ecosystem Risk": 8
  },
  "lulc_distribution": {
    "forest_pct": 20.17,
    "agriculture_pct": 62.65,
    "water_pct": 0.73,
    "builtup_pct": 14.76,
    "barren_pct": 1.70
  },
  "water_quality_summary": {
    "total_monitored_mws": 66,
    "mean_wqi": 75.0,
    "data_mode": "simulation"
  },
  "live_iot_summary": {
    "monitored_gateways": 1,
    "active_live_nodes": 1,
    "status": "online"
  },
  "field_evidence_summary": {
    "total_observations": 0,
    "status": "no_observations"
  },
  "provenance": {
    "scope": "Official 66 Shiggaon Taluk Micro-Watersheds",
    "gis": "Authoritative 66-MWS GeoPackage (EPSG:32643 / WGS84)",
    "risk": "Model 2 Risk Engine V4 (Authoritative Output)",
    "lulc": "Model 1 Sentinel-2 10m Classification",
    "water_quality": "SIMULATION (Water Quality Synthetic Simulator)",
    "live_iot": "LIVE (ESP32 Gateway Telemetry)",
    "field_evidence": "UNAVAILABLE"
  },
  "status": "available"
}
```

### 2. `GET /api/v1/reports/basin/csv`
Returns downloadable CSV file attachment (`Content-Disposition: attachment; filename="shiggaon_basin_report.csv"`).
Contains 67 lines: 1 header row + 66 data rows for every official micro-watershed.
Headers: `id,MWS,area_km2,risk_score,risk_category,primary_driver,health_index,intervention_priority,forest_pct,agriculture_pct,water_pct,builtup_pct,barren_pct,dominant_lulc,stream_len_km,drainage_density,wq_ph,wq_tds,wq_turbidity,wq_temp,wq_wqi,wq_quality_category,wq_source,iot_live_status,field_observations_count`

### 3. `GET /api/v1/reports/mws/{id}`
Returns complete decision dossier for an individual micro-watershed.
Returns HTTP 404 if `{id}` does not exist.

### 4. `GET /api/v1/reports/mws/{id}/csv`
Returns downloadable tabular CSV file attachment (`Content-Disposition: attachment; filename="watershed_report_{id}.csv"`).
Headers: `Field,Value,Unit/Context,Provenance`
Returns HTTP 404 if `{id}` does not exist.

---

## 6. Frontend Integration: Reports & Exports Screen

The screen provides:
1. **Scope Toggle**: Switch seamlessly between **Basin Scope (66 MWS)** and **Micro-Watershed Dossier**.
2. **Export Actions**:
   - One-click CSV Export (Basin 66-row CSV or Single MWS key-value CSV).
   - JSON Export (Formatted client-side download).
   - Print / PDF layout trigger.
3. **Top 4 KPI Metric Cards**:
   - Total Coverage (66 MWS / 627.5 km²)
   - Basin Health Index / MWS Risk V4 Score
   - Priority Areas / Catchment Health
   - Active Pipelines / Dominant LULC
4. **Data Honesty & Provenance HUD**:
   - Clear visual chips stating data source and synthetic status for all 6 pipelines.
5. **Interactive Vector GIS Map**:
   - Real 66-MWS vector polygons rendered in SVG (`BasinMap` with `variant="Reports & Exports"`).
   - Hover and click support to inspect individual micro-watersheds.
6. **Decision Dossier / Ledger**:
   - Searchable, filterable 66-MWS decision matrix in Basin scope.
   - Comprehensive multi-panel dossier in MWS scope (morphometry, risk, interventions, LULC, water quality, sensors, field evidence).

---

## 7. Verification Results

All test suites pass with 100% success rate:
- **Water Quality Module**: 20/20 passed (`pytest water_quality/tests`)
- **Geo-Coded Pipeline**: 171/171 passed (`pytest tests` in `geo_coded/GEO_CODED_IMAGES`)
- **Backend & Model 1 Suite**: 94/94 passed (`pytest -o pythonpath=model1/model1_lulc backend/model_2/tests model1/model1_lulc/tests`)
- **Grand Total**: 285 tests passed across the repository.
- **Model 1 Checksums**:
  - SHA-256: `541028753dcb89d478f9e1151277a5dae8e61f62f648cc168280e700cb140439` (EXACT MATCH)
  - MD5: `ee9edc9e14f13457d4d7d929ae678933` (EXACT MATCH)
