# Validation-Only Stability Study Report: Production V1 vs V2 Exp 4a

This report presents the validation-only stability study comparing the **frozen Production Model 1 (V1)** against the **V2 Exp 4a Candidate Model** (`experiments_v2/models/Exp_4a_Leaf_Regularization_minleaf2.joblib`) for the Shiggaon Watershed Intelligence System.

---

## 1. Executive Summary & Final Verdict

| Model | Evaluated Architecture | Features | Spatial Validation Protocol | Mean Macro-F1 | Mean Accuracy |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Production V1** | Random Forest (`n_est=200`, `min_samples_leaf=1`, default) | 9 | 20 Independent 300m Block Splits | **0.8047 ± 0.0054** | **80.31 ± 0.59%** |
| **V2 Exp 4a** | Random Forest (`n_est=200`, `min_samples_leaf=2`) | 11 (`+MNDWI +EVI`) | 20 Independent 300m Block Splits | **0.8077 ± 0.0053** | **80.57 ± 0.58%** |
| **Net Difference** | — | — | Paired t-test: $t = 10.83$, $p = 1.44 \times 10^{-9}$ | **+0.0031 ± 0.0013** | **+0.26 ± 0.12%** |

### Explicit Final Verdict
**V2 INCREMENTAL / INCONCLUSIVE — KEEP V1 FROZEN**

**Rationale**:
Although V2 Exp 4a demonstrates a statistically stable and consistent improvement across 19 of 20 validation splits ($p < 10^{-8}$) and enhances minority class recall (Built-up in 16/20 splits, Barren in 17/20 splits) without altering full-scene LULC proportions, the absolute performance gain (+0.31% Macro-F1, +0.26% Accuracy) is incremental in magnitude. Overwriting the frozen production model would break the frozen checksum contract, require recalculating all 66 micro-watershed zonal statistics, and risk calibration drift in Model 2 vulnerability scores. Therefore, **Production V1 must remain completely frozen**.

---

## 2. Methodology & Validation Setup

1. **Frozen Production Model (V1)**:
   - Checkpoint: `models/lulc_random_forest.joblib` (MD5: `ee9edc9e14f13457d4d7d929ae678933` — untouched).
   - Features (9): `['B2', 'B3', 'B4', 'B8', 'B11', 'NDVI', 'NDWI', 'NDBI', 'BSI']`.
2. **V2 Exp 4a Candidate Model**:
   - Checkpoint: `experiments_v2/models/Exp_4a_Leaf_Regularization_minleaf2.joblib`.
   - Features (11): `['B2', 'B3', 'B4', 'B8', 'B11', 'NDVI', 'NDWI', 'NDBI', 'BSI', 'MNDWI', 'EVI']`.
3. **Multi-Split Spatial Block Protocol**:
   - Evaluated on the held-out test data (`outputs/training_data.csv`, `split == 'test'`, 4,012 samples across 1,018 unique 300-meter spatial blocks).
   - Generated 20 independent validation splits using seeds `[42, 101, 202, 303, 404, 505, 606, 707, 808, 909, 1001, 1111, 1234, 1357, 2026, 3141, 4096, 5555, 7777, 9999]`.
   - In each split, 80% of spatial blocks (~814 blocks, ~3,200 samples) were sampled without replacement, preserving complete spatial block integrity and spatial autocorrelation controls.
   - Both models were evaluated on the exact same pixels for each split.

---

## 3. Aggregate Performance Statistics (Across 20 Splits)

### Global Metrics

| Metric | Production V1 Mean ± Std [Min, Max] | V2 Exp 4a Mean ± Std [Min, Max] | Mean Delta (V2 - V1) | Paired t-statistic | p-value |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Accuracy** | 80.31 ± 0.59% [78.46%, 80.96%] | 80.57 ± 0.58% [78.89%, 81.22%] | **+0.26 ± 0.12%** | $t = 9.87$ | $8.01 \times 10^{-9}$ |
| **Macro-F1** | 0.8047 ± 0.0054 [0.7875, 0.8122] | 0.8077 ± 0.0053 [0.7918, 0.8135] | **+0.0031 ± 0.0013** | $t = 10.83$ | $1.44 \times 10^{-9}$ |
| **Weighted-F1** | 0.8051 ± 0.0061 [0.7857, 0.8122] | 0.8080 ± 0.0060 [0.7900, 0.8149] | **+0.0028 ± 0.0012** | $t = 10.60$ | $2.09 \times 10^{-9}$ |

### Per-Class Metrics Comparison

| Class | Metric | Production V1 (Mean ± Std) | V2 Exp 4a (Mean ± Std) | Delta (V2 - V1) | Improvement Consistency |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Forest** | Precision | 0.9320 ± 0.0089 | **0.9442 ± 0.0082** | **+0.0122** | 20 / 20 splits |
| | Recall | **0.8903 ± 0.0125** | 0.8889 ± 0.0127 | -0.0014 | 8 / 20 splits |
| | **F1-Score** | 0.9106 ± 0.0064 | **0.9157 ± 0.0060** | **+0.0051** | **20 / 20 splits** |
| **Agriculture** | Precision | 0.7257 ± 0.0101 | **0.7340 ± 0.0108** | **+0.0082** | 19 / 20 splits |
| | Recall | 0.7846 ± 0.0142 | **0.7888 ± 0.0143** | **+0.0041** | 17 / 20 splits |
| | **F1-Score** | 0.7539 ± 0.0094 | **0.7603 ± 0.0099** | **+0.0064** | **19 / 20 splits** |
| **Water** | Precision | 0.9120 ± 0.0103 | **0.9184 ± 0.0092** | **+0.0064** | 17 / 20 splits |
| | Recall | **0.7692 ± 0.0146** | 0.7644 ± 0.0139 | -0.0047 | 4 / 20 splits |
| | **F1-Score** | **0.8345 ± 0.0104** | 0.8343 ± 0.0096 | -0.0002 | 9 / 20 splits |
| **Built-up** | Precision | **0.7664 ± 0.0116** | 0.7629 ± 0.0116 | -0.0035 | 6 / 20 splits |
| | Recall | 0.7632 ± 0.0135 | **0.7685 ± 0.0134** | **+0.0054** | 17 / 20 splits |
| | **F1-Score** | 0.7647 ± 0.0076 | **0.7656 ± 0.0078** | **+0.0009** | **16 / 20 splits** |
| **Barren** | Precision | **0.7072 ± 0.0124** | 0.7046 ± 0.0127 | -0.0026 | 7 / 20 splits |
| | Recall | 0.8207 ± 0.0136 | **0.8317 ± 0.0130** | **+0.0111** | 18 / 20 splits |
| | **F1-Score** | 0.7596 ± 0.0084 | **0.7628 ± 0.0082** | **+0.0032** | **17 / 20 splits** |

---

## 4. Aggregate Confusion Matrix Analysis (Summed Over 20 Splits, N = 63,209)

### Confusion Difference Matrix (V2 Exp 4a − Production V1)
```
                  Forest     Agri    Water  Built-up   Barren
Forest               -16      -42      +16       +42        0
Agriculture          -81      +48        0       +17      +16
Water                -15      +13      -70       -15      +87
Built-up             -33      -41        0       +71       +3
Barren               -13      -54     -104       +39     +132
```

### Minority Class Diagnostic Findings
1. **Barren Performance**:
   - V2 Exp 4a correctly classified **+132 additional Barren pixels** across the splits.
   - Crucially, Barren $\rightarrow$ Water misclassifications dropped by **-104** (from 1,078 down to 974).
   - Barren $\rightarrow$ Agriculture misclassifications dropped by **-54** (from 196 down to 142).
   - Barren F1 improved in **17 out of 20 splits (85%)**.
2. **Built-up Performance**:
   - V2 Exp 4a correctly classified **+71 additional Built-up pixels**.
   - Built-up $\rightarrow$ Agriculture confusion dropped by **-41** (from 2,222 down to 2,181).
   - Built-up $\rightarrow$ Forest confusion dropped by **-33** (from 216 down to 183).
   - Built-up F1 improved in **16 out of 20 splits (80%)**.

---

## 5. Summary of Outputs & File Integrity

All study outputs are stored exclusively in:
`model1/model1_lulc/experiments_v2/stability_validation/`

- Script: [`run_stability_study.py`](file:///c:/Users/madha/Downloads/shiggaon-watershed-intelligence/model1/model1_lulc/experiments_v2/stability_validation/run_stability_study.py)
- Full metrics JSON: [`stability_results.json`](file:///c:/Users/madha/Downloads/shiggaon-watershed-intelligence/model1/model1_lulc/experiments_v2/stability_validation/stability_results.json)
- Summary CSV: [`stability_summary_table.csv`](file:///c:/Users/madha/Downloads/shiggaon-watershed-intelligence/model1/model1_lulc/experiments_v2/stability_validation/stability_summary_table.csv)
- Report: [`STABILITY_VALIDATION_REPORT.md`](file:///c:/Users/madha/Downloads/shiggaon-watershed-intelligence/model1/model1_lulc/experiments_v2/stability_validation/STABILITY_VALIDATION_REPORT.md)

### Verification Checksum Confirmation
All 11 production assets were verified against `PROTECTION_MANIFEST_pre_t2_audit.txt`:
- `models/lulc_random_forest.joblib`: **OK** (`ee9edc9e14f13457d4d7d929ae678933`)
- `outputs/lulc_prediction.tif`: **OK** (`5e7606a2e0d858cc87100483d8506150`)
- `outputs/metadata.json`: **OK** (`e2c4a5b2f774571455c1c1ea2b47fed6`)
- `outputs/training_data.csv`: **OK** (`1acd667af2a9b85360d3ee9c6da175b3`)
- All 11 checksums match 100%. Zero production files were modified.
