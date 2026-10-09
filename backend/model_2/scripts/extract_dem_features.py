import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
import numpy as np
from pathlib import Path

# -----------------------------
# Paths
# -----------------------------
BASE = Path(__file__).resolve().parents[1]

WATERSHEDS = BASE / "data/raw/shiggaon_micro_watersheds_deliverables/shiggaon_micro_watersheds.gpkg"

DEM = BASE / "data/raw/Shiggaon_Taluk_DEM_GLO30/Shiggaon_Taluk_DEM_GLO30.tif"

OUTPUT_DIR = BASE / "data/processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUTPUT_DIR / "dem_features.csv"

# -----------------------------
# Load micro-watersheds
# -----------------------------
print("Loading micro-watersheds...")

gdf = gpd.read_file(WATERSHEDS)

print(f"Micro-watersheds found: {len(gdf)}")
print(f"Watershed CRS: {gdf.crs}")

# -----------------------------
# Load DEM
# -----------------------------
print("\nLoading DEM...")

with rasterio.open(DEM) as src:
    dem_crs = src.crs
    dem_data = src.read(1)
    dem_transform = src.transform
    nodata = src.nodata

print(f"DEM CRS: {dem_crs}")
print(f"DEM resolution: {src.res}")

# -----------------------------
# Reproject watersheds
# -----------------------------
gdf = gdf.to_crs(dem_crs)

# -----------------------------
# Calculate DEM statistics
# -----------------------------
print("\nCalculating elevation statistics...")

stats = zonal_stats(
    gdf,
    dem_data,
    affine=dem_transform,
    nodata=nodata,
    stats=[
        "min",
        "max",
        "mean",
        "median",
        "std"
    ]
)

stats_df = gpd.pd.DataFrame(stats)

# -----------------------------
# Add statistics
# -----------------------------
for column in stats_df.columns:
    gdf[f"elevation_{column}"] = stats_df[column].values

gdf["elevation_range"] = (
    gdf["elevation_max"] -
    gdf["elevation_min"]
)

# -----------------------------
# Keep attributes only
# -----------------------------
result = gdf.drop(columns="geometry")

# -----------------------------
# Save
# -----------------------------
result.to_csv(OUTPUT, index=False)

print("\n================================")
print("DEM PROCESSING COMPLETE")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(result)}")
print("\nColumns created:")

for column in result.columns:
    if "elevation" in column:
        print(f"  ✓ {column}")
