import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

INPUT = BASE / "data/processed/monthly_environmental_features_v4.csv"
OUTPUT = BASE / "data/processed/model2_features_final.csv"

print("Loading dataset...")

df = pd.read_csv(INPUT)

print("Rows:", len(df))
print("Columns:", len(df.columns))


# ============================================================
# SORT TEMPORALLY
# ============================================================

df = df.sort_values(
    ["id", "year", "month"]
).reset_index(drop=True)


# ============================================================
# NDVI IMPUTATION
# ============================================================

print("\nMissing NDVI before:", df["ndvi"].isna().sum())


# Create month identifier
df["date"] = pd.to_datetime(
    dict(
        year=df["year"],
        month=df["month"],
        day=1
    )
)


# ------------------------------------------------------------
# 1. Interpolate internal gaps within each watershed
# ------------------------------------------------------------

df["ndvi"] = (
    df.groupby("id")["ndvi"]
      .transform(
          lambda x: x.interpolate(
              method="linear",
              limit_direction="both"
          )
      )
)


print(
    "Missing NDVI after watershed interpolation:",
    df["ndvi"].isna().sum()
)


# ------------------------------------------------------------
# 2. Remaining gaps
#    Use watershed-month climatology
# ------------------------------------------------------------

if df["ndvi"].isna().any():

    watershed_month_median = (
        df.groupby(["id", "month"])["ndvi"]
          .transform("median")
    )

    df["ndvi"] = df["ndvi"].fillna(
        watershed_month_median
    )


# ------------------------------------------------------------
# 3. Final fallback: month-wide median
# ------------------------------------------------------------

if df["ndvi"].isna().any():

    month_median = (
        df.groupby("month")["ndvi"]
          .transform("median")
    )

    df["ndvi"] = df["ndvi"].fillna(
        month_median
    )


print(
    "Missing NDVI after imputation:",
    df["ndvi"].isna().sum()
)


# ============================================================
# REMOVE TEMPORARY DATE COLUMN
# ============================================================

df = df.drop(columns=["date"])


# ============================================================
# FINAL CHECK
# ============================================================

print("\n================================")
print("FINAL DATASET CHECK")
print("================================")

print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\nMissing values:")

missing = df.isna().sum()

print(
    missing[missing > 0]
    if missing.sum() > 0
    else "NONE"
)


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT,
    index=False
)

print("\n================================")
print("MODEL 2 DATASET READY")
print("================================")

print("Output:", OUTPUT)