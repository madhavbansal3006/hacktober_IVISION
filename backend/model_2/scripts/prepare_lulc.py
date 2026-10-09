import rasterio
import numpy as np
from pathlib import Path
from rasterio.enums import Resampling
from rasterio.warp import reproject

BASE = Path(__file__).resolve().parents[1]

LULC = BASE / "data/raw/lulc"
OUT = BASE / "data/processed/lulc"

OUT.mkdir(parents=True, exist_ok=True)


def find_band(name):
    files = list(LULC.glob(f"*_{name}_20m.jp2"))

    if not files:
        files = list(LULC.glob(f"*_{name}_10m.jp2"))

    if not files:
        raise FileNotFoundError(f"Could not find {name}")

    return files[0]


# ------------------------------------------------------------
# B11 is our 20 m reference grid
# ------------------------------------------------------------

reference_path = find_band("B11")

with rasterio.open(reference_path) as ref:

    ref_crs = ref.crs
    ref_transform = ref.transform
    ref_width = ref.width
    ref_height = ref.height
    ref_profile = ref.profile.copy()

print("Reference grid:")
print(" CRS:", ref_crs)
print(" Size:", ref_width, "x", ref_height)


bands = [
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B8A",
    "B11",
    "B12",
]

data = {}

print("\nLoading and aligning Sentinel-2 bands...")

for name in bands:

    path = find_band(name)

    print(f"  Loading {name}")

    with rasterio.open(path) as src:

        destination = np.empty(
            (ref_height, ref_width),
            dtype=np.float32
        )

        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear
        )

        # Sentinel-2 reflectance scaling
        destination /= 10000.0

        data[name] = destination


# ------------------------------------------------------------
# Spectral indices
# ------------------------------------------------------------

print("\nCalculating spectral indices...")


def safe_index(a, b):

    denominator = a + b

    result = np.full_like(
        a,
        np.nan,
        dtype=np.float32
    )

    valid = denominator != 0

    result[valid] = (
        (a[valid] - b[valid])
        / denominator[valid]
    )

    return result


# Vegetation
NDVI = safe_index(
    data["B8A"],
    data["B04"]
)

# Water
NDWI = safe_index(
    data["B03"],
    data["B8A"]
)

# Built-up
NDBI = safe_index(
    data["B11"],
    data["B8A"]
)

# Moisture
NDMI = safe_index(
    data["B8A"],
    data["B11"]
)


features = {
    "B02": data["B02"],
    "B03": data["B03"],
    "B04": data["B04"],
    "B05": data["B05"],
    "B06": data["B06"],
    "B07": data["B07"],
    "B8A": data["B8A"],
    "B11": data["B11"],
    "B12": data["B12"],
    "NDVI": NDVI,
    "NDWI": NDWI,
    "NDBI": NDBI,
    "NDMI": NDMI,
}


# ------------------------------------------------------------
# Export
# ------------------------------------------------------------

profile = ref_profile.copy()

# Force GeoTIFF output
profile["driver"] = "GTiff"
profile.update(
    dtype="float32",
    count=1,
    height=ref_height,
    width=ref_width,
    transform=ref_transform,
    crs=ref_crs,
    compress="lzw",
    nodata=-9999
)


for name, arr in features.items():

    output = OUT / f"{name}.tif"

    clean = np.where(
        np.isfinite(arr),
        arr,
        -9999
    ).astype("float32")

    with rasterio.open(
        output,
        "w",
        **profile
    ) as dst:

        dst.write(clean, 1)

    print(f"  ✓ {output.name}")


print("\n================================")
print("LULC FEATURES PREPARED")
print("================================")

print("Output:", OUT)
print("Features:", len(features))
print("Grid:", ref_width, "x", ref_height)