import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

ENV_FILE = BASE / "data/processed/monthly_environmental_features_v3.csv"
LULC_FILE = BASE / "data/raw/lulc/lulc_watershed_features.csv"
OUTPUT_FILE = BASE / "data/processed/monthly_environmental_features_v4.csv"


# ============================================================
# LOAD DATA
# ============================================================

print("Loading environmental features...")
env = pd.read_csv(ENV_FILE)

print("Loading LULC features...")
lulc = pd.read_csv(LULC_FILE)

print("Monthly observations:", len(env))
print("LULC watersheds:", len(lulc))


# ============================================================
# SELECT ONLY THE LULC FEATURES WE NEED
# ============================================================

lulc_features = lulc[
    [
        "id",
        "forest_pct",
        "agriculture_pct",
        "builtup_pct",
        "water_pct",
        "other_pct"
    ]
].copy()


# ============================================================
# CHECK FOR DUPLICATE WATERSHED IDs
# ============================================================

duplicates = lulc_features["id"].duplicated().sum()

if duplicates > 0:
    raise ValueError(
        f"Found {duplicates} duplicate watershed IDs in LULC data"
    )


# ============================================================
# CHECK MISSING VALUES
# ============================================================

print("\nLULC missing values:")

print(
    lulc_features.isna().sum()
)


# ============================================================
# MERGE
# ============================================================

print("\nMerging LULC features...")

merged = env.merge(
    lulc_features,
    on="id",
    how="left",
    validate="many_to_one"
)


# ============================================================
# VERIFY MERGE
# ============================================================

lulc_columns = [
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "other_pct"
]

print("\nMissing values after merge:")

print(
    merged[lulc_columns].isna().sum()
)


# ============================================================
# CHECK LULC PERCENTAGES
# ============================================================

print("\nLULC percentage statistics:")

print(
    merged[lulc_columns].describe().T[
        ["min", "max", "mean", "std"]
    ]
)


# ============================================================
# SAVE
# ============================================================

merged.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\n================================")
print("LULC FEATURES ADDED")
print("================================")

print("Output:", OUTPUT_FILE)
print("Rows:", len(merged))
print("Columns:", len(merged.columns))

print("\nNew LULC features:")

for col in lulc_columns:
    print("  ✓", col)