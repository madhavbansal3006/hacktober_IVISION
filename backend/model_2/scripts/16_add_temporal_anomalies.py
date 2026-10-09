import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# MODEL 2 — TEMPORAL ANOMALY FEATURES
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = BASE_DIR / "data" / "processed" / "model2_features_v3.csv"
OUTPUT = BASE_DIR / "data" / "processed" / "model2_features_v4.csv"

print("=" * 60)
print("MODEL 2 — TEMPORAL ANOMALY ENGINE")
print("=" * 60)


# ------------------------------------------------------------
# 1. Load dataset
# ------------------------------------------------------------

print("\nLoading dataset...")

df = pd.read_csv(INPUT)

print(f"Rows: {len(df)}")
print(f"Watersheds: {df['id'].nunique()}")
print(f"Years: {df['year'].min()} - {df['year'].max()}")


# ------------------------------------------------------------
# 2. Sort chronologically
# ------------------------------------------------------------

df = df.sort_values(
    ["id", "year", "month"]
).reset_index(drop=True)


# ------------------------------------------------------------
# 3. Features for anomaly calculation
# ------------------------------------------------------------

FEATURES = [
    "rainfall_mm",
    "max_daily_rainfall_mm",
    "rainy_days",
    "ndvi",
]


# ------------------------------------------------------------
# 4. Calculate seasonal historical anomalies
# ------------------------------------------------------------

print("\nCalculating temporal anomalies...")

for feature in FEATURES:

    anomaly_name = feature.replace("_mm", "") + "_anomaly"

    print(f"  → {anomaly_name}")

    # Calculate historical mean for:
    # watershed + calendar month
    group_mean = df.groupby(
        ["id", "month"]
    )[feature].transform("mean")

    # Calculate historical standard deviation
    group_std = df.groupby(
        ["id", "month"]
    )[feature].transform("std")

    # Avoid division by zero
    group_std = group_std.replace(0, np.nan)

    # Standardized anomaly
    df[anomaly_name] = (
        (df[feature] - group_mean) / group_std
    )

    # If no historical variation exists,
    # treat anomaly as neutral.
    df[anomaly_name] = (
        df[anomaly_name]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )


# ------------------------------------------------------------
# 5. Add anomaly magnitude
# ------------------------------------------------------------

ANOMALY_COLUMNS = [
    "rainfall_anomaly",
    "max_daily_rainfall_anomaly",
    "rainy_days_anomaly",
    "ndvi_anomaly",
]

print("\nCreating anomaly magnitudes...")

for column in ANOMALY_COLUMNS:

    magnitude_name = column + "_magnitude"

    df[magnitude_name] = df[column].abs()


# ------------------------------------------------------------
# 6. Statistics
# ------------------------------------------------------------

print("\nTemporal anomaly statistics:")

print(
    df[ANOMALY_COLUMNS]
    .describe()
    .round(3)
    .to_string()
)


# ------------------------------------------------------------
# 7. Missing values
# ------------------------------------------------------------

print("\nMissing anomaly values:")

print(
    df[ANOMALY_COLUMNS]
    .isna()
    .sum()
    .to_string()
)


# ------------------------------------------------------------
# 8. Save
# ------------------------------------------------------------

df.to_csv(
    OUTPUT,
    index=False
)


print("\n" + "=" * 60)
print("TEMPORAL ANOMALY ENGINE COMPLETE")
print("=" * 60)

print(f"Output: {OUTPUT}")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nNew anomaly features:")

for column in ANOMALY_COLUMNS:
    print(f"  ✓ {column}")
    print(f"  ✓ {column}_magnitude")

print("\n✓ Original model2_features_v3.csv was NOT modified.")