# EXP-003 Windows verification — 16 October 2026

**Verdict: PASSED.** The researcher uploaded `EXP-003_rolling_validation.json` and `EXP-003_all_validation_predictions.csv`. An independent Python audit compared 1,344 complete rows across the files (including measured output, indices, fold labels, retrospective strata, and 6,720 model predictions), then recomputed pooled, fold, generating-hour, ramp and time-of-day MAE/RMSE/R² metrics. **Zero discrepancies after documented score rounding.**

## Reproducibility

| File | SHA-256 |
|---|---|
| Source `PV_Data.xlsx` | `5b23a5e2155ddeb0266c8d270488bdc13dd03f63791c969081b018843c93a005` |
| `EXP-003_rolling_validation.json` | `41e5cfd5ef0ae645d591e6fc5ce666beb846d21662ad58451a0fd69911171850` |
| `EXP-003_all_validation_predictions.csv` | `b252796e53da3f4c8ff71fd252963f7d41feae4efe0b4fd345ec0d544da0c754` |

Source code at run: `3cfef4fae2c7dc7d76eca98ed1b99b17822b6aa5`. Recorded libraries: NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.1, XGBoost 3.2.0, PyTorch 2.14.1; seed 42, 48-h input window. Original target units remain **ambiguous W or Wh; do NOT label kW**.

## Train/validation boundary check

Four disjoint expanding validation folds, each 336 hourly predictions: source rows 4,682–5,017; 5,018–5,353; 5,354–5,689; 5,690–6,025. Recorded training ends are strictly before each validation fold. Reserved EXP-002 test starts **row 6,026**, so **no EXP-003 validation prediction overlaps the holdout**. EXP-002 test results were examined previously and therefore are no longer a *fresh* independent test for model changes.

## Validation results (original source units)

| Model | Pooled MAE | RMSE | R² | Generating-hour MAE (662 observations) | High-ramp MAE (61 observations) | Total training seconds |
|---|---:|---:|---:|---:|---:|---:|
| **Random Forest** | **27.7445** | **63.6706** | **0.97923** | **55.5005** | **112.6007** | 5.6683 |
| XGBoost | 31.4093 | 65.5414 | 0.97799 | 61.7208 | 123.8001 | 2.5401 |
| 24-hour persistence | 39.7321 | 104.6728 | 0.94386 | 80.2855 | 122.1803 | 0 |
| LSTM | 47.9617 | 83.5149 | 0.96426 | 86.2158 | 233.2905 | 24.5554 |
| 1-hour persistence | 98.7827 | 162.0379 | 0.86547 | 189.9411 | 462.1475 | 0 |

Random Forest pooled MAE is 30.17% lower than the 24-hour persistence comparator and 11.67% lower than XGBoost in development validation.

| Fold | RF MAE | XGBoost MAE | 24h persistence MAE | LSTM MAE |
|---|---:|---:|---:|---:|
| 1 | 24.8613 | 29.7899 | 29.2530 | 43.7395 |
| 2 | 32.7912 | 34.4993 | 50.0952 | 54.9785 |
| 3 | 25.8795 | 31.6120 | 40.9554 | 53.6604 |
| 4 | 27.4461 | 29.7361 | 38.6250 | 39.4685 |

RF wins all four folds, but only 28 of 57 represented relative day labels have RF as the **daily** lowest-MAE model; 24-hour persistence leads 21 days (LSTM four, XGBoost three, 1-hour persistence one). The largest RF daily MAE appears on relative Day 245 (103.30 source units). RF morning/ midday/evening MAE: 52.31 / 63.38 / 27.94; high-ramp MAE is roughly 4.75 times the low-ramp MAE (112.60 vs 23.71).

## Limits and next experiment decision

High-ramp and generating-hour labels are **ex-post diagnostics**, never valid target-hour predictors. Ramp thresholds were computed using fold training data. The LSTM uses an inner training subset for early stopping; its effective training regime differs from RF/XGBoost. The series has no verified calendar year, timezone, installed capacity, site coordinates, or unequivocal power unit. Four adjacent folds from one PV plant do not establish cross-site generalisation.

**Recommended next step:** preserve/freeze these development configurations and results, write the Chapter Four analysis, and acquire a genuinely independent timestamped, rated, measured AC-kW PV dataset for final confirmation. Do not retune based on the already-seen EXP-002 test segment.

[Methodology](../../docs/EXPERIMENT_003.md) | [Tracking issue](../../issues/2)
