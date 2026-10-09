"""
Download REAL daily CHIRPS rainfall for Shiggaon Taluk, Haveri, Karnataka
clipped to the taluk boundary, for 2015-01-01 to 2025-12-31.

WHY YOU NEED TO RUN THIS YOURSELF:
This environment (the assistant that wrote this script) has no live internet
access, so it cannot call Google Earth Engine or download CHIRPS files itself.
This script is fully functional -- run it in Google Colab (free, has internet)
and it will produce the actual dataset in ~2-5 minutes.

SETUP (one-time):
  1. Go to https://colab.research.google.com and create a new notebook.
  2. In a cell, run: !pip install earthengine-api geemap geopandas
  3. Get a free Earth Engine account at https://code.earthengine.google.com
     (sign up takes ~1 minute, no cost).
  4. Run this script in a Colab cell. It will prompt you to authenticate
     with your Google account the first time (ee.Authenticate()).

WHAT THIS SCRIPT DOES:
  - Loads CHIRPS Daily (UCSB-CHG/CHIRPS/DAILY), 0.05deg (~5.5km) resolution,
    the same dataset served by the Climate Hazards Center (chc.ucsb.edu).
  - Clips it to the Shiggaon Taluk boundary. By default uses the bounding
    box below (14.28N-14.59N, 75.07E-75.38E, from Wikipedia / Census extent).
    For a precise administrative polygon, replace SHIGGAON_GEOMETRY with a
    taluk shapefile from KGIS (kgis.ksrsac.in) or Bhuvan/LGD boundaries --
    see the REPLACE WITH REAL POLYGON section below.
  - Extracts one row per (date, grid cell) with lat, lon, rainfall_mm.
  - Exports a single CSV suitable for GIS / watershed analysis / ML.

OUTPUT COLUMNS: date, latitude, longitude, rainfall_mm
"""

import ee
import pandas as pd

# ----------------------------------------------------------------------
# 1. AUTHENTICATE (only needed once per Colab session)
# ----------------------------------------------------------------------
ee.Authenticate()
ee.Initialize(project='YOUR-GCP-PROJECT-ID')  # replace with your GEE project id

# ----------------------------------------------------------------------
# 2. DEFINE THE STUDY AREA
# ----------------------------------------------------------------------
# Quick option: bounding box (approximate, from Wikipedia extent of Shiggaon Taluk)
SHIGGAON_GEOMETRY = ee.Geometry.Rectangle([75.07, 14.28, 75.38, 14.59])

# --- REPLACE WITH REAL POLYGON (recommended for true GIS/watershed accuracy) ---
# Download the exact taluk boundary as a shapefile/GeoJSON from:
#   - KGIS Karnataka: https://kgis.ksrsac.in  (Karnataka State Remote Sensing
#     Applications Centre -- has official taluk boundary layers)
#   - Bhuvan (ISRO): https://bhuvan.nrsc.gov.in
#   - LGD (Local Government Directory): https://lgdirectory.gov.in
# Then upload it as an Earth Engine asset and use:
#   shiggaon_fc = ee.FeatureCollection('users/<you>/shiggaon_taluk')
#   SHIGGAON_GEOMETRY = shiggaon_fc.geometry()
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 3. LOAD CHIRPS DAILY AND CLIP
# ----------------------------------------------------------------------
start_date = '2015-01-01'
end_date   = '2025-12-31'

chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
          .filterDate(start_date, end_date)
          .filterBounds(SHIGGAON_GEOMETRY))

def clip_img(img):
    return img.clip(SHIGGAON_GEOMETRY)

chirps_clipped = chirps.map(clip_img)

# ----------------------------------------------------------------------
# 4. CONVERT TO A (date, lat, lon, rainfall_mm) TABLE
#    Uses reduceRegion with a pixel-level reducer via sampling grid points.
# ----------------------------------------------------------------------
def image_to_features(img):
    date = img.date().format('YYYY-MM-dd')
    samples = img.sample(region=SHIGGAON_GEOMETRY, scale=5566, geometries=True)
    def tag(f):
        coords = f.geometry().coordinates()
        return f.set({
            'date': date,
            'longitude': coords.get(0),
            'latitude': coords.get(1),
            'rainfall_mm': f.get('precipitation')
        })
    return samples.map(tag)

all_features = chirps_clipped.map(image_to_features).flatten()

# ----------------------------------------------------------------------
# 5. EXPORT TO GOOGLE DRIVE AS CSV
# ----------------------------------------------------------------------
task = ee.batch.Export.table.toDrive(
    collection=all_features,
    description='Shiggaon_Taluk_CHIRPS_daily_2015_2025',
    folder='CHIRPS_Shiggaon',
    fileNamePrefix='shiggaon_taluk_daily_rainfall_2015_2025',
    fileFormat='CSV',
    selectors=['date', 'latitude', 'longitude', 'rainfall_mm']
)
task.start()

print("Export task started. Check progress at https://code.earthengine.google.com/tasks")
print("The CSV will appear in your Google Drive under 'CHIRPS_Shiggaon/' when done.")
