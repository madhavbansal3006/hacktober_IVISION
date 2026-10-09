import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# MODEL 2 — LEAKAGE-SAFE TEMPORAL ANOMALIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = BASE_DIR / "data" / "processed" / "model2_features_v3.csv"
OUTPUT = BASE_DIR / "data" / "processed" / "model2_features_v5.csv"

TRAIN_END_YEAR = 2023
HOLDOUT_START_YEAR = 2024

FEATURES = [
    "rainfall_mm",
    "max_daily_rainfall_mm",
    "rainy_days",
    "ndvi",
]

ANOMALY_COLUMNS = [
    "rainfall_anomaly",
    "max_daily_rainfall_anomaly",
    "rainy_days_anomaly",
    "ndvi_anomaly",
]


print("=" * 65)
print("MODEL 2 — LEAKAGE-SAFE TEMPORAL ANOMALIES")
print("=" * 65)


# ------------------------------------------------------------
# 1. Load dataset
# ------------------------------------------------------------

print("\nLoading dataset...")

df = pd.read_csv(INPUT)

df = df.sort_values(
    ["id", "year", "month"]
).reset_index(drop=True)

print(f"Rows: {len(df)}")
print(f"Watersheds: {df['id'].nunique()}")
print(f"Years: {df['year'].min()} - {df['year'].max()}")


# ------------------------------------------------------------
# 2. Create train / holdout masks
# ------------------------------------------------------------

train_mask = df["year"] <= TRAIN_END_YEAR
holdout_mask = df["year"] >= HOLDOUT_START_YEAR

print("\nTemporal split:")
print(
    f"Training period: {df.loc[train_mask, 'year'].min()}"
    f"–{TRAIN_END_YEAR}"
)

print(
    f"Holdout period: {HOLDOUT_START_YEAR}"
    f"–{df.loc[holdout_mask, 'year'].max()}"
)

print(
    f"Training observations: {train_mask.sum()}"
)

print(
    f"Holdout observations: {holdout_mask.sum()}"
)


# ------------------------------------------------------------
# 3. Initialize anomaly columns
# ------------------------------------------------------------

for feature in FEATURES:

    anomaly_name = feature.replace("_mm", "") + "_anomaly"

    df[anomaly_name] = np.nan


# ------------------------------------------------------------
# 4. TRAINING PERIOD
# ------------------------------------------------------------

print("\nCalculating training-period anomalies...")

train_df = df.loc[train_mask].copy()

for feature in FEATURES:

    anomaly_name = feature.replace("_mm", "") + "_anomaly"

    # Historical baseline for each:
    # watershed + calendar month
    means = (
        train_df
        .groupby(["id", "month"])[feature]
        .mean()
    )

    stds = (
        train_df
        .groupby(["id", "month"])[feature]
        .std()
    )

    # Map baseline back to training rows
    keys = pd.MultiIndex.from_frame(
        train_df[["id", "month"]]
    )

    mean_values = means.reindex(keys).to_numpy()
    std_values = stds.reindex(keys).to_numpy()

    values = train_df[feature].to_numpy()

    std_values = np.where(
        (np.isnan(std_values)) | (std_values == 0),
        np.nan,
        std_values
    )

    anomalies = (
        (values - mean_values) / std_values
    )

    anomalies = np.nan_to_num(
        anomalies,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    df.loc[train_df.index, anomaly_name] = anomalies


# ------------------------------------------------------------
# 5. HOLDOUT PERIOD
# ------------------------------------------------------------

print("\nCalculating holdout anomalies...")
print("Using ONLY 2017–2023 baselines.")


holdout_df = df.loc[holdout_mask].copy()

for feature in FEATURES:

    anomaly_name = feature.replace("_mm", "") + "_anomaly"

    # IMPORTANT:
    # Baseline is calculated ONLY from training data.
    means = (
        train_df
        .groupby(["id", "month"])[feature]
        .mean()
    )

    stds = (
        train_df
        .groupby(["id", "month"])[feature]
        .std()
    )

    keys = pd.MultiIndex.from_frame(
        holdout_df[["id", "month"]]
    )

    mean_values = means.reindex(keys).to_numpy()
    std_values = stds.reindex(keys).to_numpy()

    values = holdout_df[feature].to_numpy()

    std_values = np.where(
        (np.isnan(std_values)) | (std_values == 0),
        np.nan,
        std_values
    )

    anomalies = (
        (values - mean_values) / std_values
    )

    anomalies = np.nan_to_num(
        anomalies,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    df.loc[holdout_df.index, anomaly_name] = anomalies


# ------------------------------------------------------------
# 6. Create anomaly magnitudes
# ------------------------------------------------------------

print("\nCreating anomaly magnitudes...")

for column in ANOMALY_COLUMNS:

    magnitude_name = column + "_magnitude"

    df[magnitude_name] = df[column].abs()


# ------------------------------------------------------------
# 7. Validate leakage-safe features
# ------------------------------------------------------------

print("\n" + "=" * 65)
print("TEMPORAL ANOMALY VALIDATION")
print("=" * 65)

print("\nTraining anomaly statistics:")

print(
    df.loc[train_mask, ANOMALY_COLUMNS]
    .describe()
    .round(3)
    .to_string()
)

print("\nHoldout anomaly statistics:")

print(
    df.loc[holdout_mask, ANOMALY_COLUMNS]
    .describe()
    .round(3)
    .to_string()
)


# ------------------------------------------------------------
# 8. Missing values
# ------------------------------------------------------------

print("\nMissing anomaly values:")

print(
    df[ANOMALY_COLUMNS]
    .isna()
    .sum()
    .to_string()
)


# ------------------------------------------------------------
# 9. Save
# ------------------------------------------------------------

df.to_csv(
    OUTPUT,
    index=False
)


print("\n" + "=" * 65)
print("LEAKAGE-SAFE TEMPORAL ANOMALY ENGINE COMPLETE")
print("=" * 65)

print(f"Output: {OUTPUT}")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nNew features:")

for column in ANOMALY_COLUMNS:
    print(f"  ✓ {column}")
    print(f"  ✓ {column}_magnitude")

print("\n✓ 2024–2025 did NOT influence its anomaly baseline.")
print("✓ Original model2_features_v3.csv was NOT modified.")
