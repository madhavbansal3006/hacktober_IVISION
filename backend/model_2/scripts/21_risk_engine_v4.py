import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# ============================================================
# MODEL 2 — RISK ENGINE V4
# CALIBRATED HYBRID RISK ENGINE
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = BASE_DIR / "data" / "processed" / "model2_features_v6.csv"
OUTPUT = BASE_DIR / "data" / "processed" / "risk_assessment_v4.csv"

TRAIN_END_YEAR = 2023
HOLDOUT_START_YEAR = 2024

print("=" * 70)
print("MODEL 2 RISK ENGINE V4")
print("CALIBRATED HYBRID RISK ENGINE")
print("=" * 70)


# ============================================================
# 1. LOAD DATA
# ============================================================

print("\nLoading Model 2 V6 dataset...")

df = pd.read_csv(INPUT)

print(f"Rows: {len(df)}")
print(f"Watersheds: {df['id'].nunique()}")
print(f"Years: {df['year'].min()} - {df['year'].max()}")


# ============================================================
# 2. TEMPORAL SPLIT
# ============================================================

train_mask = df["year"] <= TRAIN_END_YEAR
holdout_mask = df["year"] >= HOLDOUT_START_YEAR

print("\nTemporal split:")

print(
    f"Training period: "
    f"{df.loc[train_mask, 'year'].min()}–{TRAIN_END_YEAR}"
)

print(
    f"Training observations: "
    f"{train_mask.sum()}"
)

print(
    f"Holdout period: "
    f"{HOLDOUT_START_YEAR}–"
    f"{df.loc[holdout_mask, 'year'].max()}"
)

print(
    f"Holdout observations: "
    f"{holdout_mask.sum()}"
)


# ============================================================
# 3. HELPER
# ============================================================

def percentile_score(series):
    """
    Convert a variable to a 0–100 percentile score.
    Higher = greater contribution to risk.
    """

    return (
        series.rank(
            method="average",
            pct=True
        ) * 100
    )


# ============================================================
# 4. WATER-STRESS RISK
# ============================================================

print("\nCalculating water-stress risk...")

rainfall_component = (
    100 - percentile_score(df["rainfall_mm"])
)

ndvi_component = (
    100 - percentile_score(df["ndvi"])
)

rainfall_anomaly_component = (
    100 - percentile_score(df["rainfall_anomaly"])
)

df["water_stress_score"] = (
    0.40 * rainfall_component
    + 0.30 * ndvi_component
    + 0.30 * rainfall_anomaly_component
)


# ============================================================
# 5. FLOOD / RUNOFF RISK
# ============================================================

print("Calculating flood/runoff risk...")

rain_intensity = percentile_score(
    df["max_daily_rainfall_mm"]
)

rain_intensity_anomaly = percentile_score(
    df["max_daily_rainfall_anomaly"]
)

rainy_days_component = percentile_score(
    df["rainy_days"]
)

slope_component = percentile_score(
    df["slope_mean"]
)

drainage_component = percentile_score(
    df["drainage_density"]
)

df["flood_risk_score"] = (
    0.30 * rain_intensity
    + 0.25 * rain_intensity_anomaly
    + 0.15 * rainy_days_component
    + 0.20 * slope_component
    + 0.10 * drainage_component
)


# ============================================================
# 6. ECOSYSTEM PRESSURE
# ============================================================

print("Calculating ecosystem pressure...")

builtup_component = percentile_score(
    df["builtup_pct"]
)

agriculture_component = percentile_score(
    df["agriculture_pct"]
)

forest_component = (
    100 - percentile_score(df["forest_pct"])
)

ndvi_pressure = (
    100 - percentile_score(df["ndvi"])
)

df["ecosystem_risk_score"] = (
    0.30 * builtup_component
    + 0.25 * agriculture_component
    + 0.20 * forest_component
    + 0.25 * ndvi_pressure
)


# ============================================================
# 7. BASE ENVIRONMENTAL RISK
# ============================================================

print("Calculating base environmental risk...")

df["base_risk_score"] = (
    0.40 * df["water_stress_score"]
    + 0.35 * df["flood_risk_score"]
    + 0.25 * df["ecosystem_risk_score"]
)


# ============================================================
# 8. ISOLATION FOREST
# ============================================================

print("\nPreparing ML anomaly detector...")


ML_FEATURES = [
    # Current environmental state
    "rainfall_mm",
    "max_daily_rainfall_mm",
    "rainy_days",
    "ndvi",

    # Temporal anomalies
    "rainfall_anomaly",
    "max_daily_rainfall_anomaly",
    "rainy_days_anomaly",
    "ndvi_anomaly",

    # Terrain
    "elevation_mean",
    "elevation_range",
    "slope_mean",
    "slope_std",

    # Soil
    "clay_mean",
    "sand_mean",
    "silt_mean",
    "soc_mean",

    # Hydrology
    "stream_length_km",
    "drainage_density",
    "max_river_order",
    "mean_river_order",
    "lake_count",
    "lake_area_km2",

    # LULC
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "barren_pct",
]

print(f"ML features: {len(ML_FEATURES)}")


# ============================================================
# 9. PREPARE FEATURES
# ============================================================

X = df[ML_FEATURES].copy()

for column in ML_FEATURES:

    X[column] = pd.to_numeric(
        X[column],
        errors="coerce"
    )

X = X.replace(
    [np.inf, -np.inf],
    np.nan
)

# TRAINING-ONLY imputation
train_medians = X.loc[train_mask].median()

X = X.fillna(train_medians)
X = X.fillna(0)


# ============================================================
# 10. SCALE
# ============================================================

scaler = StandardScaler()

X_train = scaler.fit_transform(
    X.loc[train_mask]
)

X_holdout = scaler.transform(
    X.loc[holdout_mask]
)


# ============================================================
# 11. TRAIN ISOLATION FOREST
# ============================================================

print("\nTraining Isolation Forest...")

iso_forest = IsolationForest(
    n_estimators=300,
    contamination="auto",
    random_state=42,
    n_jobs=-1
)

iso_forest.fit(X_train)


# ============================================================
# 12. RAW ANOMALY SCORES
# ============================================================

train_raw = -iso_forest.decision_function(
    X_train
)

holdout_raw = -iso_forest.decision_function(
    X_holdout
)


# ============================================================
# 13. ROBUST ML ANOMALY NORMALIZATION
# ============================================================

# Instead of forcing the anomaly score to become a major
# percentage of the final risk, we convert it to a centered
# 0–100 indicator for interpretability.

train_median = np.median(train_raw)

train_mad = np.median(
    np.abs(train_raw - train_median)
)

if train_mad <= 0:

    train_mad = np.std(train_raw)

if train_mad <= 0:

    train_mad = 1.0


def normalize_ml_score(raw):

    score = (
        50
        + 20 * (
            (raw - train_median)
            / train_mad
        )
    )

    return np.clip(
        score,
        0,
        100
    )


train_ml_score = normalize_ml_score(
    train_raw
)

holdout_ml_score = normalize_ml_score(
    holdout_raw
)

df.loc[
    train_mask,
    "ml_anomaly_score"
] = train_ml_score

df.loc[
    holdout_mask,
    "ml_anomaly_score"
] = holdout_ml_score


# ============================================================
# 14. TEMPORAL WARNING SIGNALS
# ============================================================

print("\nDetecting temporal warning signals...")


# Strong positive extreme-rainfall anomaly
df["flood_warning_signal"] = (
    df["max_daily_rainfall_anomaly"] >= 1.5
)


# Strong negative rainfall anomaly
df["water_stress_warning_signal"] = (
    df["rainfall_anomaly"] <= -1.0
)


# Strong vegetation decline
df["ecosystem_warning_signal"] = (
    df["ndvi_anomaly"] <= -1.0
)


# ============================================================
# 15. CALIBRATED ML ADJUSTMENT
# ============================================================

print("Applying calibrated ML adjustment...")


# Base environmental risk remains dominant.
#
# ML is a modifier:
#
# ML score 50 → no adjustment
# ML score 75 → positive adjustment
# ML score 25 → negative adjustment
#
# Maximum adjustment = ±7 points.

ml_adjustment = (
    (df["ml_anomaly_score"] - 50)
    / 50
    * 7
)


# ============================================================
# 16. TEMPORAL WARNING ADJUSTMENT
# ============================================================

warning_adjustment = np.zeros(
    len(df)
)


# Strong flood signal
warning_adjustment += np.where(
    df["flood_warning_signal"],
    3.0,
    0.0
)


# Strong water-stress signal
warning_adjustment += np.where(
    df["water_stress_warning_signal"],
    3.0,
    0.0
)


# Strong ecosystem signal
warning_adjustment += np.where(
    df["ecosystem_warning_signal"],
    2.0,
    0.0
)


# ============================================================
# 17. FINAL RISK
# ============================================================

df["ml_adjustment"] = ml_adjustment

df["temporal_warning_adjustment"] = (
    warning_adjustment
)

df["final_risk_score"] = (
    df["base_risk_score"]
    + df["ml_adjustment"]
    + df["temporal_warning_adjustment"]
)

# Keep score within 0–100
df["final_risk_score"] = np.clip(
    df["final_risk_score"],
    0,
    100
)


# ============================================================
# 18. PRIMARY DRIVER
# ============================================================

components = pd.DataFrame({
    "Water Stress": df["water_stress_score"],
    "Flood/Runoff": df["flood_risk_score"],
    "Ecosystem Pressure": df["ecosystem_risk_score"],
})

df["primary_risk_driver"] = (
    components.idxmax(axis=1)
)


# ============================================================
# 19. RISK CATEGORIES
# ============================================================

print("Creating risk categories...")


def classify_risk(score):

    if score < 40:
        return "LOW"

    elif score < 55:
        return "MODERATE"

    elif score < 70:
        return "HIGH"

    return "CRITICAL"


df["risk_category"] = (
    df["final_risk_score"]
    .apply(classify_risk)
)


# ============================================================
# 20. RISK DRIVERS
# ============================================================

def get_risk_drivers(row):

    drivers = []

    # Environmental drivers

    if row["water_stress_score"] >= 60:

        drivers.append(
            "Water stress"
        )

    if row["flood_risk_score"] >= 60:

        drivers.append(
            "Flood/runoff susceptibility"
        )

    if row["ecosystem_risk_score"] >= 60:

        drivers.append(
            "Ecosystem degradation"
        )

    # Temporal warning signals

    if row["rainfall_anomaly"] <= -1:

        drivers.append(
            "Emerging water-stress signal"
        )

    if row["max_daily_rainfall_anomaly"] >= 1:

        drivers.append(
            "Emerging flood/runoff signal"
        )

    if row["ndvi_anomaly"] <= -1:

        drivers.append(
            "Emerging ecosystem-pressure signal"
        )

    if not drivers:

        drivers.append(
            "No dominant environmental pressure"
        )

    return "; ".join(
        dict.fromkeys(drivers)
    )


df["risk_drivers"] = (
    df.apply(
        get_risk_drivers,
        axis=1
    )
)


# ============================================================
# 21. LULC CONFIDENCE
# ============================================================

def coverage_confidence(category):

    category = str(
        category
    ).upper()

    if category == "GOOD":
        return "HIGH"

    if category == "ACCEPTABLE":
        return "MODERATE"

    if category == "LOW":
        return "LOW"

    if category == "INSUFFICIENT_DATA":
        return "VERY LOW"

    return "UNKNOWN"


df["lulc_confidence"] = (
    df["lulc_coverage_category"]
    .apply(coverage_confidence)
)


# ============================================================
# 22. DATA CONFIDENCE
# ============================================================

def data_confidence(row):

    coverage = row[
        "lulc_coverage_pct"
    ]

    if coverage >= 80:
        return "HIGH"

    elif coverage >= 40:
        return "MODERATE"

    elif coverage >= 10:
        return "LOW"

    return "VERY LOW"


df["data_confidence"] = (
    df.apply(
        data_confidence,
        axis=1
    )
)


# ============================================================
# 23. OUTPUT
# ============================================================

OUTPUT_COLUMNS = [
    "id",
    "year",
    "month",

    "water_stress_score",
    "flood_risk_score",
    "ecosystem_risk_score",

    "base_risk_score",

    "rainfall_anomaly",
    "max_daily_rainfall_anomaly",
    "rainy_days_anomaly",
    "ndvi_anomaly",

    "ml_anomaly_score",
    "ml_adjustment",

    "flood_warning_signal",
    "water_stress_warning_signal",
    "ecosystem_warning_signal",

    "temporal_warning_adjustment",

    "final_risk_score",
    "risk_category",

    "primary_risk_driver",
    "risk_drivers",

    "lulc_coverage_pct",
    "lulc_coverage_category",
    "lulc_confidence",
    "data_confidence",
]


result = df[
    OUTPUT_COLUMNS
].copy()


result.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# 24. REPORT
# ============================================================

print("\n" + "=" * 70)
print("RISK ENGINE V4 COMPLETE")
print("=" * 70)

print(f"Output: {OUTPUT}")

print(
    f"\nRows: {len(result)}"
)

print(
    f"Watersheds: "
    f"{result['id'].nunique()}"
)


print("\nRisk categories:")

print(
    result["risk_category"]
    .value_counts()
    .sort_index()
    .to_string()
)


print("\nFinal risk statistics:")

print(
    result["final_risk_score"]
    .describe()
    .round(2)
    .to_string()
)


print("\nML anomaly statistics:")

print(
    result["ml_anomaly_score"]
    .describe()
    .round(2)
    .to_string()
)


print("\nML adjustment statistics:")

print(
    result["ml_adjustment"]
    .describe()
    .round(2)
    .to_string()
)


print("\nTemporal warning adjustment:")

print(
    result["temporal_warning_adjustment"]
    .describe()
    .round(2)
    .to_string()
)


print("\nPrimary drivers:")

print(
    result["primary_risk_driver"]
    .value_counts()
    .to_string()
)


print("\nLULC confidence:")

print(
    result["lulc_confidence"]
    .value_counts()
    .to_string()
)


# ============================================================
# 25. HOLDOUT REPORT
# ============================================================

print("\n" + "=" * 70)
print("HOLDOUT PERIOD: 2024–2025")
print("=" * 70)

holdout_result = result[
    result["year"] >= HOLDOUT_START_YEAR
]

print(
    holdout_result[
        [
            "final_risk_score",
            "ml_anomaly_score",
            "ml_adjustment",
            "temporal_warning_adjustment",
        ]
    ]
    .describe()
    .round(2)
    .to_string()
)


print("\nHoldout risk categories:")

print(
    holdout_result[
        "risk_category"
    ]
    .value_counts()
    .sort_index()
    .to_string()
)


print("\nWarning signals in holdout:")

print(
    "Flood warning:",
    int(
        holdout_result[
            "flood_warning_signal"
        ].sum()
    )
)

print(
    "Water-stress warning:",
    int(
        holdout_result[
            "water_stress_warning_signal"
        ].sum()
    )
)

print(
    "Ecosystem warning:",
    int(
        holdout_result[
            "ecosystem_warning_signal"
        ].sum()
    )
)


# ============================================================
# 26. SAMPLE
# ============================================================

print("\nSample:")

print(
    result.head(10).to_string(
        index=False
    )
)


print("\n" + "=" * 70)
print("VALIDATION NOTES")
print("=" * 70)

print(
    "✓ V2 was NOT modified."
)

print(
    "✓ V3 was NOT modified."
)

print(
    "✓ V6 temporal anomalies used."
)

print(
    "✓ Isolation Forest trained only on 2017–2023."
)

print(
    "✓ 2024–2025 treated as holdout."
)

print(
    "✓ ML acts as a bounded risk modifier."
)

print(
    "✓ Temporal warning signals provide "
    "additional risk adjustments."
)

print(
    "✓ LULC coverage affects confidence, "
    "not environmental risk."
)

print(
    "\nRisk Engine V4 is ready for comparison "
    "against V2 and V3."
)