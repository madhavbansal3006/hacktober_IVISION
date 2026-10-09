import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterstats import zonal_stats
import numpy as np
from pathlib import Path

# -----------------------------
# Paths
# -----------------------------
BASE = Path(__file__).resolve().parents[1]

WATERSHEDS = (
    BASE
    / "data/raw/shiggaon_micro_watersheds_deliverables/"
    / "shiggaon_micro_watersheds.gpkg"
)

DEM = (
    BASE
    / "data/raw/Shiggaon_Taluk_DEM_GLO30/"
    / "Shiggaon_Taluk_DEM_GLO30.tif"
)

OUTPUT_DIR = BASE / "data/processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT = OUTPUT_DIR / "slope_features.csv"

# -----------------------------
# Load watersheds
# -----------------------------
print("Loading micro-watersheds...")

gdf = gpd.read_file(WATERSHEDS)

print(f"Micro-watersheds found: {len(gdf)}")
print(f"Original CRS: {gdf.crs}")

# -----------------------------
# Open DEM
# -----------------------------
print("\nLoading DEM...")

with rasterio.open(DEM) as src:

    dem = src.read(1)
    src_crs = src.crs
    src_transform = src.transform
    src_width = src.width
    src_height = src.height
    src_bounds = src.bounds
    nodata = src.nodata

print(f"DEM CRS: {src_crs}")
print(f"DEM size: {src_width} x {src_height}")

# -----------------------------
# Project to metric CRS
# -----------------------------
# UTM Zone 43N is appropriate for Shiggaon
target_crs = "EPSG:32643"

print(f"\nReprojecting DEM to {target_crs}...")

transform, width, height = calculate_default_transform(
    src_crs,
    target_crs,
    src_width,
    src_height,
    *src_bounds
)

projected_dem = np.empty((height, width), dtype=np.float32)

reproject(
    source=dem,
    destination=projected_dem,
    src_transform=src_transform,
    src_crs=src_crs,
    dst_transform=transform,
    dst_crs=target_crs,
    resampling=Resampling.bilinear
)

print("DEM reprojection complete.")

# -----------------------------
# Calculate slope
# -----------------------------
print("\nCalculating slope...")

pixel_size_x = transform.a
pixel_size_y = abs(transform.e)

# Replace nodata temporarily
if nodata is not None:
    projected_dem[projected_dem == nodata] = np.nan

# Gradient in meters
dy, dx = np.gradient(
    projected_dem,
    pixel_size_y,
    pixel_size_x
)

# Slope in degrees
slope = np.degrees(
    np.arctan(
        np.sqrt(dx**2 + dy**2)
    )
)

print(
    f"Slope range: "
    f"{np.nanmin(slope):.2f}° → "
    f"{np.nanmax(slope):.2f}°"
)

# -----------------------------
# Reproject watersheds
# -----------------------------
gdf = gdf.to_crs(target_crs)

# -----------------------------
# Zonal statistics
# -----------------------------
print("\nExtracting slope statistics...")

stats = zonal_stats(
    gdf,
    slope,
    affine=transform,
    nodata=np.nan,
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
# Add slope features
# -----------------------------
for column in stats_df.columns:
    gdf[f"slope_{column}"] = stats_df[column].values

# -----------------------------
# Save
# -----------------------------
result = gdf.drop(columns="geometry")

result.to_csv(OUTPUT, index=False)

print("\n================================")
print("SLOPE PROCESSING COMPLETE")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(result)}")

print("\nColumns created:")

for column in result.columns:
    if "slope" in column:
        print(f"  ✓ {column}")
        