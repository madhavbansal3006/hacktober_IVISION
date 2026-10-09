import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

MONTHLY = BASE / "data/processed/monthly_rainfall_ndvi.csv"
TERRAIN = BASE / "data/processed/terrain_features.csv"

OUTPUT = BASE / "data/processed/monthly_environmental_features.csv"

print("Loading monthly rainfall + NDVI...")
monthly = pd.read_csv(MONTHLY)

print("Loading terrain features...")
terrain = pd.read_csv(TERRAIN)

print(f"Monthly observations: {len(monthly)}")
print(f"Terrain watersheds: {len(terrain)}")

# Keep only the terrain features we actually need
terrain = terrain[
    [
        "id",
        "elevation_min",
        "elevation_max",
        "elevation_mean",
        "elevation_std",
        "elevation_median",
        "elevation_range",
        "slope_min",
        "slope_max",
        "slope_mean",
        "slope_std",
        "slope_median"
    ]
]

# Check that each watershed occurs only once in terrain data
if terrain["id"].duplicated().any():
    raise ValueError("Duplicate watershed IDs found in terrain data.")

# Merge static terrain features onto every monthly observation
merged = monthly.merge(
    terrain,
    on="id",
    how="left",
    validate="many_to_one"
)

# Safety checks
if len(merged) != len(monthly):
    raise ValueError(
        f"Row count changed! Before: {len(monthly)}, "
        f"After: {len(merged)}"
    )

# Check missing terrain values
terrain_columns = [
    "elevation_mean",
    "slope_mean",
    "elevation_range"
]

print("\nMissing terrain values:")
print(merged[terrain_columns].isna().sum())

# Save
merged.to_csv(OUTPUT, index=False)

print("\n================================")
print("TERRAIN FEATURES ADDED")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(merged)}")
print(f"Columns: {len(merged.columns)}")