# ============================================================
# MODEL 2 — LIVE IoT ML MODEL EXPORTER
# ============================================================
#
# This script recreates the exact Isolation Forest ML pipeline
# used in Risk Engine V4 and saves it for live inference.
#
# IMPORTANT:
# - Risk Engine V4 is NOT modified.
# - The same ML feature configuration is preserved.
# - The trained model will later be loaded by the IoT Risk Engine.
#
# ============================================================

import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


print("=" * 70)
print("MODEL 2 — LIVE IoT ML MODEL TRAINING & EXPORT")
print("=" * 70)


# ============================================================
# 1. PATH CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DATA_PATH = os.path.join(
    BASE_DIR,
    "Data",
    "processed",
    "model2_features_v6.csv"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


# ============================================================
# 2. LOAD DATA
# ============================================================

print("\nLoading Model 2 feature dataset...")

df = pd.read_csv(DATA_PATH)

print(f"Records loaded: {len(df)}")
print(f"Columns loaded: {len(df.columns)}")


# ============================================================
# 3. RECREATE V4 TRAIN / HOLDOUT SPLIT
# ============================================================

# Risk Engine V4 used historical data for training
# and kept recent data separate for validation.

train_mask = df["year"] <= 2023
holdout_mask = df["year"] >= 2024

print("\nDataset split:")

print(
    f"Training records: "
    f"{train_mask.sum()}"
)

print(
    f"Holdout records: "
    f"{holdout_mask.sum()}"
)


# ============================================================
# 4. EXACT V4 ML FEATURES
# ============================================================

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

print(
    f"\nML features: "
    f"{len(ML_FEATURES)}"
)


# ============================================================
# 5. PREPARE FEATURES
# ============================================================

print("\nPreparing ML features...")

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


# Training-only median imputation
train_medians = X.loc[
    train_mask
].median()


X = X.fillna(
    train_medians
)

X = X.fillna(
    0
)


# ============================================================
# 6. SCALE FEATURES
# ============================================================

print("Scaling features...")

scaler = StandardScaler()

X_train = scaler.fit_transform(
    X.loc[train_mask]
)


# ============================================================
# 7. TRAIN ISOLATION FOREST
# ============================================================

print("Training Isolation Forest...")

iso_forest = IsolationForest(

    n_estimators=300,
    contamination="auto",
    random_state=42,
    n_jobs=-1

)

iso_forest.fit(
    X_train
)


# ============================================================
# 8. CALCULATE V4 NORMALIZATION PARAMETERS
# ============================================================

print(
    "Calculating ML anomaly normalization parameters..."
)


train_raw = -iso_forest.decision_function(
    X_train
)


train_median = np.median(
    train_raw
)


train_mad = np.median(

    np.abs(
        train_raw -
        train_median
    )

)


if train_mad <= 0:

    train_mad = np.std(
        train_raw
    )


if train_mad <= 0:

    train_mad = 1.0


print(
    f"Training anomaly median: "
    f"{train_median:.6f}"
)

print(
    f"Training anomaly MAD: "
    f"{train_mad:.6f}"
)


# ============================================================
# 9. PACKAGE EVERYTHING REQUIRED FOR LIVE INFERENCE
# ============================================================

print(
    "\nPackaging live ML inference model..."
)


ml_package = {

    # Actual trained ML model
    "model": iso_forest,

    # Feature scaler
    "scaler": scaler,

    # Required feature order
    "feature_names": ML_FEATURES,

    # Missing-value handling
    "train_medians": train_medians,

    # ML score normalization parameters
    "train_median": train_median,
    "train_mad": train_mad,

    # Model metadata
    "model_type": "IsolationForest",
    "n_estimators": 300,
    "random_state": 42

}


# ============================================================
# 10. SAVE MODEL
# ============================================================

MODEL_PATH = os.path.join(

    MODEL_DIR,

    "model2_live_iot_isolation_forest.joblib"

)


joblib.dump(

    ml_package,

    MODEL_PATH

)


print("\n" + "=" * 70)

print(
    "LIVE IoT ML MODEL EXPORTED SUCCESSFULLY"
)

print("=" * 70)


print(
    f"\nModel saved to:\n"
    f"{MODEL_PATH}"
)


print(
    "\nThe package contains:"
)

print("✓ Trained Isolation Forest")
print("✓ StandardScaler")
print("✓ Training medians")
print("✓ Feature configuration")
print("✓ ML normalization parameters")


print("\n" + "=" * 70)
print("TRAINING COMPLETE")
print("=" * 70)