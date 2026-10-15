# EXP-001 — Random Forest versus persistence baselines

**Status:** Completed preliminary retrospective validation (not final thesis results)  
**Recorded:** 15 October 2026  
**Academic project:** Design of an AI-Driven Solar PV Forecasting System  
**Target:** `Total PV Power`  
**Research data source:** [Zenodo record 19245713](https://zenodo.org/records/19245713)  
**Horizon:** One recorded hour ahead (rolling-origin retrospective evaluation)  
**Selection:** Lowest validation MAE, with a held-out chronological test period  
**Export:** `pv_chronological_evaluation.json` supplied by the researcher  
**Export SHA-256:** `880ad6149556f0b16a63488fde1ed14fdb497c7a33792dbf9d91ea1e28ee2e63`  
**Compatible source code:** Research adapter in this repository; **the JSON does not record the actual code commit**, so an exact run-to-commit attribution is not established.

## Data integrity and splits

| Attribute | Value |
|---|---|
| Dataset records | 7,080 |
| Eligible supervised examples after lag warm-up | 7,032 |
| Training examples (earliest 70%) | 4,922 |
| Validation examples (next 15%) | 1,055 |
| Unseen test examples (last 15%) | 1,055 |
| Test start | Relative Day 252, Hour 2 |
| Generating-hour test examples | 455 |
| Calendar year, source time zone and PV rated capacity | Not documented |
| PV output unit | **Unresolved: W or Wh** in the supplied source metadata |

All prediction errors below are reported in **original source units**, **not** kW. The reported R² values are dimensionless. Target-hour observed solar radiation is used solely for ex-post generating-hour stratification, not as a forecasting input.

## Validation and test results

| Method | Validation MAE | Test MAE | Test RMSE | Test R² | Generating-hour test MAE | Generating-hour test RMSE | Generating-hour test R² |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-hour persistence | 99.627 | 97.564 | 174.182 | 0.8391 | 208.835 | 258.460 | 0.5617 |
| 24-hour persistence | 42.510 | 75.470 | 190.918 | 0.8067 | 171.848 | 289.852 | 0.4487 |
| **Random Forest** | **30.820** | **38.977** | **88.689** | **0.9583** | **86.602** | **133.544** | **0.8830** |

Random Forest was selected on validation MAE and reduced unseen-test MAE by **48.35%** relative to the 24-hour persistence baseline and by **60.05%** relative to one-hour persistence.

## Export integrity checks

- JSON declares `status=evaluated`, `dataset_type=zenodo_orientation`, `selected_model=random_forest`, and a one-hour horizon.
- It reports three models and exactly 1,055 samples in each model's test summary.
- Only the **last 240** sample predictions are exported: contiguous relative indices **6,841–7,080**, Days **286–295**, each containing measured output and all three forecast values.
- No negative model predictions or absent actual values were detected among those 240 exported examples.
- Independent computation of **MAE over the 240 exported hours only** gives 40.600 (Random Forest), 81.121 (24-hour persistence), 95.075 (one-hour persistence). These are **not** the 1,055-hour test MAEs above, and the differing values are expected.
- Therefore, the supplied JSON alone **cannot independently reconstruct the 1,055-hour scores**. Preserve this distinction in the dissertation.

## Configuration and methodological limitations

The corresponding repository implementation trains a fixed Random Forest with 120 trees, `min_samples_leaf=3`, `random_state=42`, historical lags 1, 2, 24 and 48 hours, a trailing 24-hour mean and known day/hour cycles. This specification is reconstructed from the repository and **was not embedded as a versioned configuration in the exported JSON**.

- No verified PV kW conversion, installed capacity, weather-forecast inputs, physical-model benchmark or cross-site evaluation is available.
- The experiment is a historical **rolling one-hour-ahead backtest**, not a 24-hour-ahead or live forecasting demonstration.
- Do not claim model deployment, generalisation to Nigerian mini-grids or use at arbitrary site coordinates based on this experiment.
- Generating-hour evaluation matters because overnight zero output makes all-hours scores easier to achieve.
- Dataset units, field semantics and PV system parameters should be independently verified before final academic reporting.

## Requirements for EXP-002

1. Export **all 1,055 test predictions**, not only the final 240 used by the chart.
2. Save model hyperparameters, seed, package versions, Git commit and dataset SHA-256 with each run.
3. Use **the same** chronological train/validation/test intervals, target, lag features and metrics for Random Forest, XGBoost and LSTM.
4. Tune only on training/validation; never optimize against the held-out test set.
5. Report generating-hour scores, ramp/error analysis and training cost. Use appropriate sequential lookback for LSTM without leakage.
6. Resolve source-unit ambiguity and add a second independently documented measured PV dataset for stronger external validity.

The original research dataset and full exported predictions are **not committed here**. This file archives their descriptive metadata, checked metrics and export SHA-256. Keep the researcher-supplied JSON in the secure local experiment archive.
