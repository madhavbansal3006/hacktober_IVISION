import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

WATERSHEDS = (
    BASE
    / "data/raw/shiggaon_micro_watersheds_deliverables/"
    / "shiggaon_micro_watersheds.gpkg"
)

SOIL_DIR = BASE / "data/raw/soil"
OUTPUT = BASE / "data/processed/soil_features.csv"

gdf = gpd.read_file(WATERSHEDS)

print(f"Micro-watersheds: {len(gdf)}")

soil_files = {
    "clay": SOIL_DIR / "clay_0_5cm_mean.tif",
    "sand": SOIL_DIR / "sand_0_5cm_mean.tif",
    "silt": SOIL_DIR / "silt_0_5cm_mean.tif",
    "soc": SOIL_DIR / "soc_0_5cm_mean.tif",
}

for name, raster_path in soil_files.items():

    print(f"\nExtracting {name}...")

    with rasterio.open(raster_path) as src:
        raster = src.read(1)
        affine = src.transform

    stats = zonal_stats(
        gdf,
        raster,
        affine=affine,
        stats=["mean"],
        all_touched=True
    )

    values = pd.DataFrame(stats)["mean"]

    gdf[f"{name}_mean"] = values

    print(f"  Valid values: {values.notna().sum()}/{len(values)}")

result = gdf.drop(columns="geometry")

print("\nMissing values:")
for name in soil_files:
    print(
        f"{name}_mean:",
        result[f"{name}_mean"].isna().sum()
    )

result.to_csv(OUTPUT, index=False)

print("\n================================")
print("SOIL PROCESSING COMPLETE")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(result)}")