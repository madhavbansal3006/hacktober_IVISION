# Model 1 — Demo Report

**Study area**: Shiggaon Taluk, Haveri District, Karnataka, India
**Production model**: Experiment B (equal-count sampling, class_weight=None)

## LULC Class Percentages
- Forest: 20.07%
- Agriculture: 63.08%
- Water: 0.73%
- Built-up: 14.46%
- Barren: 1.67%

## Confidence
- Status: MATCH
- Mean confidence: 0.783
- Low (<0.5): 7.0%
- Medium (0.5-0.75): 33.1%
- High (>=0.75): 59.8%

> lulc_confidence.tif nodata tag was previously inconsistent (-1.0 vs actual 0.0) — this was identified and fixed; nodata is now consistently 0.0. See demo_report.json for detail.

## Micro-Watershed Data Quality
- LOW: 35
- GOOD: 27
- ACCEPTABLE: 3
- INSUFFICIENT_DATA: 1

**36/66 watersheds are NOT reliable for interpretation** (LOW or INSUFFICIENT_DATA coverage).

## Known Limitations
- Built-up is over-predicted relative to WorldCover reference prevalence.
- Barren is over-predicted relative to WorldCover reference prevalence.
- Agriculture <-> Built-up spectral confusion exists.
- Water <-> Barren confusion exists because of heterogeneous reference labeling.
- 36/66 micro-watersheds have LOW or INSUFFICIENT_DATA coverage.
- Only one Sentinel-2 date is currently used.
- No SCL/cloud-shadow masking is available.
- WorldCover is reference/pseudo-ground-truth and is not field-verified.
