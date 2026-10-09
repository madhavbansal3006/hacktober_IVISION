# Geo-Coded Image Module — Architecture

This document describes the module **as it exists on disk today**. It is
written after the fact, from the actual `src/` code, not from the design
proposed before implementation — so it reflects reality rather than the
original plan. Where the two differ (they do, in a few places — noted
inline), this document defers to the code.

No source code, tests, configuration, datasets, or outputs were changed
to produce this document.

---

## 1. Purpose

Given a geotagged JPEG, determine:

- its GPS coordinate,
- whether that coordinate falls inside the Shiggaon Taluk study-area
  boundary,
- if so, which micro-watershed it falls in,
- what Model 1's LULC raster classifies that exact pixel as,

and emit one structured result per image, plus batch CSV/JSON output.
Frontend, 3D visualization, GIS rendering, API/database, and IoT
integration are explicitly **not** part of this module.

## 2. Data inputs

| Input | Path | Format | Notes |
|---|---|---|---|
| Geotagged photograph | supplied by caller | JPEG | Must carry GPS EXIF (lat/lon + N/S/E/W refs) to be processed successfully; images without it still produce a result, with a failure status. |
| Study-area boundary | `data/raw/study_area/shiggaon_boundary.gpkg` | GeoPackage, EPSG:4326, 1 polygon feature | Model 1 dataset; read-only |
| Micro-watersheds | `data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg` | GeoPackage, EPSG:4326, 66 polygon features | Model 1 dataset; read-only. Not clipped to the boundary — many watersheds extend beyond it (see §5). |
| LULC raster | `data/raw/lulc/lulc_prediction.tif` | GeoTIFF, EPSG:32643, single band, uint8 | Model 1 output; read-only. No embedded class legend (see §8). |

All three dataset paths are defined once, in `src/config.py`, and every
module that needs them imports from there rather than hardcoding a path.

## 3. Module-by-module purpose

| Module | Purpose | Explicitly does NOT do |
|---|---|---|
| `src/config.py` | Single source of truth for dataset paths, CRS constants (`WGS84`, `RASTER_CRS`), the LULC class map, watershed field names, and default output paths. | Contains no logic — constants only. |
| `src/exceptions.py` | Typed exception hierarchy (`GeoCodedError` base; `NoGPSError`, `MalformedGPSError`, `InvalidCoordinateError`), each carrying the offending `image_path`. | Nothing beyond exception definitions. |
| `src/exif_reader.py` | `extract_gps(image_path) -> RawGPSData`: reads raw (unconverted) GPS EXIF — DMS components + hemisphere refs. Opens images read-only; never modifies them. | DMS→decimal conversion, coordinate validation, anything spatial. |
| `src/coordinate_validator.py` | `validate(raw: RawGPSData) -> ValidatedCoordinate`: converts DMS to signed decimal degrees, checks minutes/seconds < 60, checks final lat/lon are within valid WGS84 range, builds a `shapely.Point`. | Anything about the boundary, watersheds, or raster. |
| `src/boundary_checker.py` | `BoundaryChecker`: loads the Shiggaon boundary once; `is_inside(point) -> bool`. | Watershed or raster logic. |
| `src/watershed_locator.py` | `WatershedLocator`: loads all 66 micro-watersheds once with a spatial index (`STRtree`); `locate(point) -> WatershedMatch \| None`, returning `micro_watershed_id` (`id` field) and `mws_code` (`MWS` field). Ties between overlapping candidates (e.g. a point on a shared edge) are broken deterministically by smallest true area (reprojected to EPSG:32643 for the comparison, not degree-based). | Does not know about the boundary — the caller (`spatial_analyzer.py`) is responsible for checking boundary containment first. |
| `src/spatial_analyzer.py` | `SpatialAnalyzer`: combines `BoundaryChecker` + `WatershedLocator`. `analyze(lat, lon) -> SpatialResult` — boundary is always checked first; watershed lookup only runs for in-boundary points. | LULC/raster logic. |
| `src/lulc_query.py` | `LULCQuery`: loads the LULC raster once (full band into memory); `query(lat, lon) -> LULCResult`. Reprojects the WGS84 point into EPSG:32643, locates the pixel via the raster's own affine transform (`rasterio.transform.rowcol`, never manual pixel math), maps the raw value to a class name via `config.LULC_CLASS_MAP`, and computes a small (default 3×3) neighborhood purity/NoData-percentage diagnostic. | Boundary or watershed logic. |
| `src/geo_lulc_analyzer.py` | `GeoLULCAnalyzer`: combines `SpatialAnalyzer` + `LULCQuery` into `GeoCodedCoreResult`. LULC is skipped entirely for out-of-boundary points (never queried). Resolves the single reported `status` when multiple conditions are true at once, via the explicit `STATUS_PRIORITY` list (see §7). | EXIF extraction — operates on an already-validated coordinate, not an image path. |
| `src/schema.py` | Defines `GeoCodedResult`, the final per-image output shape, plus the EXIF/coordinate-stage status constants (`STATUS_NO_GPS`, `STATUS_MALFORMED_GPS`, `STATUS_INVALID_COORDINATE`, `STATUS_ERROR`). Every field is present on every result (never a partial dict) — inapplicable fields are explicit `None`. | No logic — dataclass + constants only. |
| `src/image_analyzer.py` | `analyze_image(image_path, analyzer) -> GeoCodedResult`: the full per-image orchestration — EXIF → coordinate validation → `GeoLULCAnalyzer`. Catches every anticipated exception (`NoGPSError`, `MalformedGPSError`, `InvalidCoordinateError`, `FileNotFoundError`) plus any unanticipated one, turning each into a result with the appropriate status and `error_reason`. **Never raises.** | Batch iteration, file discovery, CSV/JSON writing. |
| `src/pipeline.py` | `find_images(dir)` and `run_pipeline(image_dir, analyzer=None) -> list[GeoCodedResult]`: discovers `.jpg`/`.jpeg` files (case-insensitive) in a folder and calls `analyze_image` on each, collecting every result. Wraps each call in a defensive `try/except` as a final backstop beyond `image_analyzer`'s own exhaustive handling. | Per-image spatial/LULC logic — delegates entirely to `image_analyzer`. |
| `src/io_writer.py` | `write_csv`, `write_json`, `write_outputs`: serializes a `list[GeoCodedResult]` to disk. CSV via Python's built-in `csv` module (not pandas — not a dependency of this module); JSON via `json.dumps` directly, relying on every `GeoCodedResult` field already being a native Python type. | Any spatial computation. |

## 4. Processing flow

```
Geo-tagged JPEG (image_path)
        │
        ▼
exif_reader.extract_gps(image_path)
        │  raises NoGPSError / MalformedGPSError
        │  → image_analyzer catches → GeoCodedResult(status=NO_GPS / MALFORMED_GPS)
        ▼
RawGPSData (DMS + hemisphere refs)
        │
        ▼
coordinate_validator.validate(raw)
        │  raises InvalidCoordinateError
        │  → image_analyzer catches → GeoCodedResult(status=INVALID_COORDINATE)
        ▼
ValidatedCoordinate (decimal lat/lon, shapely Point, EPSG:4326)
        │
        ▼
GeoLULCAnalyzer.analyze(lat, lon)
        │
        ├─► SpatialAnalyzer.analyze(lat, lon)
        │      │
        │      ├─► BoundaryChecker.is_inside(point)
        │      │      │
        │      │      └─ False → SpatialResult(status=OUTSIDE_STUDY_AREA)
        │      │                  → GeoLULCAnalyzer returns immediately;
        │      │                    LULC raster is NEVER queried for this point
        │      │
        │      └─ True → WatershedLocator.locate(point)
        │                   │
        │                   ├─ None  → SpatialResult(status=NO_WATERSHED_MATCH)
        │                   └─ Match → SpatialResult(status=WATERSHED_MATCHED,
        │                               micro_watershed_id, mws_code)
        │
        └─► (only if inside boundary) LULCQuery.query(lat, lon)
               │
               ├─► reproject point WGS84 → EPSG:32643
               ├─► rasterio.transform.rowcol(transform, x, y) → (row, col)
               ├─► out of raster grid → LULCResult(status=OUTSIDE_RASTER_EXTENT)
               ├─► raw pixel == declared NoData → LULCResult(status=NODATA_PIXEL)
               └─► otherwise → LULCResult(status=OK, lulc_value, lulc_class,
                                            neighborhood purity/NoData stats)
        │
        ▼
_resolve_status(spatial.status, lulc.status)   [see §7 — STATUS_PRIORITY]
        │
        ▼
GeoCodedCoreResult (spatial + LULC fields, single resolved status)
        │
        ▼
image_analyzer wraps with image_name, processing_timestamp,
schema_version, error_reason=None → GeoCodedResult
        │
        ▼
pipeline.run_pipeline() collects one GeoCodedResult per image in a folder
        │
        ▼
io_writer.write_outputs() → outputs/geo_coded_results.csv
                             outputs/geo_coded_results.json
```

Any unanticipated exception at any stage inside `analyze_image` (not just
the four typed exceptions above) is also caught and turned into a result
with `status=ERROR` — a single bad image cannot raise past `analyze_image`
or stop `run_pipeline`'s batch loop.

## 5. Output schema

`src/schema.py: GeoCodedResult` — every field present on every result,
`None` where not applicable:

| Field | Type |
|---|---|
| `schema_version` | `str` (currently `"1.0"`) |
| `image_name` | `str` — filename only |
| `processing_timestamp` | `str` — ISO 8601 UTC, wall-clock processing time (not EXIF capture time) |
| `latitude`, `longitude` | `float \| None` |
| `status` | `str` — see §7 |
| `error_reason` | `str \| None` |
| `inside_study_area` | `bool \| None` |
| `micro_watershed_id` | `str \| None` — see §6 |
| `mws_code` | `str \| None` — see §6 |
| `lulc_value` | `int \| None` — raw raster pixel value |
| `lulc_class` | `str \| None` — mapped class name, see §8 |
| `raster_pixel_row`, `raster_pixel_col` | `int \| None` |
| `lulc_neighborhood_window_size` | `int \| None` — default 3 |
| `lulc_neighborhood_class_purity_pct` | `float \| None` |
| `lulc_neighborhood_nodata_pct` | `float \| None` |

The three `lulc_neighborhood_*` fields are a Phase 5 addition beyond what
was originally scoped — a rough homogeneity diagnostic, not something
independently requested by name. They exist in the current schema; drop
them downstream if not useful.

## 6. `micro_watershed_id` and `mws_code`

An explicit, deliberate decision, implemented in `watershed_locator.py`
and reused everywhere downstream:

- **`micro_watershed_id` = the `id` field** of the micro-watershed layer
  (e.g. `"g_mws.240575"`) — the cross-module integration key.
- **`mws_code` = the `MWS` field** (e.g. `"4D4F2m3"`) — the hydrological
  watershed identifier, kept separate.

Both are populated together on a successful watershed match; both are
`None` together when there's no match (`OUTSIDE_STUDY_AREA` or
`NO_WATERSHED_MATCH`).

## 7. Status values and priority

Defined across three modules (not centralized into one status file — this
is a real characteristic of the current code, not an oversight being
described as a feature):

- `spatial_analyzer.py`: `STATUS_OUTSIDE_STUDY_AREA`, `STATUS_NO_WATERSHED_MATCH`, `STATUS_WATERSHED_MATCHED`
- `lulc_query.py`: `STATUS_OK`, `STATUS_NODATA_PIXEL`, `STATUS_OUTSIDE_RASTER_EXTENT`
- `schema.py`: `STATUS_NO_GPS`, `STATUS_MALFORMED_GPS`, `STATUS_INVALID_COORDINATE`, `STATUS_ERROR`
- `geo_lulc_analyzer.py`: `STATUS_OK` (the final "everything resolved" status used in the combined result — distinct from `lulc_query.py`'s own internal `STATUS_OK`, which only means "this pixel has data")

| Status | Meaning |
|---|---|
| `OK` | Boundary check passed, watershed matched, LULC pixel has data. |
| `NO_GPS` | No GPS EXIF in the image. |
| `MALFORMED_GPS` | GPS EXIF present but malformed (bad ref, wrong shape, missing tag). |
| `INVALID_COORDINATE` | Coordinate out of valid WGS84 range, or DMS minutes/seconds ≥ 60. |
| `OUTSIDE_STUDY_AREA` | Valid coordinate, outside the Shiggaon boundary. LULC never queried. |
| `NO_WATERSHED_MATCH` | Inside boundary, but no watershed polygon covers this exact point. LULC is still queried. |
| `NODATA_PIXEL` | Watershed matched, but the raster pixel at this point is NoData. |
| `OUTSIDE_RASTER_EXTENT` | Inside boundary but off the raster's pixel grid entirely. |
| `ERROR` | Any unanticipated failure; check `error_reason`. |

**When more than one condition is true simultaneously**, only one status
is reported, chosen by `geo_lulc_analyzer.py: STATUS_PRIORITY` — an
explicit, ordered, reorderable list (not an if/elif chain), current order:

```
OUTSIDE_STUDY_AREA > OUTSIDE_RASTER_EXTENT > NO_WATERSHED_MATCH > NODATA_PIXEL > OK
```

The resolution logic lives in `_resolve_status()`, unit-tested in
isolation from the rest of the analyzer (`tests/test_geo_lulc_analyzer.py:
TestStatusPriorityResolution`). This ordering is documented as a
deliberately swappable implementation decision — changing it is a
one-line reorder of `STATUS_PRIORITY`, and does not require touching the
underlying boundary/watershed/raster analysis at all.

## 8. LULC class mapping — user-confirmed, not source-code verified

`src/config.py: LULC_CLASS_MAP`:

```python
{0: "NODATA", 1: "Forest", 2: "Agriculture", 3: "Water", 4: "Built-up", 5: "Barren"}
```

**This has not been verified against Model 1's training or export code.**
No such code, notebook, or label-encoder artifact has ever been provided
to the sessions that built this module — confirmed by direct filesystem
search, more than once, including immediately before this document was
written. `lulc_prediction.tif` itself carries no embedded class legend:
every metadata channel the GeoTIFF format supports (tags across all
namespaces, band description, colormap/RAT) was inspected and found
empty of class semantics. The mapping above comes entirely from an
explicit statement made by the person building Model 1, describing it as
fixed. If Model 1's actual training/export code ever becomes available,
cross-check it against this dict before relying on `lulc_class` for
anything beyond a hackathon demo — nothing else in this module depends on
the specific values, so a correction is a one-place change.

## 9. Integration entry points

Two functions are the entire public surface this module expects other
teammates to use:

- **`src/image_analyzer.py: analyze_image(image_path, analyzer) -> GeoCodedResult`**
  Process one image. Never raises.
- **`src/pipeline.py: run_pipeline(image_dir, analyzer=None) -> list[GeoCodedResult]`**
  Process every JPEG in a folder. Constructs a `GeoLULCAnalyzer` (loading
  boundary/watershed/raster once) if none is passed in.

Both return `GeoCodedResult` dataclasses — `dataclasses.asdict()` +
`json.dumps()` works directly on them with no custom encoder, verified in
`tests/test_io_writer.py` and `tests/test_geo_lulc_analyzer.py`.

## 10. How the GIS teammate consumes results

- Read `outputs/geo_coded_results.csv` or `.json` (written by
  `io_writer.write_outputs`), or call `run_pipeline()` directly from
  Python and work with the returned list in memory — no shared runtime
  state, no live connection to set up.
- **Join key back into the watershed layer**: `micro_watershed_id` in the
  output matches the `id` field in
  `data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg` exactly —
  same values, same type (string).
- This module does not render anything — no map, no frontend, no API. It
  is a pure function from "folder of photos" to "CSV/JSON of geospatial +
  LULC facts about each one," and the GIS module is expected to do all
  rendering on its own side using that output plus the same watershed
  GeoPackage.

---

## 11. Teammate handover layer (added after this doc's initial version)

A second wave of modules was added on top of everything in §1–10, to make
this module's output compatible with
`SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx` (a downstream
teammate's own required workflow doc). None of the modules or logic in
§1–10 were rewritten to do this — this layer is additive:

| Module | Purpose |
|---|---|
| `src/image_id_ledger.py` | `ImageIdLedger`: persistent `IMG_0001`-style ID assignment, backed by a single local JSON file (explicitly not a database). Keyed by file content hash (SHA-256), not filename. IDs are never reused, even after manual entry deletion, via a monotonic counter independent of current entries. **Opt-in**: `analyze_image()`/`run_pipeline()` only touch a ledger if one is explicitly passed in; omitting it leaves `image_id=None` with zero disk I/O. |
| `src/status_translator.py` | `translate_status()`: pure function deriving `coordinate_status` (`VALID`/`MISSING`/`SUSPICIOUS`/`OUTSIDE_STUDY_AREA`) and `study_area_status` (`INSIDE`/`BOUNDARY_REVIEW`/`OUTSIDE`) from the existing internal `status` + `inside_study_area` + a new boundary-distance check. Does not alter or replace the internal status system. |
| `src/teammate_metadata_writer.py` | Writes `Photo_Master_Validated.csv`, `QA_Log.xlsx` (via `openpyxl`), and the batch-level `GeoCoded_Processing_Log.txt`. Human-review columns (`observation_type`, `description`, `photo_quality`, `evidence_relevance`, `intervention_type`, `remarks`, `review_status`, `reviewer`) are always written blank — this module has no image-content understanding and does not invent values for them. |
| `src/teammate_gis_writer.py` | Writes `GEO_CODED_PHOTO_POINTS.gpkg` and `GEO_CODED_PHOTO_MWS_JOINED.gpkg` (EPSG:4326, via `geopandas`). Includes only results with a valid coordinate. Does not perform a separate spatial join — the watershed match is already resolved inline by the existing `watershed_locator.py`, unchanged; the "joined" file just surfaces `mws_id`/`mws_code` as columns. |

**Extensions to existing modules, all additive (new methods/fields with
defaults, no existing signature or behavior changed):**

- `boundary_checker.py: BoundaryChecker.distance_to_boundary_m(point)` —
  new method. Reprojects to EPSG:32643 (same CRS as the raster) and
  measures distance to the boundary polygon's edge, not its filled area
  — meaningful whether the point is inside or outside. Used only to
  decide `BOUNDARY_REVIEW`; the boundary geometry itself, and
  `is_inside()`'s strict containment semantics, are unchanged.
- `spatial_analyzer.py: SpatialAnalyzer.boundary_checker` and
  `geo_lulc_analyzer.py: GeoLULCAnalyzer.boundary_checker` — new
  read-only properties exposing the underlying `BoundaryChecker` (which
  was already being constructed internally), so `image_analyzer.py` can
  call `distance_to_boundary_m()` without reaching into a private
  attribute.
- `exif_reader.py: RawGPSData` — two new optional fields
  (`capture_datetime_raw`, `gps_accuracy_m`), both defaulted to `None` so
  every existing construction of this dataclass is unaffected. Populated
  best-effort from EXIF `DateTimeOriginal` (Exif sub-IFD) and
  `GPSHPositioningError` (GPS IFD) respectively — absence of either never
  affects whether `extract_gps()` succeeds. A new `parse_capture_datetime()`
  function converts the raw EXIF datetime string to ISO-8601 shape,
  explicitly preserving the camera's LOCAL time (EXIF carries no
  timezone) — not to be confused with `processing_timestamp`, which is
  wall-clock UTC.
- `schema.py: GeoCodedResult` — seven new optional fields, all defaulted
  to `None`, appended after the existing fields: `image_id`, `file_path`,
  `capture_datetime`, `gps_source`, `gps_accuracy_m`, `coordinate_status`,
  `study_area_status`. The existing CSV/JSON writer (`io_writer.py`,
  unchanged) derives its column list from this dataclass, so it picks up
  the new fields automatically.
- `image_analyzer.py: analyze_image()` gained one new optional parameter,
  `id_ledger` (default `None`) — every existing call site continues to
  work unchanged. `pipeline.py: run_pipeline()` gained the same, threaded
  through to `analyze_image()`.

**`mws_id` resolution**: the teammate README's own text defers the choice
of which watershed-layer field `mws_id` should be to "confirm with the
main GIS teammate." The user explicitly resolved this: `mws_id` = the
`id` field, identical in value to the already-established
`micro_watershed_id`. This is implemented as a column rename at the
export layer only (`teammate_metadata_writer.py`, `teammate_gis_writer.py`)
— `micro_watershed_id` and `mws_code` on `GeoCodedResult` itself are
unchanged.

**`BOUNDARY_REVIEW_TOLERANCE_M`** (`config.py`, default 15.0 meters) is
the single place this tolerance is defined. Changing it changes when
`BOUNDARY_REVIEW` is triggered without touching any boundary geometry or
any other module.

---

## Where this document differs from the original pre-implementation plan

Documented explicitly rather than silently, since a few things did not
end up exactly as first proposed:

- The original plan proposed a single `analyzer.py`. In the actual code
  this responsibility is split across `spatial_analyzer.py` (boundary +
  watershed only), `geo_lulc_analyzer.py` (+ LULC), and
  `image_analyzer.py` (+ EXIF, the true final per-image orchestrator).
- Status constants are spread across four modules rather than centralized
  into one, as noted in §7.
- The neighborhood-purity/NoData-percentage fields in the output schema
  were not part of the original output spec — added during LULC query
  implementation as a reasonable interpretation of "relevant statistics,"
  and flagged as such at the time.
