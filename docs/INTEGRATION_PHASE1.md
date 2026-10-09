# Phase 1: Integration Foundation Documentation

## 1. System Architecture

The Shiggaon Watershed Intelligence System integrates satellite remote sensing (Model 1), geospatial analysis (GIS), watershed risk modeling (Model 2), field ground-truth verification (Geo-Coded), and physical telemetry (IoT) into a single unified API architecture serving the Next.js decision-support frontend:

```
[ Model 1: Sentinel-2 LULC ]     [ GIS: 66 MWS Master GPKG ]     [ Model 2: Risk Engine V4 ]
            |                                  |                                  |
            v                                  v                                  v
   model1_adapter.py                     gis_adapter.py                    model2_adapter.py
            \                                  |                                  /
             \--------------------------+------+---------------------------------/
                                        |
                                        v
                       +---------------------------------+
                       |    Unified FastAPI Application   |
                       |       (backend/model_2/api)     |
                       +----------------+----------------+
                                        |
                   +--------------------+--------------------+
                   |                                         |
                   v                                         v
       [ Live IoT Telemetry ]                    [ Geo-Coded Photo Evidence ]
       iot_inference_engine.py                        geocoded_adapter.py
                   |                                         |
                   +--------------------+--------------------+
                                        |
                                        v
                                REST API (/api/v1/...)
                                        |
                                        v
                            [ Next.js V0 Frontend ]
```

---

## 2. Canonical MWS Identity Contract

The repository establishes and enforces a strict, two-tier micro-watershed identity convention across all databases, APIs, and interfaces:

| Key | Description | Canonical Example | Primary Role |
|---|---|---|---|
| `id` | Internal / System / GIS Join Key | `g_mws.240575` | Relational join key across GIS, Model 1, Model 2, and Geo-Coded databases. Unique string. |
| `MWS` | Hydrological / Display Code | `4D4F2m3` | Human-readable SLUSI watershed classification displayed in UI, maps, and reports. |

> [!IMPORTANT]
> **Contract Rule:** Never swap or conflate `id` and `MWS`. The API surfaces both explicitly on all endpoints so downstream consumers have complete clarity.

---

## 3. Versioned API Contracts (`/api/v1/...`)

### `GET /api/v1/watersheds`
Returns all 66 micro-watersheds with summary metrics and health indices.
```json
[
  {
    "id": "g_mws.240575",
    "MWS": "4D4F2m3",
    "area_km2": 14.24,
    "dominant_class": "Agriculture",
    "final_risk_score": 60.0,
    "risk_category": "HIGH",
    "health_index": 40.0,
    "status": "available"
  }
]
```

### `GET /api/v1/watersheds/basin/summary`
Returns high-level executive KPIs for the entire Shiggaon Taluk basin.
```json
{
  "watershed_count": 66,
  "total_area_km2": 966.2,
  "basin_health_index": 47.1,
  "average_risk_score": 52.9,
  "critical_count": 0,
  "high_count": 24,
  "moderate_count": 39,
  "low_count": 3,
  "data_mode": "simulation",
  "status": "available"
}
```

### `GET /api/v1/watersheds/{id}`
Returns complete profile combining GIS attributes, LULC breakdown, Model 2 risk scores, and recommended interventions. Accepts either `id` (`g_mws.240575`) or `MWS` (`4D4F2m3`).

### `GET /api/v1/telemetry/latest`
Returns the most recent live sensor telemetry and compound event risk calculation. Returns HTTP 404 with honest waiting state if no telemetry has been posted.

### `POST /api/v1/telemetry`
Ingests physical sensor telemetry, immediately executes the online Model 2 Isolation Forest inference and compound event detection, persists the reading, and returns real-time risk classification.

### `POST /api/v1/telemetry/infer`
Runs real Model 2 ML inference on synthetic/scenario inputs without mutating active production telemetry.

### `GET /api/v1/gis/mws-boundaries`
Returns GeoJSON `FeatureCollection` of all 66 micro-watershed boundaries reprojected to WGS84 (`EPSG:4326`).

### `GET /api/v1/evidence`
Returns validated field ground-truth photos with EXIF coordinates, spatial validations, and LULC tags.

---

## 4. Cross-Module Data Flows

### Model 1 $\to$ Model 2
- **Source:** `model1/model1_lulc/outputs/micro_watershed_lulc_statistics.csv`
- **Adapter:** `model1_adapter.py`
- **Resolution:** Normalizes naming inversion (`internal_id` $\to$ `id`, `micro_watershed_id` $\to$ `MWS`, `forest_percent` $\to$ `forest_pct`).
- **Status:** Integrated via live in-memory adapter.

### GIS $\to$ Backend
- **Source:** `gis/SIH_2026_SHIGGAON_GIS_FINAL/03_MICRO_WATERSHEDS/Shiggaon_MWS_Master_66.gpkg`
- **Adapter:** `gis_adapter.py`
- **Resolution:** Extracts 66 polygon geometries, converts `EPSG:32643` $\to$ `EPSG:4326` WGS84 for web maps.
- **Status:** Integrated and cached at server startup.

### Geo-Coded $\to$ Backend
- **Source:** `geo_coded/GEO_CODED_IMAGES/`
- **Adapter:** `geocoded_adapter.py`
- **Resolution:** Parses field photo master records and provides `/api/v1/evidence`. Returns explicit `no_data` state when unpopulated.
- **Status:** Integrated.

### IoT $\to$ Model 2 Live Inference
- **Source:** Sensor payload posted to `POST /api/v1/telemetry` (or legacy `POST /iot-data`)
- **Engine:** `iot_inference_engine.py`
- **Execution:**
  1. Computes monthly rainfall z-score against historical baseline.
  2. Runs online inference with `model2_live_iot_isolation_forest.joblib`.
  3. Calculates multi-sensor disturbance score ($0.35\cdot \text{rain} + 0.30\cdot \text{soil} + 0.20\cdot \text{level} + 0.15\cdot \text{turbidity}$).
  4. Classifies compound alerts (`HIGH ALERT`, `CRITICAL`).
- **Status:** Fully connected and verified against baseline tests.

### Backend $\to$ Frontend
- **Client:** `frontend/lib/api.ts`
- **Resolution:** Fetches `/api/v1/watersheds` and `/api/v1/watersheds/basin/summary` on mount.
- **Offline Safety:** Displays explicit disconnected banner and `"—"` metrics when backend is unreachable (no fake mock data).

---

## 5. Environment & Setup Requirements

### Running Backend API
```bash
# From repository root:
python -m uvicorn backend.model_2.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running Frontend
```bash
# From frontend directory:
npm run dev
# Accessible at http://localhost:3000
```
