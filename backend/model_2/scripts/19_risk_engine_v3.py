import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# ============================================================
# MODEL 2 — RISK ENGINE V3
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = BASE_DIR / "data" / "processed" / "model2_features_v6.csv"
OUTPUT = BASE_DIR / "data" / "processed" / "risk_assessment_v3.csv"

TRAIN_END_YEAR = 2023
HOLDOUT_START_YEAR = 2024

print("=" * 70)
print("MODEL 2 RISK ENGINE V3")
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
# 3. ENVIRONMENTAL RISK COMPONENTS
# ============================================================

print("\nCalculating water-stress risk...")


def percentile_score(series):
    """
    Convert a variable into a 0–100 percentile score.
    Higher = greater contribution to risk.
    """

    return (
        series.rank(
            method="average",
            pct=True
        ) * 100
    )


# ------------------------------------------------------------
# Water stress
# ------------------------------------------------------------

# Lower rainfall and lower NDVI can indicate water stress.
# We therefore invert their percentile contribution.

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


# ------------------------------------------------------------
# Flood / runoff
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Ecosystem pressure
# ------------------------------------------------------------

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
# 4. BASE ENVIRONMENTAL RISK
# ============================================================

print("Calculating base environmental risk...")

df["base_risk_score"] = (
    0.40 * df["water_stress_score"]
    + 0.35 * df["flood_risk_score"]
    + 0.25 * df["ecosystem_risk_score"]
)


# ============================================================
# 5. ML ANOMALY DETECTOR
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
# 6. PREPARE ML DATA
# ============================================================

X = df[ML_FEATURES].copy()

# Numeric conversion
for column in ML_FEATURES:
    X[column] = pd.to_numeric(
        X[column],
        errors="coerce"
    )

# Replace infinite values
X = X.replace(
    [np.inf, -np.inf],
    np.nan
)

# Median imputation using TRAINING data only
train_medians = X.loc[train_mask].median()

X = X.fillna(train_medians)

# Final fallback
X = X.fillna(0)


# ============================================================
# 7. STANDARDIZE
# ============================================================

scaler = StandardScaler()

X_train = scaler.fit_transform(
    X.loc[train_mask]
)

X_holdout = scaler.transform(
    X.loc[holdout_mask]
)


# ============================================================
# 8. TRAIN ISOLATION FOREST
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
# 9. CONVERT ANOMALY SCORES TO 0–100
# ============================================================

train_raw = -iso_forest.decision_function(
    X_train
)

holdout_raw = -iso_forest.decision_function(
    X_holdout
)

# Fit score range ONLY using training observations.
train_min = train_raw.min()
train_max = train_raw.max()

if train_max == train_min:
    train_scores = np.full(
        len(train_raw),
        50.0
    )

    holdout_scores = np.full(
        len(holdout_raw),
        50.0
    )

else:

    train_scores = (
        (train_raw - train_min)
        / (train_max - train_min)
        * 100
    )

    holdout_scores = (
        (holdout_raw - train_min)
        / (train_max - train_min)
        * 100
    )

    # Holdout values can legitimately fall outside
    # the training range, so clip only for score stability.
    holdout_scores = np.clip(
        holdout_scores,
        0,
        100
    )


df.loc[train_mask, "ml_anomaly_score"] = train_scores

df.loc[
    holdout_mask,
    "ml_anomaly_score"
] = holdout_scores


# ============================================================
# 10. COMBINE ENVIRONMENTAL + ML RISK
# ============================================================

print("\nCombining environmental risk + ML anomaly...")

df["final_risk_score"] = (
    0.70 * df["base_risk_score"]
    + 0.30 * df["ml_anomaly_score"]
)


# ============================================================
# 11. PRIMARY DRIVER
# ============================================================

components = {
    "Water Stress": df["water_stress_score"],
    "Flood/Runoff": df["flood_risk_score"],
    "Ecosystem Pressure": df["ecosystem_risk_score"],
}

component_df = pd.DataFrame(
    components
)

df["primary_risk_driver"] = (
    component_df.idxmax(axis=1)
)


# ============================================================
# 12. RISK CATEGORIES
# ============================================================

print("Creating risk categories...")


def classify_risk(score):

    if score < 40:
        return "LOW"

    elif score < 55:
        return "MODERATE"

    elif score < 70:
        return "HIGH"

    else:
        return "CRITICAL"


df["risk_category"] = (
    df["final_risk_score"]
    .apply(classify_risk)
)


# ============================================================
# 13. LULC CONFIDENCE
# ============================================================

print("Calculating LULC confidence metadata...")


def coverage_confidence(category):

    category = str(category).upper()

    if category == "GOOD":
        return "HIGH"

    elif category == "ACCEPTABLE":
        return "MODERATE"

    elif category == "LOW":
        return "LOW"

    elif category == "INSUFFICIENT_DATA":
        return "VERY LOW"

    return "UNKNOWN"


df["lulc_confidence"] = (
    df["lulc_coverage_category"]
    .apply(coverage_confidence)
)


# ============================================================
# 14. OVERALL DATA CONFIDENCE
# ============================================================

# LULC is only ONE evidence source.
# Therefore low LULC coverage does not automatically
# reduce environmental risk.

def overall_confidence(row):

    coverage = row["lulc_coverage_pct"]

    ml_score = row["ml_anomaly_score"]

    # Strong LULC coverage
    if coverage >= 80:
        return "HIGH"

    # Moderate LULC coverage
    elif coverage >= 40:
        return "MODERATE"

    # Low LULC coverage but enough other evidence
    elif coverage >= 10:
        return "LOW"

    # Extremely limited LULC evidence
    else:
        return "VERY LOW"


df["data_confidence"] = (
    df.apply(
        overall_confidence,
        axis=1
    )
)


# ============================================================
# 15. RISK DRIVERS
# ============================================================

def get_risk_drivers(row):

    drivers = []

    if row["water_stress_score"] >= 60:
        drivers.append("Water stress")

    if row["flood_risk_score"] >= 60:
        drivers.append("Flood/runoff susceptibility")

    if row["ecosystem_risk_score"] >= 60:
        drivers.append("Ecosystem degradation")

    # Temporal signals
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

    # Remove duplicate drivers
    return "; ".join(dict.fromkeys(drivers))


df["risk_drivers"] = (
    df.apply(
        get_risk_drivers,
        axis=1
    )
)


# ============================================================
# 16. OUTPUT COLUMNS
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

    "final_risk_score",
    "risk_category",

    "primary_risk_driver",
    "risk_drivers",

    "lulc_coverage_pct",
    "lulc_coverage_category",
    "lulc_confidence",
    "data_confidence",
]


# Keep only columns that exist
OUTPUT_COLUMNS = [
    column
    for column in OUTPUT_COLUMNS
    if column in df.columns
]

result = df[OUTPUT_COLUMNS].copy()


# ============================================================
# 17. SAVE
# ============================================================

result.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# 18. REPORT
# ============================================================

print("\n" + "=" * 70)
print("RISK ENGINE V3 COMPLETE")
print("=" * 70)

print(f"Output: {OUTPUT}")

print(f"\nRows: {len(result)}")
print(f"Watersheds: {result['id'].nunique()}")


print("\nRisk categories:")

print(
    result["risk_category"]
    .value_counts()
    .sort_index()
    .to_string()
)


print("\nRisk score statistics:")

print(
    result["final_risk_score"]
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


print("\nOverall data confidence:")

print(
    result["data_confidence"]
    .value_counts()
    .to_string()
)


# ============================================================
# 19. HOLDOUT REPORT
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
        ]
    ]
    .describe()
    .round(2)
    .to_string()
)


print("\nSample:")

print(
    result.head(10).to_string(
        index=False
    )
)


print("\n✓ Model 2 V2 was NOT modified.")
print("✓ Model 2 V3 uses V6 temporal anomalies.")
print("✓ Isolation Forest trained only on 2017–2023.")
print("✓ 2024–2025 treated as holdout.")
print("✓ LULC coverage used as confidence metadata.")