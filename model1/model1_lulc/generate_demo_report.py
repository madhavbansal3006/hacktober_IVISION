"""
Generate a demo-safe summary report and confidence visualization from the
EXISTING production outputs. Reads only; writes only new, additive files:
  outputs/demo_report.json
  outputs/demo_report.md
  outputs/lulc_confidence.png

Does not touch models/lulc_random_forest.joblib, outputs/lulc_prediction.tif,
outputs/lulc_confidence.tif, outputs/training_data.csv,
outputs/micro_watershed_lulc_statistics.csv, or outputs/metadata.json's
existing keys (metadata.json gets two additive keys appended separately,
see add_metadata_fields.py).
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from src.demo_report import (
    load_confidence_aligned, summarize_confidence_safe,
    load_watershed_statistics, watershed_reliability_summary,
)

PREDICTION_TIF = "outputs/lulc_prediction.tif"
CONFIDENCE_TIF = "outputs/lulc_confidence.tif"
WATERSHED_CSV = "outputs/micro_watershed_lulc_statistics.csv"
CLASS_STATS_CSV = "outputs/class_statistics.csv"


def main():
    with open("outputs/metadata.json") as f:
        metadata = json.load(f)

    # --- 1. Confidence: verify + cross-check against stored stats ---
    recomputed = summarize_confidence_safe(PREDICTION_TIF, CONFIDENCE_TIF)
    stored = metadata["confidence_stats"]
    matches = (
        abs(recomputed["mean_confidence"] - stored["mean_confidence"]) < 1e-6
        and abs(recomputed["low_confidence_pct"] - stored["low_confidence_pct"]) < 1e-6
    )
    print(f"Confidence stats cross-check (corrected validity mask vs stored metadata.json): "
          f"{'MATCH' if matches else 'MISMATCH'}")
    print(f"  Recomputed: mean={recomputed['mean_confidence']:.4f}, "
          f"low={recomputed['low_confidence_pct']:.2f}%, "
          f"medium={recomputed['medium_confidence_pct']:.2f}%, "
          f"high={recomputed['high_confidence_pct']:.2f}%")

    # --- 2. Watershed reliability ---
    wdf = load_watershed_statistics(WATERSHED_CSV)
    reliability = watershed_reliability_summary(wdf)
    print(f"\nWatershed reliability: {reliability['reliable_count']} reliable "
          f"(GOOD/ACCEPTABLE), {reliability['unreliable_count']} unreliable (LOW/INSUFFICIENT_DATA) "
          f"out of {reliability['total_watersheds']}")

    # --- 3. Class percentages (from existing class_statistics.csv) ---
    class_stats = pd.read_csv(CLASS_STATS_CSV)
    class_pct = dict(zip(class_stats["class_name"], class_stats["percent_of_classified_area"]))

    # --- Confidence visualization ---
    with rasterio.open(PREDICTION_TIF) as p, rasterio.open(CONFIDENCE_TIF) as c:
        pred = p.read(1)
        conf = c.read(1)
    valid = pred != 0
    display_conf = np.where(valid, conf, np.nan)

    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(display_conf, cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Model 1 — Prediction Confidence (max class probability)\n"
                  "Red=low (<0.5)  Yellow=medium (0.5-0.75)  Green=high (>=0.75)")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.04)
    cbar.set_label("Confidence")
    fig.tight_layout()
    fig.savefig("outputs/lulc_confidence.png", dpi=150)
    plt.close(fig)
    print("\nWrote outputs/lulc_confidence.png")

    # --- Assemble report ---
    report = {
        "study_area": "Shiggaon Taluk, Haveri District, Karnataka, India",
        "production_model": "Experiment B (equal-count sampling, class_weight=None)",
        "lulc_class_percent": {k: float(v) for k, v in class_pct.items()},
        "confidence": {
            "verification_status": "MATCH" if matches else "MISMATCH — investigate before demo",
            "nodata_fix_status": (
                "outputs/lulc_confidence.tif previously declared nodata=-1.0 in its GeoTIFF "
                "header while actual invalid pixels were physically stored as 0.0 (0 pixels "
                "equaled -1.0 in the file). This was identified and FIXED directly in the file: "
                "nodata is now consistently 0.0, matching both the actual invalid-pixel values "
                "and lulc_prediction.tif's own nodata convention. Verified: valid confidence "
                "pixels are unchanged (bit-identical before/after), prediction/confidence "
                "valid-pixel masks now match exactly, and the production model and all "
                "classification outputs (lulc_prediction.tif, training_data.csv, metrics, class "
                "encoding) were not touched by this fix."
            ),
            **recomputed,
        },
        "watershed_data_quality": reliability,
        "interpretation_guidance": {
            "GOOD": "coverage >= 90% of true watershed area — safe to interpret directly.",
            "ACCEPTABLE": "coverage 75-90% — usable with minor caveat.",
            "LOW": "coverage < 75% — statistics reflect only a small, possibly unrepresentative "
                   "fragment of the watershed. Do not present as if describing the whole watershed.",
            "INSUFFICIENT_DATA": "valid pixel count below the defensible minimum (100 px) — "
                                  "statistics should not be interpreted at all.",
        },
        "known_limitations": [
            "Built-up is over-predicted relative to WorldCover reference prevalence.",
            "Barren is over-predicted relative to WorldCover reference prevalence.",
            "Agriculture <-> Built-up spectral confusion exists.",
            "Water <-> Barren confusion exists because of heterogeneous reference labeling.",
            "36/66 micro-watersheds have LOW or INSUFFICIENT_DATA coverage.",
            "Only one Sentinel-2 date is currently used.",
            "No SCL/cloud-shadow masking is available.",
            "WorldCover is reference/pseudo-ground-truth and is not field-verified.",
        ],
    }

    with open("outputs/demo_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Wrote outputs/demo_report.json")

    md_lines = [
        "# Model 1 — Demo Report",
        f"\n**Study area**: {report['study_area']}",
        f"**Production model**: {report['production_model']}",
        "\n## LULC Class Percentages",
    ]
    for k, v in report["lulc_class_percent"].items():
        md_lines.append(f"- {k}: {v:.2f}%")
    md_lines.append("\n## Confidence")
    md_lines.append(f"- Status: {report['confidence']['verification_status']}")
    md_lines.append(f"- Mean confidence: {report['confidence']['mean_confidence']:.3f}")
    md_lines.append(f"- Low (<0.5): {report['confidence']['low_confidence_pct']:.1f}%")
    md_lines.append(f"- Medium (0.5-0.75): {report['confidence']['medium_confidence_pct']:.1f}%")
    md_lines.append(f"- High (>=0.75): {report['confidence']['high_confidence_pct']:.1f}%")
    md_lines.append(f"\n> lulc_confidence.tif nodata tag was previously inconsistent (-1.0 vs actual 0.0) — this was identified and fixed; nodata is now consistently 0.0. See demo_report.json for detail.")
    md_lines.append("\n## Micro-Watershed Data Quality")
    for cat, n in report["watershed_data_quality"]["category_counts"].items():
        md_lines.append(f"- {cat}: {n}")
    md_lines.append(f"\n**{report['watershed_data_quality']['unreliable_count']}/"
                     f"{report['watershed_data_quality']['total_watersheds']} watersheds are "
                     f"NOT reliable for interpretation** (LOW or INSUFFICIENT_DATA coverage).")
    md_lines.append("\n## Known Limitations")
    for lim in report["known_limitations"]:
        md_lines.append(f"- {lim}")

    with open("outputs/demo_report.md", "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print("Wrote outputs/demo_report.md")


if __name__ == "__main__":
    main()
