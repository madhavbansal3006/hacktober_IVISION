import geopandas as gpd
import fiona

for name, path in [
    ("shiggaon_boundary.gpkg", "data/raw/study_area/shiggaon_boundary.gpkg"),
    ("shiggaon_micro_watersheds.gpkg", "data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg"),
]:
    print(f"\n{'='*60}\n{name}\n{'='*60}")
    layers = fiona.listlayers(path)
    print("Layers:", layers)
    for layer in layers:
        gdf = gpd.read_file(path, layer=layer)
        print(f"\n--- Layer: {layer} ---")
        print("CRS:", gdf.crs)
        print("Feature count:", len(gdf))
        print("Geometry types:", gdf.geom_type.unique())
        print("Columns:", list(gdf.columns))
        print("Bounds:", gdf.total_bounds)
        print("Validity - is_valid all True?:", gdf.geometry.is_valid.all())
        if not gdf.geometry.is_valid.all():
            print("  Invalid count:", (~gdf.geometry.is_valid).sum())
        print("\nHead:")
        print(gdf.drop(columns='geometry').head(10).to_string())
        print("\nDtypes:")
        print(gdf.dtypes)
