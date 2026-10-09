import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

BASE = Path(__file__).resolve().parents[1]

INPUT = BASE / "data/processed/model2_features_final.csv"
OUTPUT = BASE / "data/processed/risk_assessment_v2.csv"

print("================================")
print("MODEL 2 RISK ENGINE V2")
print("================================")

df = pd.read_csv(INPUT)

print("\nRows:", len(df))
print("Watersheds:", df["id"].nunique())
print("Years:", df["year"].min(), "-", df["year"].max())


# ============================================================
# PERCENTILE RISK TRANSFORMATION
# ============================================================

def percentile_score(series, higher_is_worse=True):

    score = series.rank(
        method="average",
        pct=True
    ) * 100

    if higher_is_worse:
        return score

    return 100 - score


# ============================================================
# 1. WATER STRESS
# ============================================================

print("\nCalculating water-stress risk...")

rainfall_risk = percentile_score(
    df["rainfall_mm"],
    higher_is_worse=False
)

rainy_days_risk = percentile_score(
    df["rainy_days"],
    higher_is_worse=False
)

ndvi_risk = percentile_score(
    df["ndvi"],
    higher_is_worse=False
)

water_coverage_risk = percentile_score(
    df["water_pct"],
    higher_is_worse=False
)

df["water_stress_score"] = (
    0.35 * rainfall_risk
    + 0.25 * rainy_days_risk
    + 0.25 * ndvi_risk
    + 0.15 * water_coverage_risk
)


# ============================================================
# 2. FLOOD / RUNOFF
# ============================================================

print("Calculating flood/runoff risk...")

rainfall_intensity_risk = percentile_score(
    df["max_daily_rainfall_mm"],
    higher_is_worse=True
)

slope_risk = percentile_score(
    df["slope_mean"],
    higher_is_worse=True
)

drainage_risk = percentile_score(
    df["drainage_density"],
    higher_is_worse=True
)

builtup_runoff_risk = percentile_score(
    df["builtup_pct"],
    higher_is_worse=True
)

clay_risk = percentile_score(
    df["clay_mean"],
    higher_is_worse=True
)

df["flood_risk_score"] = (
    0.35 * rainfall_intensity_risk
    + 0.25 * slope_risk
    + 0.20 * drainage_risk
    + 0.10 * builtup_runoff_risk
    + 0.10 * clay_risk
)


# ============================================================
# 3. ECOSYSTEM PRESSURE
# ============================================================

print("Calculating ecosystem pressure...")

forest_risk = percentile_score(
    df["forest_pct"],
    higher_is_worse=False
)

agriculture_risk = percentile_score(
    df["agriculture_pct"],
    higher_is_worse=True
)

builtup_ecosystem_risk = percentile_score(
    df["builtup_pct"],
    higher_is_worse=True
)

vegetation_risk = percentile_score(
    df["ndvi"],
    higher_is_worse=False
)

soc_risk = percentile_score(
    df["soc_mean"],
    higher_is_worse=False
)

df["ecosystem_risk_score"] = (
    0.30 * forest_risk
    + 0.25 * agriculture_risk
    + 0.15 * builtup_ecosystem_risk
    + 0.20 * vegetation_risk
    + 0.10 * soc_risk
)


# ============================================================
# 4. EXPLAINABLE BASE RISK
# ============================================================

print("Calculating base risk...")

df["base_risk_score"] = (
    0.35 * df["water_stress_score"]
    + 0.35 * df["flood_risk_score"]
    + 0.30 * df["ecosystem_risk_score"]
)


# ============================================================
# 5. ISOLATION FOREST
# ============================================================

print("\nPreparing ML anomaly detector...")

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


# ============================================================
# TEMPORAL SPLIT
# ============================================================

train_mask = df["year"] <= 2023
test_mask = df["year"] >= 2024

train_df = df.loc[train_mask].copy()
test_df = df.loc[test_mask].copy()

print("\nTemporal split:")
print("Training period: 2017–2023")
print("Training observations:", len(train_df))
print("Holdout period: 2024–2025")
print("Holdout observations:", len(test_df))


# ============================================================
# SCALE USING TRAINING DATA ONLY
# ============================================================

scaler = MinMaxScaler()

X_train = scaler.fit_transform(
    train_df[ml_features]
)

X_all = scaler.transform(
    df[ml_features]
)


# ============================================================
# TRAIN ISOLATION FOREST
# ============================================================

print("\nTraining Isolation Forest...")

isolation_forest = IsolationForest(
    n_estimators=300,
    contamination=0.05,
    random_state=42,
    n_jobs=-1
)

isolation_forest.fit(X_train)


# ============================================================
# ANOMALY SCORES
# ============================================================

raw_anomaly = -isolation_forest.score_samples(
    X_all
)

df["raw_ml_anomaly"] = raw_anomaly


# Convert anomaly signal to 0–100 relative score
#
# IMPORTANT:
# Scaling is based on the complete set only for presentation.
# The model itself was trained exclusively on 2017–2023.

df["ml_anomaly_score"] = (
    pd.Series(raw_anomaly, index=df.index)
    .rank(pct=True)
    * 100
)


# ============================================================
# 6. HYBRID RISK SCORE
# ============================================================

print("Combining environmental risk + ML anomaly...")

df["final_risk_score"] = (
    0.80 * df["base_risk_score"]
    + 0.20 * df["ml_anomaly_score"]
)

df["final_risk_score"] = (
    df["final_risk_score"]
    .clip(0, 100)
)


# ============================================================
# 7. EMPIRICAL RISK CATEGORIES
# ============================================================

print("Creating empirical risk categories...")

q40 = df["final_risk_score"].quantile(0.40)
q70 = df["final_risk_score"].quantile(0.70)
q90 = df["final_risk_score"].quantile(0.90)

print("\nRisk thresholds:")
print(f"LOW:       < {q40:.2f}")
print(f"MODERATE:  {q40:.2f} – {q70:.2f}")
print(f"HIGH:      {q70:.2f} – {q90:.2f}")
print(f"CRITICAL:  >= {q90:.2f}")


def classify_risk(score):

    if score < q40:
        return "LOW"

    elif score < q70:
        return "MODERATE"

    elif score < q90:
        return "HIGH"

    else:
        return "CRITICAL"


df["risk_category"] = (
    df["final_risk_score"]
    .apply(classify_risk)
)


# ============================================================
# 8. PRIMARY DRIVER
# ============================================================

component_scores = pd.DataFrame({
    "Water Stress": df["water_stress_score"],
    "Flood/Runoff": df["flood_risk_score"],
    "Ecosystem Pressure": df["ecosystem_risk_score"],
})

df["primary_risk_driver"] = (
    component_scores.idxmax(axis=1)
)


# ============================================================
# 9. TEMPORAL ML SUMMARY
# ============================================================

print("\n================================")
print("TEMPORAL ML RESULTS")
print("================================")

print("\nTraining anomaly statistics:")
print(
    df.loc[train_mask, "ml_anomaly_score"]
    .describe()[["min", "mean", "50%", "max"]]
    .round(2)
)

print("\nHoldout anomaly statistics:")
print(
    df.loc[test_mask, "ml_anomaly_score"]
    .describe()[["min", "mean", "50%", "max"]]
    .round(2)
)


# ============================================================
# 10. SAVE
# ============================================================

df.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# FINAL REPORT
# ============================================================

print("\n================================")
print("RISK ENGINE V2 COMPLETE")
print("================================")

print("Output:", OUTPUT)

print("\nRisk categories:")
print(
    df["risk_category"]
    .value_counts()
    .sort_index()
)

print("\nFinal risk statistics:")
print(
    df["final_risk_score"]
    .describe()
    .round(2)
)

print("\nPrimary drivers:")
print(
    df["primary_risk_driver"]
    .value_counts()
)

print("\n================================")
print("HOLDOUT PERIOD: 2024–2025")
print("================================")

holdout = df[test_mask]

print(
    holdout[
        [
            "final_risk_score",
            "ml_anomaly_score",
            "risk_category"
        ]
    ]
    .describe()
    .round(2)
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