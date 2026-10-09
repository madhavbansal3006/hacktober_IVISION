import geopandas as gpd
import rasterio
from shapely.geometry import box

boundary = gpd.read_file("data/raw/study_area/shiggaon_boundary.gpkg")
mws = gpd.read_file("data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg")

with rasterio.open("data/raw/lulc/lulc_prediction.tif") as src:
    raster_crs = src.crs
    raster_bounds = src.bounds
    raster_bbox_geom = box(*raster_bounds)

print("=== ID FIELD UNIQUENESS (micro-watersheds) ===")
for col in ["id", "MWS", "SUBWATERSH", "SUBCATCH"]:
    n_unique = mws[col].nunique()
    n_total = len(mws)
    print(f"  {col}: unique={n_unique} / total={n_total}  {'UNIQUE' if n_unique==n_total else 'NOT UNIQUE'}")

print("\n=== CRS SUMMARY ===")
print("boundary CRS:", boundary.crs)
print("micro_watersheds CRS:", mws.crs)
print("raster CRS:", raster_crs)

print("\n=== RASTER BOUNDS REPROJECTED TO EPSG:4326 ===")
raster_bbox_wgs84 = gpd.GeoSeries([raster_bbox_geom], crs=raster_crs).to_crs("EPSG:4326")
print("Raster bbox in WGS84:", raster_bbox_wgs84.total_bounds)
print("Boundary bbox (WGS84):", boundary.total_bounds)
print("MWS bbox (WGS84):", mws.total_bounds)

print("\n=== SPATIAL OVERLAP CHECKS ===")
# Does raster bbox cover the boundary polygon?
boundary_union = boundary.union_all()
raster_bbox_shape = raster_bbox_wgs84.iloc[0]
covers = raster_bbox_shape.contains(boundary_union)
intersects = raster_bbox_shape.intersects(boundary_union)
print("Raster bbox fully contains boundary polygon:", covers)
print("Raster bbox intersects boundary polygon:", intersects)
if not covers:
    diff = boundary_union.difference(raster_bbox_shape)
    print("  Boundary area NOT covered by raster (deg^2):", diff.area, "  (~fraction:", diff.area / boundary_union.area, ")")

# Does mws union cover boundary? (should roughly match/exceed)
mws_union = mws.union_all()
mws_covers_boundary = mws_union.contains(boundary_union)
mws_intersects_boundary = mws_union.intersects(boundary_union)
boundary_area = boundary_union.area
mws_boundary_overlap_area = mws_union.intersection(boundary_union).area
print("\nMicro-watersheds union contains boundary:", mws_covers_boundary)
print("Micro-watersheds union intersects boundary:", mws_intersects_boundary)
print(f"Boundary area covered by MWS: {100*mws_boundary_overlap_area/boundary_area:.2f}%")

# How many watersheds intersect boundary vs fall fully outside
mws_reproj = mws  # already 4326
intersecting = mws_reproj[mws_reproj.intersects(boundary_union)]
print(f"\nMicro-watersheds intersecting boundary: {len(intersecting)} / {len(mws_reproj)}")
fully_within = mws_reproj[mws_reproj.within(boundary_union)]
print(f"Micro-watersheds FULLY within boundary: {len(fully_within)} / {len(mws_reproj)}")

# geometry validity re-check with explicit buffer(0) test
print("\n=== GEOMETRY VALIDITY DETAIL ===")
print("Boundary invalid geoms:", (~boundary.geometry.is_valid).sum())
print("MWS invalid geoms:", (~mws.geometry.is_valid).sum())
