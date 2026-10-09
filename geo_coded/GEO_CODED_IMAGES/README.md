# Geo-Coded Image Analysis Module

**SIH Problem Statement 26015** — Application of Geospatial Techniques for
visualization and analysis to interpret Geo-Coded Images to enhance
watershed Development Outcomes (Ministry of Rural Development, DoLR).

This module is one independent backend piece of the overall system: given
a geotagged field photograph, it determines where the photo was taken
relative to the Shiggaon Taluk study area, which micro-watershed it falls
in, and what Model 1's land-cover classification says about that exact
location. It has **no frontend, no 3D visualization, no API/database, and
no IoT integration** — those are other team members' modules. This module
exposes two Python functions and writes CSV/JSON; everything else is out
of scope by design.

---

## 1. What this module does

For each geotagged JPEG, it answers:

- Where was this photo taken (decimal-degree GPS coordinate)?
- Is that location inside the Shiggaon study-area boundary?
- If so, which micro-watershed does it fall in?
- What does Model 1's LULC raster say the land cover is at that exact
  pixel?

...and writes one row per image to CSV and JSON, so downstream tools (GIS
rendering, Model 2's risk scoring, reporting) can consume the results
without re-implementing any of this.

## 2. Input requirements

- JPEG images (`.jpg` / `.jpeg`, any case) containing **GPS EXIF metadata**
  (latitude, longitude, and their N/S/E/W reference tags).
- Images without GPS EXIF, or with malformed GPS EXIF, are not rejected by
  the pipeline outright — they're processed and returned with a `NO_GPS`
  or `MALFORMED_GPS` status (see §8). One bad image never stops a batch.
- Input images are **never modified**. The module only reads EXIF; it
  never writes to, re-saves, or re-tags an input JPEG.

## 3. Processing flow

```
Geo-tagged JPEG
      │
      ▼
EXIF GPS extraction ────────────► NO_GPS / MALFORMED_GPS on failure
      │
      ▼
Coordinate validation (DMS→decimal,
range + sanity checks) ─────────► INVALID_COORDINATE on failure
      │
      ▼
Shiggaon study-area boundary check ─► OUTSIDE_STUDY_AREA (stops here,
      │                                LULC raster is never queried)
      ▼ (inside)
Micro-watershed identification ────► NO_WATERSHED_MATCH is possible even
      │                               when inside the boundary (see §8) --
      │                               processing continues to LULC anyway
      ▼
LULC raster query at the GPS pixel ─► NODATA_PIXEL if the raster has no
      │                                classification there
      ▼
Structured result (schema in §7)
      │
      ▼
CSV + JSON output (one row per image)
```

Source modules implementing each stage:

| Stage | Module |
|---|---|
| EXIF GPS extraction | `src/exif_reader.py` |
| Coordinate validation | `src/coordinate_validator.py` |
| Boundary check | `src/boundary_checker.py` |
| Micro-watershed lookup | `src/watershed_locator.py` |
| LULC raster query | `src/lulc_query.py` |
| Combines boundary+watershed+LULC | `src/geo_lulc_analyzer.py` |
| Per-image orchestration (the full flow above) | `src/image_analyzer.py` |
| Batch runner over a folder | `src/pipeline.py` |
| CSV/JSON writer | `src/io_writer.py` |
| Result schema (single source of truth for output fields) | `src/schema.py` |
| Paths, CRS constants, LULC class map | `src/config.py` |

## 4. Installing dependencies

```bash
pip install -r requirements.txt
```

See `requirements.txt` for exactly which packages are used and why —
every entry was verified against actual imports, not copied from a
template.

## 5. Running a single image

```python
from src.geo_lulc_analyzer import GeoLULCAnalyzer
from src.image_analyzer import analyze_image

analyzer = GeoLULCAnalyzer()          # loads boundary/watershed/raster ONCE
result = analyze_image("path/to/photo.jpg", analyzer)

print(result.status)        # e.g. "OK", "OUTSIDE_STUDY_AREA", "NO_GPS", ...
print(result.lulc_class)    # e.g. "Agriculture", or None if not applicable
```

`result` is a `GeoCodedResult` dataclass (see §7 for every field). It is
never partially populated — fields that don't apply for a given status
are explicitly `None`, not omitted, so downstream code can rely on every
field existing on every result.

If you're processing more than one image, reuse a single `GeoLULCAnalyzer`
instance across all of them (as shown above) rather than constructing a
new one per image — it loads the boundary, all 66 micro-watersheds, and
the full LULC raster into memory once, and reusing it avoids re-reading
those files per photo.

## 6. Running the batch pipeline

```python
from src.pipeline import run_pipeline
from src.io_writer import write_outputs

results = run_pipeline("path/to/folder/of/photos")
csv_path, json_path = write_outputs(results)
print(f"Wrote {len(results)} results to {csv_path} and {json_path}")
```

`run_pipeline` finds every `.jpg`/`.jpeg` (case-insensitive) in the given
folder, processes each one, and returns a list of `GeoCodedResult` — one
per image, in every case, including failures. **A single bad image never
stops the batch**; each image's own errors are captured in its own result
row (`status` + `error_reason`), not raised as an exception.

Default output paths (used when you don't pass explicit paths to
`write_outputs`) are `outputs/geo_coded_results.csv` and
`outputs/geo_coded_results.json`, relative to the module root
(`src/config.py: DEFAULT_CSV_PATH`, `DEFAULT_JSON_PATH`). The `outputs/`
folder is created automatically if it doesn't exist yet.

## 7. Output fields (CSV columns / JSON keys)

Every result — success or failure — has exactly these fields
(`src/schema.py: GeoCodedResult`):

| Field | Type | Notes |
|---|---|---|
| `schema_version` | str | currently `"1.0"` |
| `image_name` | str | filename only, not full path |
| `processing_timestamp` | str | ISO 8601 UTC, wall-clock time of processing (not EXIF capture time) |
| `latitude` | float or null | decimal degrees, WGS84 |
| `longitude` | float or null | decimal degrees, WGS84 |
| `status` | str | see §8 |
| `error_reason` | str or null | human-readable failure detail; null on success |
| `inside_study_area` | bool or null | null only when GPS/coordinate extraction itself failed |
| `micro_watershed_id` | str or null | **from the `id` field** — see §9 |
| `mws_code` | str or null | **from the `MWS` field** — see §10 |
| `lulc_value` | int or null | raw pixel value from the raster (0 = NoData) |
| `lulc_class` | str or null | mapped class name — see §11 |
| `raster_pixel_row` | int or null | row index sampled in the raster |
| `raster_pixel_col` | int or null | column index sampled in the raster |
| `lulc_neighborhood_window_size` | int or null | odd integer, default 3 (3×3 window) |
| `lulc_neighborhood_class_purity_pct` | float or null | % of the window matching the sampled pixel's class — rough homogeneity signal |
| `lulc_neighborhood_nodata_pct` | float or null | % of the window that is NoData |

The last three fields (`lulc_neighborhood_*`) are additions made during
this module's Phase 5 beyond the originally-scoped output — useful as a
rough confidence signal (a photo near a class boundary will have low
purity), but they are not something anyone asked for by name, so drop
them downstream if they're not useful to you.

**Additional fields exist on `GeoCodedResult`** (`image_id`, `file_path`,
`capture_datetime`, `gps_source`, `gps_accuracy_m`, `coordinate_status`,
`study_area_status`) added for teammate-README compatibility — see §13
for what populates them and their meaning. They default to `None` and
are included automatically in the existing `outputs/*.csv`/`.json` (the
CSV writer derives its header from the dataclass, so it picks up new
fields for free) as well as in the new `12_GEO_CODED_IMAGES/` outputs.

## 8. Status values

| Status | Meaning |
|---|---|
| `OK` | Fully resolved: inside boundary, watershed matched, LULC pixel valid. |
| `NO_GPS` | JPEG has no GPS EXIF data at all. |
| `MALFORMED_GPS` | GPS EXIF is present but incomplete/invalid (bad hemisphere ref, wrong tag shape, etc). |
| `INVALID_COORDINATE` | GPS converts to a decimal coordinate outside valid WGS84 range, or has malformed DMS components (e.g. minutes/seconds ≥ 60). |
| `OUTSIDE_STUDY_AREA` | Coordinate is valid but falls outside the Shiggaon boundary. LULC is never queried for these — no `lulc_value`/`lulc_class`. |
| `NO_WATERSHED_MATCH` | Inside the Shiggaon boundary, but the micro-watershed layer has a gap at this exact point (the boundary and watershed layers are independently sourced and don't perfectly tile — see `docs/GEO_CODED_DATA_AUDIT.md` §4). LULC is still queried and populated in this case. |
| `NODATA_PIXEL` | Watershed matched, but the LULC raster has no classification (NoData) at this exact pixel. |
| `OUTSIDE_RASTER_EXTENT` | Inside the boundary but somehow off the raster's pixel grid. Should be rare (raster covers the boundary almost completely per the Phase 1 audit) but is not assumed impossible. |
| `ERROR` | An unanticipated failure (e.g. file not found, corrupt image). Always check `error_reason` for detail. |

**A point can trigger more than one unusual condition at once** (e.g.
inside the boundary, watershed gap, AND a NoData pixel). Only one status
is reported per result, chosen by an explicit, documented priority order
in `src/geo_lulc_analyzer.py` (`STATUS_PRIORITY`, current order:
`OUTSIDE_STUDY_AREA` > `OUTSIDE_RASTER_EXTENT` > `NO_WATERSHED_MATCH` >
`NODATA_PIXEL` > `OK`). This ordering is a documented, deliberately
swappable implementation decision, not something derived from the data —
see the comment block above `STATUS_PRIORITY` in that file if you need to
change which condition "wins" when several are true simultaneously; the
underlying analysis doesn't need to change to do so.

**A second, separate status vocabulary** (`coordinate_status` /
`study_area_status`) is also available on every result — see §13.3. It
does not replace `status` above; it's an additional translation for
compatibility with the teammate imagery README.

## 9. `micro_watershed_id`

`micro_watershed_id` is populated from the micro-watershed layer's `id`
field (e.g. `"g_mws.240575"`). This was an explicit decision: `id` is the
cross-module integration key used elsewhere in the overall system
(Model 2 etc.), while the hydrological watershed code lives separately in
`mws_code`.

## 10. `mws_code`

`mws_code` is populated from the micro-watershed layer's `MWS` field
(e.g. `"4D4F2m3"`) — the actual hydrological/GIS watershed identifier,
kept distinct from the integration key above.

## 11. LULC class mapping — ⚠️ user-confirmed, NOT verified against source

The mapping currently configured in `src/config.py: LULC_CLASS_MAP` is:

```
0 = NODATA
1 = Forest
2 = Agriculture
3 = Water
4 = Built-up
5 = Barren
```

**This mapping has NOT been independently verified against Model 1's
training/export code or a label-encoder artifact.** No such code or
artifact was ever provided to the session that built this module — only
`lulc_prediction.tif` itself, which carries no embedded class legend
(confirmed by inspecting every metadata channel the GeoTIFF format
supports: tags, band description, colormap/RAT — none present, see
`docs/GEO_CODED_DATA_AUDIT.md`). The mapping above comes entirely from an
explicit statement by the person who built Model 1, made during this
module's development, describing it as fixed and not to be reordered.

**Before trusting this module's `lulc_class` output for anything beyond a
hackathon demo, cross-check `LULC_CLASS_MAP` in `src/config.py` against
Model 1's actual training script or label encoder.** If they disagree,
only `src/config.py` needs to change — nothing else in this module
depends on the specific mapping values.

## 12. Integration for the GIS teammate

Two public entry points, everything else is an implementation detail:

- **`src/image_analyzer.py: analyze_image(image_path, analyzer) -> GeoCodedResult`**
  — process exactly one image. Never raises; every failure mode is
  captured in the returned result's `status`/`error_reason`.
- **`src/pipeline.py: run_pipeline(image_dir, analyzer=None) -> list[GeoCodedResult]`**
  — process every JPEG in a folder. If you don't pass `analyzer`, one is
  constructed for you (loading the boundary/watershed/raster once).

Both return `GeoCodedResult` objects (`src/schema.py`) — plain
dataclasses, JSON-serializable via `dataclasses.asdict()` with no custom
encoder needed (verified in `tests/test_io_writer.py` and
`tests/test_geo_lulc_analyzer.py`).

**To render results on a map:** join on `micro_watershed_id` back into
`data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg`'s `id` field —
that's the same key. The `outputs/geo_coded_results.csv` /
`.json` files (or `run_pipeline()`'s return value directly, if you're
calling this from Python rather than reading files) are a static input to
your side — there's no shared runtime state or live connection to set up.

**What this module does NOT do**, so you don't build around an assumption
it will: no frontend, no map rendering, no 3D, no API server, no
database, no IoT ingestion. It's a pure function from
"folder of photos" to "CSV/JSON of geospatial+LULC facts about each one."

---

## 13. Teammate handover outputs

This section covers a second, additional set of outputs built specifically
for compatibility with `SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx`
(the imagery-handling teammate's own workflow doc). These sit alongside —
not instead of — the `outputs/*.csv`/`.json` from §6/§7 above; nothing
about those changed.

### 13.1 Persistent `image_id`

`src/image_id_ledger.py: ImageIdLedger` assigns stable `IMG_0001`-style
IDs, backed by a single local JSON file (**not a database**). Identity is
by file content hash (SHA-256), not filename — a renamed or re-copied
photo resolves to the same ID; two different photos never collide just
because they share a filename. IDs are never reused, even if an entry is
manually deleted from the ledger (a monotonic counter is stored
independently of which entries currently exist).

**This is opt-in.** `analyze_image()` and `run_pipeline()` only assign
`image_id`s if you explicitly pass an `ImageIdLedger` in — if you don't,
`image_id` stays `None` and no ledger file is touched. This keeps casual/
test usage side-effect-free. For a real run where you want persistent
IDs:

```python
from src.image_id_ledger import ImageIdLedger
from src.pipeline import run_pipeline
from src import config

id_ledger = ImageIdLedger(config.IMAGE_ID_LEDGER_PATH)
results = run_pipeline("path/to/photos", id_ledger=id_ledger)
```

Run it again later on the same folder (with new photos added) and
previously-processed photos keep their existing IDs; only new ones get
new sequential IDs.

### 13.2 `Photo_Master_Validated.csv`

`src/teammate_metadata_writer.py: write_photo_master_validated_csv()` →
`12_GEO_CODED_IMAGES/Metadata/Photo_Master_Validated.csv`. One row per
processed image (successes and failures both included), columns exactly
matching the teammate README's field list:

`image_id, file_name, file_path, latitude, longitude, capture_datetime,
gps_source, gps_accuracy_m, coordinate_status, mws_id, study_area_status,
observation_type, description, photo_quality, evidence_relevance,
intervention_type, remarks, review_status, reviewer`

**The last eight columns (`observation_type` through `reviewer`) are
always blank.** This module has no image-content understanding and does
not invent values for human-judgment fields — they exist as columns so
the schema matches, to be filled in by a human reviewer as a separate
step this module doesn't perform.

### 13.3 `coordinate_status` / `study_area_status`

`src/status_translator.py: translate_status()` derives these two fields
from the existing internal `status` (unchanged, still the source of
truth) plus a new boundary-proximity check:

| internal `status` | `coordinate_status` | `study_area_status` |
|---|---|---|
| `NO_GPS` | `MISSING` | `None` |
| `MALFORMED_GPS` / `INVALID_COORDINATE` | `SUSPICIOUS` | `None` |
| `ERROR` | `None` | `None` |
| valid, near boundary (within tolerance) | `VALID` | `BOUNDARY_REVIEW` |
| valid, inside | `VALID` | `INSIDE` |
| valid, outside | `OUTSIDE_STUDY_AREA` | `OUTSIDE` |

"Near boundary" is decided by `BoundaryChecker.distance_to_boundary_m()`
(a new method — the boundary geometry itself is never modified) compared
against `config.BOUNDARY_REVIEW_TOLERANCE_M` (default **15.0 meters**,
configurable in one place). `BOUNDARY_REVIEW` overrides `INSIDE`/`OUTSIDE`
regardless of which side of the boundary the point is actually on — it's
a "needs manual review" flag, not a third spatial category.

### 13.4 `mws_id`

Per the explicit, confirmed project decision: **`mws_id` = the `id` field**
(same value as `micro_watershed_id`), exposed under the column name the
teammate README expects. This is a rename at the export layer only —
`micro_watershed_id` (the internal field) and `mws_code` (the `MWS`
field) are unchanged; nothing about the underlying integration-key
contract was altered.

### 13.5 GeoPackage outputs

`src/teammate_gis_writer.py`, two files, both EPSG:4326, one point per
image with a **valid coordinate** (missing/suspicious-GPS images are
excluded — there's no coordinate to plot; out-of-study-area images ARE
included, since they still have a real geocode):

- `write_photo_points_gpkg()` → `12_GEO_CODED_IMAGES/GIS/GEO_CODED_PHOTO_POINTS.gpkg`
  — image/location/status/LULC attributes, no watershed columns.
- `write_photo_mws_joined_gpkg()` → `12_GEO_CODED_IMAGES/GIS/GEO_CODED_PHOTO_MWS_JOINED.gpkg`
  — same points, plus `mws_id`/`mws_code`.

**Note on "join":** the teammate README describes a manual two-step QGIS
workflow (create points, then join against the watershed layer). This
pipeline already resolves the watershed match inline during analysis
(`watershed_locator.py`, unchanged) — there's no separate join step here.
The "joined" file is the same points with those two columns surfaced, for
parity with what the manual workflow produces.

### 13.6 QA log

`src/teammate_metadata_writer.py: write_qa_log_xlsx()` →
`12_GEO_CODED_IMAGES/QA/QA_Log.xlsx` (via `openpyxl`). One row per image:
`image_id, file_name, coordinate_status, study_area_status, mws_id,
lulc_class, status, review_status, remarks` — the last two always blank,
same reasoning as §13.2.

### 13.7 Processing log

`src/teammate_metadata_writer.py: write_processing_log()` →
`12_GEO_CODED_IMAGES/Metadata/GeoCoded_Processing_Log.txt` — batch-level
counts (total, geotagged, missing GPS, invalid/malformed GPS, outside
study area, boundary review, watershed matched, LULC matched, errors),
CRS used, and which watershed field was used as the join key. Every
number is computed directly from the batch's own results, not estimated.

### 13.8 Running the full teammate-compatible pipeline

```python
from src.pipeline import run_pipeline
from src.image_id_ledger import ImageIdLedger
from src.io_writer import write_outputs
from src.teammate_metadata_writer import (
    write_photo_master_validated_csv, write_qa_log_xlsx, write_processing_log,
)
from src.teammate_gis_writer import write_photo_points_gpkg, write_photo_mws_joined_gpkg
from src import config

id_ledger = ImageIdLedger(config.IMAGE_ID_LEDGER_PATH)
results = run_pipeline("path/to/photos", id_ledger=id_ledger)

write_outputs(results)                    # outputs/*.csv, *.json
write_photo_master_validated_csv(results) # 12_GEO_CODED_IMAGES/Metadata/Photo_Master_Validated.csv
write_qa_log_xlsx(results)                # 12_GEO_CODED_IMAGES/QA/QA_Log.xlsx
write_processing_log(results)             # 12_GEO_CODED_IMAGES/Metadata/GeoCoded_Processing_Log.txt
write_photo_points_gpkg(results)          # 12_GEO_CODED_IMAGES/GIS/GEO_CODED_PHOTO_POINTS.gpkg
write_photo_mws_joined_gpkg(results)      # 12_GEO_CODED_IMAGES/GIS/GEO_CODED_PHOTO_MWS_JOINED.gpkg
```

Every writer accepts an optional explicit `path` argument if you want a
different location than the `config.py` defaults.

---

## Project structure

```
geo_coded/
├── requirements.txt
├── README.md                          (this file)
├── data/raw/
│   ├── study_area/shiggaon_boundary.gpkg
│   ├── micro_watersheds/shiggaon_micro_watersheds.gpkg
│   └── lulc/lulc_prediction.tif       (Model 1 output -- read-only, never modified)
├── docs/
│   ├── GEO_CODED_DATA_AUDIT.md        (Phase 1 dataset audit)
│   └── ARCHITECTURE.md                (module-by-module architecture)
├── src/
│   ├── config.py
│   ├── exceptions.py
│   ├── exif_reader.py
│   ├── coordinate_validator.py
│   ├── boundary_checker.py
│   ├── watershed_locator.py
│   ├── spatial_analyzer.py
│   ├── lulc_query.py
│   ├── geo_lulc_analyzer.py
│   ├── schema.py
│   ├── status_translator.py
│   ├── image_id_ledger.py
│   ├── image_analyzer.py
│   ├── pipeline.py
│   ├── io_writer.py
│   ├── teammate_metadata_writer.py
│   └── teammate_gis_writer.py
├── tests/                              (171 tests, see below)
├── outputs/                             (created on first pipeline run)
│   ├── geo_coded_results.csv
│   └── geo_coded_results.json
└── 12_GEO_CODED_IMAGES/                 (created on first teammate-writer run)
    ├── Metadata/
    │   ├── Photo_Master_Validated.csv
    │   ├── image_id_ledger.json
    │   └── GeoCoded_Processing_Log.txt
    ├── GIS/
    │   ├── GEO_CODED_PHOTO_POINTS.gpkg
    │   └── GEO_CODED_PHOTO_MWS_JOINED.gpkg
    └── QA/
        └── QA_Log.xlsx
```

## Running the tests

```bash
python -m pytest
```

171 tests, 0 warnings, 0 errors as of the last full run. Tests use a mix
of synthetic fixtures (fabricated JPEGs with controlled/malformed EXIF,
fabricated boundary/watershed geometries, fabricated small rasters) and
integration tests against the real Shiggaon datasets — see individual
test files for which is which.
