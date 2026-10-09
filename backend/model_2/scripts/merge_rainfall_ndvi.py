import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

RAINFALL = BASE / "data/raw/monthly_rainfall_2015_2025.csv"
NDVI = BASE / "data/raw/monthly_ndvi_2017_2025.csv"

OUTPUT_DIR = BASE / "data/processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUTPUT_DIR / "monthly_rainfall_ndvi.csv"

print("Loading rainfall...")
rainfall = pd.read_csv(RAINFALL)

print("Loading NDVI...")
ndvi = pd.read_csv(NDVI)

print(f"Rainfall rows: {len(rainfall)}")
print(f"NDVI rows: {len(ndvi)}")

# Rename NDVI value
ndvi = ndvi.rename(columns={
    "mean": "ndvi"
})

# Columns needed from rainfall
rainfall = rainfall[
    [
        "id",
        "MWS",
        "year",
        "month",
        "rainfall_mm",
        "max_daily_rainfall_mm",
        "rainy_days"
    ]
]

# Columns needed from NDVI
ndvi = ndvi[
    [
        "id",
        "year",
        "month",
        "ndvi"
    ]
]

# Merge using watershed + time
merged = rainfall.merge(
    ndvi,
    on=["id", "year", "month"],
    how="inner",
    validate="one_to_one"
)

print("\n================================")
print("RAINFALL + NDVI MERGE")
print("================================")

print(f"Rows after merge: {len(merged)}")
print(f"Columns: {len(merged.columns)}")

# Check missing values
print("\nMissing values:")
print(merged.isna().sum())

# Check unique watersheds
print(f"\nUnique watersheds: {merged['id'].nunique()}")

# Save
merged.to_csv(OUTPUT, index=False)

print(f"\nSaved to:")
print(OUTPUT)