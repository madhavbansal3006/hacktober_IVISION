import rasterio
import numpy as np
import json

path = "data/raw/lulc/lulc_prediction.tif"

with rasterio.open(path) as src:
    print("=== RASTER: lulc_prediction.tif ===")
    print("CRS:", src.crs)
    print("Width:", src.width)
    print("Height:", src.height)
    print("Count (bands):", src.count)
    print("Dtype:", src.dtypes)
    print("Transform:", src.transform)
    print("Resolution (x,y):", src.res)
    print("Bounds:", src.bounds)
    print("NoData:", src.nodata)
    print("Tags:", src.tags())
    print("Band 1 tags:", src.tags(1))
    print("Color interp:", src.colorinterp)

    arr = src.read(1)
    print("\nArray shape:", arr.shape)
    print("Array dtype:", arr.dtype)

    unique, counts = np.unique(arr, return_counts=True)
    print("\nUnique values and pixel counts:")
    total = arr.size
    for u, c in zip(unique, counts):
        print(f"  value={u}  count={c}  pct={100*c/total:.3f}%")

    # Check for a colormap (often encodes class->color, sometimes with labels)
    try:
        cmap = src.colormap(1)
        print("\nColormap present, entries:", len(cmap))
        print("Sample colormap entries:", list(cmap.items())[:10])
    except Exception as e:
        print("\nNo colormap:", e)
