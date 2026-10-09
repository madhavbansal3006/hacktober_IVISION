import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

MONTHLY = BASE / "data/processed/monthly_environmental_features.csv"
SOIL = BASE / "data/processed/soil_features.csv"

OUTPUT = BASE / "data/processed/monthly_environmental_features_v2.csv"

print("Loading monthly environmental data...")
monthly = pd.read_csv(MONTHLY)

print("Loading soil features...")
soil = pd.read_csv(SOIL)

print(f"Monthly observations: {len(monthly)}")
print(f"Soil watersheds: {len(soil)}")

# Keep only the soil features needed for Model 2
soil = soil[
    [
        "id",
        "clay_mean",
        "sand_mean",
        "silt_mean",
        "soc_mean"
    ]
]

# Make sure each watershed has only one soil record
if soil["id"].duplicated().any():
    raise ValueError("Duplicate watershed IDs found in soil data.")

# Add soil values to every monthly observation
merged = monthly.merge(
    soil,
    on="id",
    how="left",
    validate="many_to_one"
)

# Make sure we didn't lose observations
if len(merged) != len(monthly):
    raise ValueError(
        f"Row count changed! Before: {len(monthly)}, "
        f"After: {len(merged)}"
    )

print("\nMissing soil values:")

for col in [
    "clay_mean",
    "sand_mean",
    "silt_mean",
    "soc_mean"
]:
    print(f"{col}: {merged[col].isna().sum()}")

# Check watershed coverage
print(f"\nUnique watersheds: {merged['id'].nunique()}")

merged.to_csv(OUTPUT, index=False)

print("\n================================")
print("SOIL FEATURES ADDED")
print("================================")
print(f"Output: {OUTPUT}")
print(f"Rows: {len(merged)}")
print(f"Columns: {len(merged.columns)}")