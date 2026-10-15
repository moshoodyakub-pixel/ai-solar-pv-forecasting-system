# EXP-002 — Windows verification (15 October 2026)

**Status:** Independently verified five-model retrospective experiment from the researcher's uploaded evaluation JSON, prediction CSV and original `PV_Data.xlsx`. This is **preliminary single-holdout evidence**, not final cross-site accuracy. The raw files remain private to the user's local research archive; only scores, metadata and checksums are recorded here.

## Independent integrity checks

- JSON reports 1,055 held-out target hours; CSV contains exactly 1,055 matching rows and predictions for all five models.
- All CSV measured and predicted values match the JSON values; **zero mismatches**.
- Recomputed **full test** MAE/RMSE/R² and generating-hour metrics match the report to its exported rounding precision (maximum difference under 0.00005).
- Test rows have contiguous relative indices 6,026–7,080 (Day 252 Hour 2 through Day 295 Hour 24).
- Dataset SHA-256 matches the original workbook; model selected by **minimum validation MAE**, not test MAE.
- Reproducing Windows environment: Python 3.11.4, scikit-learn 1.9.1, XGBoost 3.2.0, PyTorch 2.14.1; code commit `5f091431ebdcb25cbb5b7d72b80f4c94b199fb5d`.

| Input / output | SHA-256 |
|---|---|
| Source PV_Data.xlsx | `5b23a5e2155ddeb0266c8d270488bdc13dd03f63791c969081b018843c93a005` |
| Evaluation JSON | `16586cae28c741adb9afcf1b302644eec10f5c7a9e93ea80a27bb3f4741df2c7` |
| Full-prediction CSV | `3da3abfadabd686a2bb8f27a9d5151edf8cd1a712c9112aa9be474bf4ca0a4eb` |

## Verified test scores

**Errors are in original source units (W/Wh unresolved); not kW.** Relative sequence only; no known year, location or PV plant rating.

| Model | Validation MAE | Test MAE | Test RMSE | Test R² | Generating-hour test MAE | Windows training (s) |
|---|---:|---:|---:|---:|---:|---:|
| **Random Forest** | 29.7671 | **39.7940** | **89.6830** | **0.95735** | **88.2837** | 2.752 |
| XGBoost | 32.4242 | 40.8450 | 90.2520 | 0.95681 | 88.4702 | 2.751 |
| LSTM | 44.1545 | 54.2348 | 102.4104 | 0.94439 | 111.9604 | 24.113 |
| 24h persistence | 42.5100 | 75.4701 | 190.9175 | 0.80672 | 171.8484 | n/a |
| 1h persistence | 99.6265 | 97.5640 | 174.1817 | 0.83912 | 208.8352 | n/a |

Original dataset 7,080 hours; after 48-hour warm-up, 7,032 eligible; 4,922 train / 1,055 validation / 1,055 held-out test; **455** ex-post generating-hour samples. LSTM best weights at epoch 12 of 14.

Random Forest reduced unseen-test MAE by approximately **47.27%** versus 24-hour persistence. Its MAE advantage versus XGBoost is **1.051 source units** (about 2.64% of XGBoost MAE), too small to establish general dominance from one holdout.

## Additional diagnostic findings

- Across 44 represented test days, the lowest *daily* MAE was achieved by 24h persistence on 16 days, RF on 14, XGBoost on 7, LSTM on 5 and 1h persistence on 2. Day-to-day variation matters even when RF wins overall.
- Radiation-zero test observations: RF forecast positive power 69 times, XGBoost 594 times and LSTM 131 times. Radiation-zero is **not necessarily nighttime**. Do not use **observed target-hour** solar radiation as a forecast-time gating variable.
- Generating-hour errors are considerably larger than overall errors; zero-power hours can make all-hour scores deceptively strong.
- Exploratory 44-day-block bootstrap (5,000 resamples, seed 42) for `MAE(XGBoost) - MAE(Random Forest)`: observed +1.051, approximate 95% interval **[-0.60, +2.65]** source units, including zero. This does not constitute cross-season or cross-site statistical evidence.

## Next research actions

Keep the current last-15%-in-time holdout untouched for future **final** comparisons; avoid repeatedly tuning after seeing its scores. Conduct rolling validation folds on historical development data, study errors on generation ramps, add a clock/solar-position gate only when legitimate future time/location inputs are established, and acquire a second measured AC-kW PV site with documented capacity and timestamps.

No full raw source workbook, predictions, secrets, or third-party experimental records are committed with this Markdown file.

[Experiment design](../../docs/EXPERIMENT_002.md) | [Implementation issue](../../issues/1)
