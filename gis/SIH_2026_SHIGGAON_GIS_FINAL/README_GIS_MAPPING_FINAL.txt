SIH 2026 – SHIGGAON TALUK
FINAL GIS MAPPING PACKAGE
============================================

Project: GIS-based watershed and risk-analysis mapping
Study Area: Shiggaon Taluk, Haveri District, Karnataka
Project CRS: EPSG:32643 (WGS 84 / UTM Zone 43N)

PURPOSE
-------
This is the final GIS handoff package for the Shiggaon Taluk SIH 2026 project.
It organizes the completed GIS datasets for team use and presentation.

IMPORTANT DATA RULES
--------------------
1. The 66 fine-scale project micro-watersheds are the primary analytical units.
2. Use the MWS field/code as the common bridge for micro-watershed joins and
   integration between LULC, Model-2 and geo-coded observations.
3. Do not replace the 66 project micro-watersheds with the coarse WRIS watershed
   polygons.
4. Treat the original source/project datasets as authoritative. Do not overwrite
   or modify the original source data.
5. The final folder contains exported individual layers for team sharing.
6. Project/analysis CRS: EPSG:32643. Do not change the analytical CRS to EPSG:4326.
7. OpenStreetMap is only a contextual basemap and is not required as portable data.
8. Model-2 erosion output was intentionally excluded from the final risk layer set.

FOLDER STRUCTURE
----------------
00_PROJECT_CONTROL
    README and project/control documentation.

01_STUDY_AREA
    Shiggaon Taluk study-area boundary.

02_BOUNDARIES
    Taluk, village, district and state boundaries.

03_MICRO_WATERSHEDS
    66-micro-watershed datasets and final 66-MWS spatial integration data.

04_HYDROLOGY
    Rivers/drainage, waterbodies, derived stream network, Strahler stream order,
    flow accumulation and flow direction.

05_TERRAIN
    DEM and terrain derivatives: DEM Filled, Slope, Aspect and Hillshade.

06_SOIL
    Soil / FAO soil mapping.

07_RAINFALL
    Rainfall time-series and 2024 rainfall data.

08_LULC_REMOTE_SENSING
    Model-1 LULC prediction and LULC confidence rasters.

09_MODEL_2_RISK
    Individual Model-2 risk layers:
      - M2_Flood_Risk
      - M2_Water_Stress_Risk
      - M2_Ecosystem_Risk
      - M2_ML_Anomaly_Risk

10_GEO_CODED_IMAGES
    Geo-coded image supporting material and team handoff data.

11_CONTEXT_REFERENCE
    Supporting WRIS watershed, sub-basin and habitation/context layers.

KEY DATA
--------
Primary analytical unit:
    66 fine-scale Shiggaon micro-watersheds.

Primary final spatial integration:
    Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL

Common integration key:
    MWS / mws_id

MODEL-1 LULC CLASSES
--------------------
1 = Forest
2 = Agriculture
3 = Water
4 = Built-up
5 = Barren

The final Model-2 GIS integration uses the authoritative Model-1 LULC statistics
for the 66 micro-watersheds.

LULC COVERAGE NOTE
------------------
The 66 micro-watersheds extend beyond the Shiggaon Taluk boundary, while the
Model-1 LULC raster is approximately limited to the taluk study area. Therefore,
LULC-derived interpretation should consider the LULC coverage/confidence status.

Verified Model-1 LULC coverage categories across the 66 MWS:
    LOW = 35
    GOOD = 27
    ACCEPTABLE = 3
    INSUFFICIENT_DATA = 1

MODEL-2 RISK
------------
The final Model-2 integration contains the latest risk information and
intervention-priority fields for the 66 MWS.

Latest risk categories:
    CRITICAL = 5
    HIGH = 15
    MODERATE = 17
    LOW = 29

Latest primary risk drivers:
    Ecosystem Risk = 8
    ML Anomaly = 20
    Water Stress = 38

Risk calculation:
    base_risk_score =
        0.35 * water_stress_score
      + 0.35 * flood_risk_score
      + 0.30 * ecosystem_risk_score

    final_risk_score =
        0.80 * base_risk_score
      + 0.20 * ml_anomaly_score

HYDROLOGY / STREAM ORDER
------------------------
The project-derived Strahler stream-order raster is the authoritative
project-derived stream-order product and has a maximum order of 5.

Do not silently replace this project-derived stream order with external river-order
values. If another source is used, validate it separately before integration.

GEO-CODED IMAGE HANDOFF
-----------------------
The 66-MWS MWS/mws_id identifier is the integration bridge for geo-coded imagery.

Recommended metadata:
    image_id
    file_name
    latitude
    longitude
    timestamp / capture_datetime
    mws_id / MWS
    village
    image_type / observation_type
    description

Do not modify teammate/source imagery. Preserve original filenames and metadata.

QGIS WORKFLOW
-------------
1. Load the required layers from their respective final folders.
2. Use the 66-MWS final spatial integration as the main analysis framework.
3. Use MWS as the common join/integration field.
4. Use hydrology and terrain layers for watershed interpretation.
5. Check LULC coverage/confidence before interpreting LULC results.
6. Use the four Model-2 risk layers for individual risk visualization.
7. Use the final 66-MWS integration for combined risk and intervention analysis.

FINAL HANDOFF STATUS
--------------------
This folder is the organized GIS handoff package for the SIH 2026 Shiggaon project.
Team members should use the individual exported layers for analysis, mapping,
visualization and presentation without rebuilding the completed GIS workflow.

Prepared for team handoff.
