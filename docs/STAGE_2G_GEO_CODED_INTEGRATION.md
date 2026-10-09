# Stage 2G — Geo-Coded Field Observations Integration

This document specifies the integration of the authoritative Geo-Coded field imagery pipeline into the Shiggaon Watershed Intelligence System backend and frontend.

---

## 1. Primary Flow & Architecture

The Geo-Coded pipeline connects field survey photographs with official spatial boundaries and Model 1 LULC classifications:

```
Field Survey Image
       ↓
EXIF Metadata / GPS Extraction (GPSLatitude & GPSLongitude tags)
       ↓
Coordinate Validation & DMS-to-Decimal (WGS84 EPSG:4326)
       ↓
Shiggaon Taluk Boundary-First Inclusion Check (01_STUDY_AREA)
       ↓
66-MWS STRtree Spatial Index Lookup (03_MICRO_WATERSHEDS)
       ↓
Canonical Watershed Identity Resolution (id vs MWS)
       ↓
Model 1 Sentinel-2 10m LULC Sampling & Class Purity
       ↓
Status Translation (VALID, MISSING, INSIDE, BOUNDARY_REVIEW)
       ↓
Deterministic SHA-256 Ledger ID Assignment (IMG_0001 format)
       ↓
Backend Adapter & REST API (/api/v1/field-observations)
       ↓
Frontend Field Observations Screen (Vector GIS map, KPIs, Ledger HUD)
```

---

## 2. Canonical MWS Contract

Strict compliance with the project's canonical MWS contract:

- **`id`**: Primary internal/system/GIS join key (e.g. `g_mws.240575`).
- **`MWS`**: Human-readable hydrological display code (e.g. `4D4F2m3`).
- **Authoritative Verified Mapping**: `g_mws.240575` $\rightarrow$ `4D4F2m3`.

---

## 3. Data Provenance & Honesty Contract

- **Field Observations Provenance**: Marked with `source = "geocoded_pipeline"`.
- **Honest Empty State**: When no processed field batches are present, the API returns an empty list (`[]`) and the UI displays:
  `"No field observations available. Process geotagged field photos through the Geo-Coded pipeline to populate ground-truth records."`
- **Zero Simulation Substitution**: Field observation screens NEVER substitute synthetic data or simulated coordinates.
- **Zero Fabricated Coordinates**: Images without valid EXIF GPS return `latitude: null`, `longitude: null`, and `observation_status: "NO_GPS"`.

---

## 4. Relationship: Field Observations vs. IoT Telemetry vs. Simulation

| Dimension | Field Observations | Live IoT Telemetry | Simulation Mode |
| :--- | :--- | :--- | :--- |
| **Data Nature** | Geotagged site photographs | Real-time physical sensor streams (rainfall, soil, water level) | Synthetic precipitation / catchment scenarios |
| **Pipeline** | EXIF extraction $\rightarrow$ GIS join $\rightarrow$ LULC query | Isolation Forest ML anomaly + compound runoff alerts | Baseline risk engine scenarios |
| **Source Tag** | `source: "geocoded_pipeline"` | `source: "live"` | `source: "simulation"` |
| **Fallback** | Honest empty list (`[]`) | Explicit waiting for gateway | Calibrated baseline Model 2 risk |

---

## 5. API Specification

### Endpoints

- **`GET /api/v1/field-observations`**: List all processed observations.
  - Query parameter: `watershed_id: Optional[str]`. Validates against official 66-MWS GIS catalog; returns HTTP 404 if MWS does not exist.
- **`GET /api/v1/field-observations/{image_id}`**: Retrieve single observation by permanent ledger ID (e.g. `IMG_0001`). Returns HTTP 404 if not found.
- **`GET /api/v1/field-observations/mws/{id}`**: Retrieve observations belonging to a specific micro-watershed. Returns HTTP 404 if unknown MWS.
- **`GET /api/v1/evidence`**: Backward-compatible alias to `/api/v1/field-observations`.

### Observation Schema (`EvidenceItem`)

```json
{
  "image_id": "IMG_0001",
  "filename": "valid_ne.jpg",
  "latitude": 15.012338,
  "longitude": 75.213450,
  "id": "g_mws.240603",
  "MWS": "4D4F2j8",
  "boundary_status": "INSIDE",
  "coordinate_status": "VALID",
  "observation_status": "OK",
  "lulc_class": "Agriculture",
  "lulc_value": 2,
  "timestamp": "2026-09-07T04:02:21Z",
  "gps_source": "EXIF",
  "gps_accuracy_m": null,
  "source": "geocoded_pipeline",
  "status": "available"
}
```

---

## 6. How to Run & Test

```bash
# 1. Run Water Quality regression suite
python -m pytest water_quality/tests

# 2. Run full backend and Model 1 test suite
python -m pytest -o pythonpath=model1/model1_lulc backend\model_2\tests model1\model1_lulc\tests

# 3. Run Geo-Coded module test suite
python -m pytest tests  # (inside geo_coded/GEO_CODED_IMAGES)

# 4. Verify Model 1 artifact checksums
python -c "import hashlib; d=open('model1/model1_lulc/models/lulc_random_forest.joblib','rb').read(); print(hashlib.sha256(d).hexdigest(), hashlib.md5(d).hexdigest())"
```
