import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

DEM_FILE = BASE / "data/processed/dem_features.csv"
SLOPE_FILE = BASE / "data/processed/slope_features.csv"

OUTPUT_DIR = BASE / "data/processed"
OUTPUT = OUTPUT_DIR / "terrain_features.csv"

print("Loading DEM features...")
dem = pd.read_csv(DEM_FILE)

print("Loading slope features...")
slope = pd.read_csv(SLOPE_FILE)

print(f"DEM rows: {len(dem)}")
print(f"Slope rows: {len(slope)}")

# Find the common watershed identifier
possible_ids = ["id", "ID", "MWS", "mw_id", "MW_ID"]

id_column = None

for col in possible_ids:
    if col in dem.columns and col in slope.columns:
        id_column = col
        break

if id_column is None:
    raise ValueError(
        "Could not find a common watershed ID column. "
        f"DEM columns: {list(dem.columns)}"
    )

print(f"Using watershed ID: {id_column}")

# Keep only useful columns from slope
slope_columns = [
    id_column,
    "slope_min",
    "slope_max",
    "slope_mean",
    "slope_std",
    "slope_median"
]

slope = slope[slope_columns]

# Merge
terrain = dem.merge(
    slope,
    on=id_column,
    how="inner",
    validate="one_to_one"
)

# Safety check
if len(terrain) != 66:
    raise ValueError(
        f"Expected 66 watersheds after merge, got {len(terrain)}"
    )

terrain.to_csv(OUTPUT, index=False)

print("\n================================")
print("TERRAIN MERGE COMPLETE")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(terrain)}")
print(f"Columns: {len(terrain.columns)}")

print("\nTerrain features:")
for col in terrain.columns:
    print(f"  ✓ {col}")