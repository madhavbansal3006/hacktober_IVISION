Shiggaon Taluk DEM - Copernicus GLO-30
========================================

File: Shiggaon_Taluk_DEM_GLO30.tif
- Source dataset : Copernicus DEM GLO-30 (ESA / AWS Open Data)
- Source tiles    : Copernicus_DSM_COG_10_N14_00_E075_00_DEM
                     Copernicus_DSM_COG_10_N15_00_E075_00_DEM
- Resolution      : 30 m (1 arc-second, ~0.000278 deg pixel)
- CRS             : EPSG:4326 (WGS 84, geographic lat/lon)
- Data type       : Float32, elevation in metres
- NoData value    : -9999.0
- Extent          : clipped to the Shiggaon Taluk administrative boundary
                     (OpenStreetMap relation 4198132, admin_level=6,
                     LGD subdistrict code 5489)
- Raster size     : 1027 x 1072 pixels
- Elevation range : ~540 m to ~738 m within the taluk

File: Shiggaon_Taluk_Boundary.geojson
- The exact taluk boundary polygon used to clip the DEM (from OpenStreetMap).

Processing steps performed:
1. Mosaicked the two 1x1 degree GLO-30 tiles covering the taluk
   (it straddles the 15N tile boundary).
2. Rasterised the taluk polygon and masked out all pixels outside it
   (set to NoData), cropped to the polygon's bounding extent.
3. Wrote a single-band, georeferenced GeoTIFF (deflate-compressed,
   EPSG:4326) suitable for direct use in QGIS/GIS watershed workflows
   (fill sinks, flow direction/accumulation, stream extraction, etc.).

Notes for QGIS:
- The file loads directly with correct CRS (EPSG:4326) - no manual
  georeferencing needed.
- For hydrological analysis (e.g. TauDEM, GRASS r.watershed, SAGA),
  it's usually best to reproject to a local projected CRS in metres
  (e.g. UTM Zone 43N, EPSG:32643) before running flow-direction/
  flow-accumulation tools, since the native CRS is geographic (degrees).
