import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

MONTHLY = BASE / "data/processed/monthly_environmental_features_v2.csv"
HYDRO = BASE / "data/processed/hydrology_features.csv"

OUTPUT = BASE / "data/processed/monthly_environmental_features_v3.csv"

print("Loading environmental features...")
monthly = pd.read_csv(MONTHLY)

print("Loading hydrology features...")
hydro = pd.read_csv(HYDRO)

print(f"Monthly observations: {len(monthly)}")
print(f"Hydrology watersheds: {len(hydro)}")

hydro_cols = [
    "id",
    "stream_length_km",
    "drainage_density",
    "max_river_order",
    "mean_river_order",
    "lake_count",
    "lake_area_km2"
]

hydro = hydro[hydro_cols]

merged = monthly.merge(
    hydro,
    on="id",
    how="left",
    validate="many_to_one"
)

if len(merged) != len(monthly):
    raise ValueError(
        f"Row count changed: {len(monthly)} → {len(merged)}"
    )

print("\nMissing hydrology values:")

for col in hydro_cols[1:]:
    print(f"{col}: {merged[col].isna().sum()}")

print(f"\nUnique watersheds: {merged['id'].nunique()}")

merged.to_csv(OUTPUT, index=False)

print("\n================================")
print("HYDROLOGY FEATURES ADDED")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(merged)}")
print(f"Columns: {len(merged.columns)}")