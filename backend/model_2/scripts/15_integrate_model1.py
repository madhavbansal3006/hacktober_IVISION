import pandas as pd
from pathlib import Path


# ============================================================
# MODEL 1 → MODEL 2 LULC INTEGRATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

MODEL2_INPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "model2_features_final.csv"
)

MODEL1_LULC = (
    BASE_DIR.parent
    / "model1_lulc"
    / "outputs"
    / "micro_watershed_lulc_statistics.csv"
)

OUTPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "model2_features_v3.csv"
)


print("=" * 50)
print("MODEL 1 → MODEL 2 LULC INTEGRATION")
print("=" * 50)


# ------------------------------------------------------------
# 1. Load datasets
# ------------------------------------------------------------

print("\nLoading Model 2 dataset...")
model2 = pd.read_csv(MODEL2_INPUT)

print(f"Model 2 rows: {len(model2)}")
print(f"Model 2 watersheds: {model2['id'].nunique()}")


print("\nLoading Model 1 LULC statistics...")
lulc = pd.read_csv(MODEL1_LULC)

print(f"Model 1 rows: {len(lulc)}")
print(f"Model 1 watersheds: {lulc['internal_id'].nunique()}")


# ------------------------------------------------------------
# 2. Validate IDs
# ------------------------------------------------------------

model2_ids = set(model2["id"])
model1_ids = set(lulc["internal_id"])

common_ids = model2_ids & model1_ids

print("\nID matching:")
print(f"  Model 2 IDs: {len(model2_ids)}")
print(f"  Model 1 IDs: {len(model1_ids)}")
print(f"  Common IDs:  {len(common_ids)}")


missing_from_model1 = model2_ids - model1_ids

if missing_from_model1:
    print(
        f"\nWARNING: {len(missing_from_model1)} Model 2 watersheds "
        "are missing from Model 1."
    )
else:
    print("\n✓ All Model 2 watersheds found in Model 1")


# ------------------------------------------------------------
# 3. Select and rename Model 1 features
# ------------------------------------------------------------

lulc = lulc[
    [
        "internal_id",
        "forest_percent",
        "agriculture_percent",
        "water_percent",
        "builtup_percent",
        "barren_percent",
        "pct_of_watershed_within_raster_extent",
        "valid_pixel_count",
        "coverage_category",
    ]
].copy()


lulc = lulc.rename(
    columns={
        "internal_id": "id",
        "forest_percent": "forest_pct",
        "agriculture_percent": "agriculture_pct",
        "water_percent": "water_pct",
        "builtup_percent": "builtup_pct",
        "barren_percent": "barren_pct",
        "pct_of_watershed_within_raster_extent": "lulc_coverage_pct",
        "valid_pixel_count": "lulc_valid_pixel_count",
        "coverage_category": "lulc_coverage_category",
    }
)


# ------------------------------------------------------------
# 4. Remove old LULC fields from Model 2
# ------------------------------------------------------------

old_lulc_columns = [
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "other_pct",
]

existing_old_columns = [
    c for c in old_lulc_columns if c in model2.columns
]

if existing_old_columns:
    print("\nRemoving old LULC fields:")
    for col in existing_old_columns:
        print(f"  - {col}")

    model2 = model2.drop(columns=existing_old_columns)


# ------------------------------------------------------------
# 5. Merge Model 1 → Model 2
# ------------------------------------------------------------

print("\nMerging Model 1 LULC features...")

model2_v3 = model2.merge(
    lulc,
    on="id",
    how="left",
    validate="many_to_one",
)


# ------------------------------------------------------------
# 6. Validate merge
# ------------------------------------------------------------

print("\nChecking merge...")

new_lulc_columns = [
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "barren_pct",
    "lulc_coverage_pct",
    "lulc_valid_pixel_count",
    "lulc_coverage_category",
]

print("\nMissing values:")
print(
    model2_v3[new_lulc_columns]
    .isna()
    .sum()
    .to_string()
)


# ------------------------------------------------------------
# 7. Coverage statistics
# ------------------------------------------------------------

print("\nLULC coverage statistics:")

print(
    model2_v3["lulc_coverage_pct"]
    .describe()
    .round(2)
    .to_string()
)


print("\nCoverage categories:")

print(
    model2_v3["lulc_coverage_category"]
    .value_counts()
    .to_string()
)


# ------------------------------------------------------------
# 8. Validate LULC percentages
# ------------------------------------------------------------

lulc_pct_columns = [
    "forest_pct",
    "agriculture_pct",
    "builtup_pct",
    "water_pct",
    "barren_pct",
]

model2_v3["lulc_pct_sum"] = (
    model2_v3[lulc_pct_columns]
    .sum(axis=1)
)

print("\nLULC percentage sum:")
print(
    model2_v3["lulc_pct_sum"]
    .describe()
    .round(2)
    .to_string()
)


# ------------------------------------------------------------
# 9. Save
# ------------------------------------------------------------

model2_v3.to_csv(OUTPUT, index=False)

print("\n" + "=" * 50)
print("MODEL 1 → MODEL 2 INTEGRATION COMPLETE")
print("=" * 50)

print(f"Output: {OUTPUT}")
print(f"Rows: {len(model2_v3)}")
print(f"Columns: {len(model2_v3.columns)}")

print("\nNew LULC features:")

for col in new_lulc_columns:
    print(f"  ✓ {col}")

print("\n✓ Original model2_features_final.csv was NOT modified.")
print("✓ Model 2 V2 risk results were NOT modified.")