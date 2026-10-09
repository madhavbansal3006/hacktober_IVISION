# Water Quality Module — Shiggaon Watershed Intelligence System

## Purpose

This package is a small, self-contained backend/model module implementing a
simple water-quality scoring and simulation layer for the Shiggaon Taluk
(Haveri, Karnataka) Smart Watershed Monitoring / Decision Support System.

It is designed to be dropped into an existing FastAPI project later. **This
package does not contain a frontend, an API layer, IoT integration, or
forecasting.** It only implements the water-quality data model, the WQI
calculation, validation, and a deterministic simulator, as described below.

## The Four Parameters

The module works with exactly four water-quality parameters, as specified
for this release:

| Parameter    | Field name    | Unit  |
|--------------|---------------|-------|
| pH           | `ph`          | —     |
| TDS          | `tds`         | mg/L  |
| Turbidity    | `turbidity`   | NTU   |
| Temperature  | `temperature` | °C    |

## WQI Methodology

This module implements the **Weighted Arithmetic Water Quality Index**
method, a widely used generic approach for combining several water-quality
parameters into a single index. For each parameter *i*:

```
Qi = |Vi - Vo_i| / (Si - Vo_i) * 100      (quality rating)
Wi = K / Si                                (unit weight)
K  = 1 / sum(1 / Si for all parameters)
WQI = sum(Wi * Qi) / sum(Wi)
```

- `Vi` — the observed value of parameter *i*
- `Vo_i` — the "ideal" value of parameter *i* (0 for most pollutants, 7.0
  for pH)
- `Si` — the "standard"/permissible reference value of parameter *i*

**Important clarification:** this weighted-arithmetic formula is a generic,
widely-used method in water-quality literature. **It is not defined by BIS
10500** (or any single standard). BIS 10500 and similar references are only
one common *source of reference/permissible values* for parameters like pH,
TDS, and turbidity — they do not prescribe how those values should be
combined into an index.

### Assumptions — reference and weighting constants

The **exact Shiggaon project WQI constants were not provided** to this
module. Rather than pretend these are confirmed project values, the
constants below are documented here as explicit assumptions. They live in a
single place, `src/wqi.py :: PARAMETER_STANDARDS`, so they can be replaced
with official project-approved values without touching any calculation
logic.

| Parameter    | Ideal (`Vo`) | Standard (`Si`) | Basis (assumption) |
|--------------|--------------|------------------|---------------------|
| pH           | 7.0          | 8.5              | Commonly cited permissible upper limit for pH in Indian drinking-water quality literature (of which BIS 10500 is one well-known source). |
| TDS          | 0.0 mg/L     | 500 mg/L         | Commonly cited "desirable limit" for total dissolved solids. |
| Turbidity    | 0.0 NTU      | 5 NTU            | Commonly cited permissible turbidity limit. |
| Temperature  | 25.0 °C      | 30.0 °C          | **Weakest-justified parameter.** Temperature has no universal regulatory "quality limit" the way pH/TDS/turbidity do. 25 °C is assumed as a representative ambient baseline for the region, and 30 °C as an assumed acceptable upper deviation, purely so temperature can be expressed on the same 0–100 quality-rating scale. **This should be reviewed and replaced by the project team** with a locally validated value if/when available. |

If the Shiggaon project team has already defined its own reference values
and weights, update `PARAMETER_STANDARDS` in `src/wqi.py` — all downstream
calculations (weights, quality ratings, WQI, category) will use the new
values automatically.

### Quality Categories

The final WQI score is mapped to a category using the commonly used
weighted-arithmetic WQI bands:

| WQI range     | Category                 |
|---------------|---------------------------|
| 0 – 25        | Excellent                 |
| 25 – 50       | Good                      |
| 50 – 75       | Poor                      |
| 75 – 100      | Very Poor                 |
| > 100         | Unsuitable for Drinking   |

These bands are also an assumption based on common usage in the literature,
not a value confirmed by the Shiggaon project. They are defined in
`src/wqi.py :: QUALITY_CATEGORIES` and can be edited in one place.

## Data Schema

### Observation (input)

```json
{
    "id": "g_mws.240575",
    "MWS": "4D4F2m3",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "ph": 7.2,
    "tds": 350,
    "turbidity": 4.5,
    "temperature": 25.4,
    "source": "simulation"
}
```

- `id` — the canonical micro-watershed identifier (e.g. `g_mws.240575`).
  There are 66 official micro-watersheds in the Shiggaon Taluk study area.
- `MWS` — the hydrological/display code (e.g. `4D4F2m3`).
- `source` — one of `"simulation"`, `"historical"`, or `"live"`. **Only
  `"simulation"` is implemented in this release.** Records produced by
  `src/simulator.py` are always tagged `"source": "simulation"` and must
  never be treated as, or presented as, real Shiggaon measurements.

### Derived output

```json
{
    "wqi": 42.13,
    "quality_category": "Good"
}
```

Produced by `evaluate_observation()` in `src/wqi.py`.

## Simulator

`src/simulator.py :: generate_readings()` produces plausible, **synthetic**
sample readings for a given micro-watershed:

- Inputs: MWS `id`, MWS `code`, number of readings, optional random `seed`,
  optional `start_time`, and `interval_minutes` between readings.
- Every generated record is tagged `"source": "simulation"`.
- Passing the same `seed` (and other arguments) always produces identical
  output — the simulator is deterministic.
- Value ranges are chosen to be *plausible-looking* only; they are **not**
  derived from any actual Shiggaon Taluk measurement campaign.

## Validation

`src/wqi.py :: validate_observation()` performs simple, explicit checks:

- All four parameters must be present and numeric.
- `pH` must be within `[0, 14]`.
- `TDS` must be non-negative.
- `Turbidity` must be non-negative.
- `Temperature` must be within a generous but finite physical range
  (`-5 °C` to `60 °C`).
- If present, `source` must be one of `simulation`, `historical`, `live`.

Invalid observations raise `ObservationValidationError`. Validation is
intentionally simple — it is not a full schema/typing framework.

## Package Structure

```
water_quality/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── wqi.py
│   └── simulator.py
├── data/
│   └── sample_water_quality.csv
└── tests/
    ├── test_wqi.py
    └── test_simulator.py
```

## Running the tests

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

All 20 tests pass as of this release (see delivery notes / test report).

## Limitations

- **This package currently provides a simple water-quality calculation and
  simulation layer. Live IoT integration and forecasting are not
  implemented in this release.**
- No frontend and no API/HTTP layer are included — this is intended to be
  imported as a Python module by the existing FastAPI project.
- The WQI reference values, weights, and category bands are documented
  assumptions, not confirmed official Shiggaon project constants (see
  "Assumptions" above). They must be reviewed before any production or
  reporting use.
- The simulator generates synthetic data only. It must never be presented
  as, or confused with, real historical or live sensor readings.
- Validation is intentionally basic (range checks only); it does not
  attempt statistical outlier detection or cross-parameter plausibility
  checks.

## Future Integration

This module is intended to be imported into the existing FastAPI project
as a plain Python package (e.g. `from water_quality.src.wqi import
evaluate_observation`). Suggested next steps, out of scope for this
release:

- Expose `evaluate_observation()` and `generate_readings()` through
  FastAPI endpoints.
- Add a `"historical"` data loader once real historical records are
  available.
- Add a `"live"` ingestion path once IoT sensor integration exists.
- Add forecasting once a modeling approach is chosen by the project team.
- Replace the assumed `PARAMETER_STANDARDS` and `QUALITY_CATEGORIES`
  constants with official, project-approved values.
