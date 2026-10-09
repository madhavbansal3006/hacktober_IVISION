import geopandas as gpd
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

WATERSHEDS = (
    BASE
    / "data/raw/shiggaon_micro_watersheds_deliverables/"
    / "shiggaon_micro_watersheds.gpkg"
)

RIVERS = (
    BASE
    / "data/raw/hydrology/"
    / "HydroRIVERS_v10_as.gdb/"
    / "HydroRIVERS_v10_as.gdb"
)

LAKES = (
    BASE
    / "data/raw/hydrology/"
    / "HydroLAKES_polys_v10_shp/"
    / "HydroLAKES_polys_v10_shp/"
    / "HydroLAKES_polys_v10.shp"
)

OUTPUT = BASE / "data/processed/hydrology_features.csv"

print("Loading micro-watersheds...")

watersheds = gpd.read_file(WATERSHEDS)

print(f"Watersheds: {len(watersheds)}")
print(f"CRS: {watersheds.crs}")

# Use projected CRS for distance/length calculations
watersheds = watersheds.to_crs("EPSG:32643")

# Save watershed area
watersheds["area_km2_calc"] = watersheds.geometry.area / 1_000_000

# Bounding box in WGS84 for efficient spatial filtering
bbox = tuple(watersheds.to_crs("EPSG:4326").total_bounds)
print("\nStudy area:")
print(f"West:  {bbox[0]}")
print(f"South: {bbox[1]}")
print(f"East:  {bbox[2]}")
print(f"North: {bbox[3]}")


# ============================================================
# HYRORIVERS
# ============================================================

print("\nLoading HydroRIVERS...")

rivers = gpd.read_file(
    RIVERS,
    layer="HydroRIVERS_v10_as",
    bbox=bbox
)

print(f"River segments in study area: {len(rivers)}")

rivers = rivers.to_crs("EPSG:32643")

river_features = []

for idx, ws in watersheds.iterrows():

    ws_id = ws["id"]
    polygon = ws.geometry

    intersecting = rivers[rivers.geometry.intersects(polygon)]

    if len(intersecting) == 0:

        river_features.append({
            "id": ws_id,
            "stream_length_km": 0,
            "drainage_density": 0,
            "max_river_order": 0,
            "mean_river_order": 0
        })

        continue

    # Clip rivers to watershed
    clipped = gpd.clip(intersecting, polygon)

    stream_length = clipped.geometry.length.sum() / 1000

    area = ws["area_km2_calc"]

    drainage_density = (
        stream_length / area
        if area > 0
        else 0
    )

    river_orders = pd.to_numeric(
        clipped["ORD_FLOW"],
        errors="coerce"
    ).dropna()

    river_features.append({
        "id": ws_id,
        "stream_length_km": stream_length,
        "drainage_density": drainage_density,
        "max_river_order": (
            river_orders.max()
            if len(river_orders) > 0 else 0
        ),
        "mean_river_order": (
            river_orders.mean()
            if len(river_orders) > 0 else 0
        )
    })

river_df = pd.DataFrame(river_features)


# ============================================================
# HYDROLAKES
# ============================================================

print("\nLoading HydroLAKES...")

lakes = gpd.read_file(
    LAKES,
    bbox=bbox
)

print(f"Lakes in study area: {len(lakes)}")

lakes = lakes.to_crs("EPSG:32643")

lake_features = []

for idx, ws in watersheds.iterrows():

    ws_id = ws["id"]
    polygon = ws.geometry

    intersecting = lakes[lakes.geometry.intersects(polygon)]

    if len(intersecting) == 0:

        lake_features.append({
            "id": ws_id,
            "lake_count": 0,
            "lake_area_km2": 0
        })

        continue

    clipped = gpd.clip(intersecting, polygon)

    lake_area = clipped.geometry.area.sum() / 1_000_000

    lake_features.append({
        "id": ws_id,
        "lake_count": len(clipped),
        "lake_area_km2": lake_area
    })

lake_df = pd.DataFrame(lake_features)


# ============================================================
# MERGE
# ============================================================

result = watersheds[[
    "id"
]].copy()

result = result.merge(
    river_df,
    on="id",
    how="left"
)

result = result.merge(
    lake_df,
    on="id",
    how="left"
)

# Fill watersheds without rivers/lakes
for col in [
    "stream_length_km",
    "drainage_density",
    "max_river_order",
    "mean_river_order",
    "lake_count",
    "lake_area_km2"
]:

    result[col] = result[col].fillna(0)


# ============================================================
# VALIDATION
# ============================================================

print("\n================================")
print("HYDROLOGY PROCESSING COMPLETE")
print("================================")

print(f"Rows: {len(result)}")
print(f"Columns: {len(result.columns)}")

print("\nMissing values:")
print(result.isna().sum())

print("\nSample:")
print(result.head())

result.to_csv(
    OUTPUT,
    index=False
)

print(f"\nOutput: {OUTPUT}")