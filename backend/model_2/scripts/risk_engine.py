import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

BASE = Path(__file__).resolve().parents[1]

INPUT = BASE / "data/processed/model2_features_final.csv"
OUTPUT = BASE / "data/processed/risk_assessment.csv"

print("Loading Model 2 dataset...")
df = pd.read_csv(INPUT)

print("Rows:", len(df))
print("Watersheds:", df["id"].nunique())


# ============================================================
# HELPER: PERCENTILE NORMALIZATION
# ============================================================

def percentile_score(series, higher_is_worse=True):
    """
    Convert a variable into a 0-100 relative risk score.

    Higher percentile = higher risk when higher_is_worse=True.
    """

    rank = series.rank(
        method="average",
        pct=True
    ) * 100

    if higher_is_worse:
        return rank

    return 100 - rank


# ============================================================
# 1. WATER STRESS
# ============================================================

print("\nCalculating water-stress risk...")

# Less rainfall → greater stress
rainfall_risk = percentile_score(
    df["rainfall_mm"],
    higher_is_worse=False
)

# Fewer rainy days → greater stress
rainy_days_risk = percentile_score(
    df["rainy_days"],
    higher_is_worse=False
)

# Lower vegetation health → greater stress
ndvi_risk = percentile_score(
    df["ndvi"],
    higher_is_worse=False
)

# Lower water availability represented by surface-water coverage
water_risk = percentile_score(
    df["water_pct"],
    higher_is_worse=False
)

water_stress = (
    0.35 * rainfall_risk
    + 0.25 * rainy_days_risk
    + 0.25 * ndvi_risk
    + 0.15 * water_risk
)


# ============================================================
# 2. FLOOD / RUNOFF SUSCEPTIBILITY
# ============================================================

print("Calculating flood/runoff risk...")

# Extreme rainfall
rainfall_intensity_risk = percentile_score(
    df["max_daily_rainfall_mm"],
    higher_is_worse=True
)

# Steeper terrain
slope_risk = percentile_score(
    df["slope_mean"],
    higher_is_worse=True
)

# Higher drainage density
drainage_risk = percentile_score(
    df["drainage_density"],
    higher_is_worse=True
)

# More built-up area → more impervious surface
builtup_risk = percentile_score(
    df["builtup_pct"],
    higher_is_worse=True
)

# Higher clay content → relatively lower infiltration
clay_risk = percentile_score(
    df["clay_mean"],
    higher_is_worse=True
)

flood_risk = (
    0.35 * rainfall_intensity_risk
    + 0.25 * slope_risk
    + 0.20 * drainage_risk
    + 0.10 * builtup_risk
    + 0.10 * clay_risk
)


# ============================================================
# 3. ECOSYSTEM / WATERSHED DEGRADATION
# ============================================================

print("Calculating ecosystem pressure...")

# Less forest → greater degradation
forest_risk = percentile_score(
    df["forest_pct"],
    higher_is_worse=False
)

# More agriculture → greater land-use pressure
agriculture_risk = percentile_score(
    df["agriculture_pct"],
    higher_is_worse=True
)

# More built-up → greater pressure
builtup_degradation = percentile_score(
    df["builtup_pct"],
    higher_is_worse=True
)

# Lower NDVI → greater degradation
vegetation_risk = percentile_score(
    df["ndvi"],
    higher_is_worse=False
)

# Lower SOC → greater soil degradation
soc_risk = percentile_score(
    df["soc_mean"],
    higher_is_worse=False
)

ecosystem_risk = (
    0.30 * forest_risk
    + 0.25 * agriculture_risk
    + 0.15 * builtup_degradation
    + 0.20 * vegetation_risk
    + 0.10 * soc_risk
)


# ============================================================
# 4. COMBINED EXPLAINABLE RISK
# ============================================================

print("Calculating overall risk...")

overall_risk = (
    0.35 * water_stress
    + 0.35 * flood_risk
    + 0.30 * ecosystem_risk
)

df["water_stress_score"] = water_stress
df["flood_risk_score"] = flood_risk
df["ecosystem_risk_score"] = ecosystem_risk
df["base_risk_score"] = overall_risk


# ============================================================
# 5. ISOLATION FOREST — ML ANOMALY DETECTION
# ============================================================

print("\nTraining Isolation Forest...")

ml_features = [
    "rainfall_mm",
    "max_daily_rainfall_mm",
    "rainy_days",
    "ndvi",
    "slope_mean",
    "drainage_density",
    "clay_mean",
    "sand_mean",
    "silt_mean",
    "soc_mean",
    "stream_length_km",
    "max_river_order",
    "mean_river_order",
    "lake_count",
    "lake_area_km2",
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "other_pct",
]


X = df[ml_features].copy()


# Normalize features
scaler = MinMaxScaler()

X_scaled = scaler.fit_transform(X)


# Train anomaly detector
isolation_forest = IsolationForest(
    n_estimators=300,
    contamination=0.05,
    random_state=42,
    n_jobs=-1
)

isolation_forest.fit(X_scaled)


# Raw anomaly score
raw_anomaly = -isolation_forest.score_samples(
    X_scaled
)


# Convert to 0-100
anomaly_score = (
    pd.Series(raw_anomaly)
    .rank(pct=True)
    * 100
)

df["ml_anomaly_score"] = anomaly_score


# ============================================================
# 6. FINAL RISK SCORE
# ============================================================

# ML contributes 20%.
# Explainable environmental risk contributes 80%.

df["final_risk_score"] = (
    0.80 * df["base_risk_score"]
    + 0.20 * df["ml_anomaly_score"]
)


# Keep inside 0-100
df["final_risk_score"] = (
    df["final_risk_score"]
    .clip(0, 100)
)


# ============================================================
# 7. RISK CATEGORY
# ============================================================

def risk_category(score):

    if score < 33:
        return "LOW"

    elif score < 66:
        return "MODERATE"

    else:
        return "HIGH"


df["risk_category"] = (
    df["final_risk_score"]
    .apply(risk_category)
)


# ============================================================
# 8. PRIMARY DRIVER
# ============================================================

risk_components = {
    "Water Stress": df["water_stress_score"],
    "Flood/Runoff": df["flood_risk_score"],
    "Ecosystem Pressure": df["ecosystem_risk_score"],
}

risk_component_df = pd.DataFrame(risk_components)

df["primary_risk_driver"] = (
    risk_component_df.idxmax(axis=1)
)


# ============================================================
# 9. SAVE
# ============================================================

df.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# REPORT
# ============================================================

print("\n================================")
print("RISK ENGINE COMPLETE")
print("================================")

print("Output:", OUTPUT)

print("\nRisk categories:")

print(
    df["risk_category"]
    .value_counts()
)

print("\nRisk score statistics:")

print(
    df[
        [
            "water_stress_score",
            "flood_risk_score",
            "ecosystem_risk_score",
            "ml_anomaly_score",
            "final_risk_score",
        ]
    ]
    .describe()
    .T[
        ["min", "max", "mean", "std"]
    ]
)

print("\nPrimary drivers:")

print(
    df["primary_risk_driver"]
    .value_counts()
)

print("\nSample:")

print(
    df[
        [
            "id",
            "year",
            "month",
            "water_stress_score",
            "flood_risk_score",
            "ecosystem_risk_score",
            "ml_anomaly_score",
            "final_risk_score",
            "risk_category",
            "primary_risk_driver",
        ]
    ]
    .head(10)
    .to_string(index=False)
)