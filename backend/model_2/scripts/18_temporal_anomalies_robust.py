import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# MODEL 2 — ROBUST WALK-FORWARD TEMPORAL ANOMALIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = BASE_DIR / "data" / "processed" / "model2_features_v3.csv"
OUTPUT = BASE_DIR / "data" / "processed" / "model2_features_v6.csv"

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
print("MODEL 2 — ROBUST WALK-FORWARD TEMPORAL ANOMALIES")
print("=" * 65)


# ------------------------------------------------------------
# 1. Load
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
# 2. Initialize anomaly columns
# ------------------------------------------------------------

for feature in FEATURES:
    anomaly_name = feature.replace("_mm", "") + "_anomaly"
    df[anomaly_name] = 0.0


# ------------------------------------------------------------
# 3. Robust anomaly function
# ------------------------------------------------------------

def robust_anomaly(current, history):
    """
    Robust standardized anomaly.

    Uses median + MAD rather than mean + standard deviation.

    MAD = median absolute deviation.

    A minimum scale prevents extremely small historical
    variability from creating unrealistic anomaly values.
    """

    history = pd.to_numeric(
        history,
        errors="coerce"
    ).dropna()

    current = pd.to_numeric(
        pd.Series([current]),
        errors="coerce"
    ).iloc[0]

    if pd.isna(current) or len(history) < 2:
        return 0.0

    median = history.median()

    mad = np.median(
        np.abs(history - median)
    )

    # Convert MAD to approximately standard-deviation scale.
    robust_std = 1.4826 * mad

    # Fallback to standard deviation when MAD is zero.
    if robust_std <= 0 or np.isnan(robust_std):
        robust_std = history.std()

    if robust_std <= 0 or np.isnan(robust_std):
        return 0.0

    # Prevent tiny historical variation from exploding.
    # Use a data-driven floor based on the historical
    # magnitude of the variable.
    scale_floor = max(
        history.median() * 0.05,
        0.1
    )

    robust_std = max(
        robust_std,
        scale_floor
    )

    anomaly = (
        current - median
    ) / robust_std

    # Safety bound for ML stability.
    anomaly = np.clip(
        anomaly,
        -6.0,
        6.0
    )

    return float(anomaly)


# ------------------------------------------------------------
# 4. Walk-forward calculation
# ------------------------------------------------------------

print("\nCalculating walk-forward anomalies...")
print("Each observation uses only earlier data.")


for feature in FEATURES:

    anomaly_name = feature.replace("_mm", "") + "_anomaly"

    print(f"  → {anomaly_name}")

    results = np.zeros(len(df))

    # Process each watershed independently
    for watershed_id, indices in df.groupby("id").groups.items():

        indices = list(indices)

        for position, idx in enumerate(indices):

            current_year = df.loc[idx, "year"]
            current_month = df.loc[idx, "month"]

            # ------------------------------------------------
            # Training period
            # ------------------------------------------------

            if current_year <= TRAIN_END_YEAR:

                # Only observations strictly BEFORE current row
                previous_indices = indices[:position]

                history_indices = [
                    i for i in previous_indices
                    if df.loc[i, "month"] == current_month
                ]

            # ------------------------------------------------
            # Holdout period
            # ------------------------------------------------

            else:

                # Holdout NEVER contributes to baseline.
                history_indices = [
                    i for i in indices
                    if (
                        df.loc[i, "year"] <= TRAIN_END_YEAR
                        and df.loc[i, "month"] == current_month
                    )
                ]

            history = df.loc[
                history_indices,
                feature
            ]

            current_value = df.loc[
                idx,
                feature
            ]

            results[idx] = robust_anomaly(
                current_value,
                history
            )

    df[anomaly_name] = results


# ------------------------------------------------------------
# 5. Add anomaly magnitudes
# ------------------------------------------------------------

print("\nCreating anomaly magnitudes...")

for column in ANOMALY_COLUMNS:

    df[column + "_magnitude"] = (
        df[column].abs()
    )


# ------------------------------------------------------------
# 6. Training / holdout masks
# ------------------------------------------------------------

train_mask = (
    df["year"] <= TRAIN_END_YEAR
)

holdout_mask = (
    df["year"] >= HOLDOUT_START_YEAR
)


# ------------------------------------------------------------
# 7. Statistics
# ------------------------------------------------------------

print("\n" + "=" * 65)
print("ROBUST ANOMALY VALIDATION")
print("=" * 65)

print("\nTraining anomaly statistics:")

print(
    df.loc[
        train_mask,
        ANOMALY_COLUMNS
    ]
    .describe()
    .round(3)
    .to_string()
)


print("\nHoldout anomaly statistics:")

print(
    df.loc[
        holdout_mask,
        ANOMALY_COLUMNS
    ]
    .describe()
    .round(3)
    .to_string()
)


# ------------------------------------------------------------
# 8. Check extreme values
# ------------------------------------------------------------

print("\nMaximum absolute anomaly:")

for column in ANOMALY_COLUMNS:

    maximum = df[column].abs().max()

    print(
        f"  {column}: {maximum:.3f}"
    )


# ------------------------------------------------------------
# 9. Missing values
# ------------------------------------------------------------

print("\nMissing anomaly values:")

print(
    df[ANOMALY_COLUMNS]
    .isna()
    .sum()
    .to_string()
)


# ------------------------------------------------------------
# 10. Save
# ------------------------------------------------------------

df.to_csv(
    OUTPUT,
    index=False
)


print("\n" + "=" * 65)
print("ROBUST TEMPORAL ANOMALY ENGINE COMPLETE")
print("=" * 65)

print(f"Output: {OUTPUT}")
print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nNew features:")

for column in ANOMALY_COLUMNS:
    print(f"  ✓ {column}")
    print(f"  ✓ {column}_magnitude")

print("\n✓ Walk-forward baseline used.")
print("✓ 2024–2025 excluded from training baselines.")
print("✓ Extreme anomalies capped at ±6.")
print("✓ Original model2_features_v3.csv was NOT modified.")