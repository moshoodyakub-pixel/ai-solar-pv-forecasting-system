# Methodology and research validity

## Aim and scope

Design and **evaluate** a reproducible AI-driven solar PV power forecasting system. Version 0.1 uses measured hourly AC PV power (`kW`) with a **one-hour-ahead** horizon. The predictions shown are historical out-of-sample evaluations, not a live future service. The optional location coordinates are metadata, not proof of local calibration.

## Baselines and algorithm

- `persistence_1h`: predict power at target hour *t* from measurement *t−1*.
- `persistence_24h`: predict power at *t* from measurement *t−24h*.
- `random_forest`: 120 trees, `min_samples_leaf=3`, seed 42; features `t−1`, `t−2`, `t−24`, `t−48`, trailing 24-hour mean of **past** power and cyclical local target hour/day-of-year. No feature uses the target-hour measured power.
- Optional `physical_pvwatts_style` benchmark: requires **AS-ISSUED target-hour forecasts** of plane-of-array irradiance and ambient temperature, and the site's known rated DC capacity. Simplified temperature and inverter corrections documented in `backend/forecasting/evaluation.py`. This is not a plant-calibrated physics model and must not be called measured generation.
- Optional AI weather inputs: forecast POA and temperature can be added when complete; these must be true predictions issued earlier, not target-hour observations. No weather input is assumed by default.

## Splitting and evaluation

1. Select authentic timestamp and measured AC power columns.
2. Convert supplied local timestamps using the **explicitly selected time zone**. Sort chronologically, reject duplicate timestamps, reject negative power values, and reject sub-hourly recordings. Keep hourly gaps as missing data; do not generate power readings.
3. Build features with historical power lags and calendar-derived time. Remove examples with incomplete target or required lags.
4. Chronologically split eligible rows 70% train, 15% validation, 15% **held-out test** (no shuffling).
5. Train one fixed Random Forest configuration on training rows. Select the best among the candidate methods by **minimum validation MAE**. Do not use test metrics for selection or tuning.
6. Evaluate all candidates on the same held-out test targets. Report MAE and RMSE in kW, R² when variance is nonzero, and normalized RMSE as percent of **known rated DC capacity** when capacity is supplied. Do not use MAPE near nighttime zero power.

### Rolling-origin caveat

Validation and testing use measured power from preceding hours when calculating lagged inputs. This is an operationally realistic **rolling one-hour-ahead backtest** only if data collection makes the previous-hour actual available before prediction. It does **not** establish a 24-hour-ahead forecast. For a day-ahead test, redesign inputs and baselines to prevent using same-day future measurements.

### Known limitations

- Raw plant data must be independently checked for curtailment, clipping, inverter outages, meter resets, time-zone and daylight-saving issues, and training/test leakage.
- Random Forest cannot be transferred to an unseen site based on coordinates alone. Cross-site testing and transfer learning are future work.
- CSV and first-sheet XLSX only, max 25 MB. Input `kWh` or 15-minute readings must be converted by a **documented** procedure before training.
- Early phase performs retrospective evaluation only; model persistence, scheduled live forecasts, live weather retrieval and model registry remain planned work.
- No measured dataset is shipped in the repository. The synthetic arrays used in unit tests are **test fixtures**, not research observations, and must never be included in project findings.
