# Experiment 002 — Auditable RF / XGBoost / LSTM Comparison

**Status:** First implementation is complete; model results remain preliminary, not final dissertation findings.

## Start in PyCharm (Python 3.11 or 3.12)

```powershell
git pull origin main
python -m pip install -r requirements-ml.txt
python -m pytest -q
python -m uvicorn backend.main:app --reload
```

At http://127.0.0.1:8000 upload and **Inspect** the original `PV_Data.xlsx`. In the *Experiment 002* section, select XGBoost and LSTM and click **Run Experiment 002**. Download the complete JSON and CSV from the resulting panel. Both contain predictions for the entire chronological test partition.

**API:** `POST /api/experiment2` takes an XLSX multipart `file`, `power_column` (default `Total PV Power`), `include_xgboost` and `include_lstm`. The app retains no uploaded workbook on disk.

## Fair comparison and no-leakage protocol

- Exactly 48 previous measured PV values (t−48 through t−1), plus four known target-hour/relative-day cycle features, comprise the **same forecast-information set** for RF, XGBoost and LSTM.
- RF and XGBoost receive the 48 lagged features as a vector; LSTM consumes them as an ordered historical sequence, merging known calendar terms only after its LSTM layer.
- Source contains 7,080 complete relative hourly samples. Drop the first 48 lag-warmup samples. Split the remaining 7,032 **chronologically**, not randomly: 4,922 train, 1,055 validation, 1,055 test.
- Choose the final model by **validation MAE only**. Test labels do not enter fitting, normalization, early stopping, or model selection.
- Random Forest: 120 trees, leaf size 3, seed 42. XGBoost: 160 estimators, depth 4, learning rate 0.06, seed 42. LSTM: 24 hidden units, 32-unit dense layer, up to 14 epochs, patience 4, Adam 0.004, batch 256, seed 42 on CPU. These are initial fixed configurations; **no test-driven hyperparameter search**.
- Compute all-hours MAE/RMSE/R² and generating-hours metrics, where target-hour observed solar radiation is used **only for retrospective reporting**, never prediction.
- Rolling **one-hour-ahead** testing presumes the preceding measured PV value is available at the issue time. This does not demonstrate 24-hour-ahead or multi-site accuracy.

## Experimental exporter

The `EXP-002_full_evaluation.json` includes:

- 1,055 test rows with relative day/hour, actual values, all requested model predictions, and the ex-post generating-hour flag.
- Train/validation/test metrics, model selection rule, source unit warning, training runtimes and LSTM best epoch.
- Original uploaded workbook's SHA-256 (raw bytes), source reference, runtime timestamp, Python version, platform, library versions, random seed, hyperparameters, window length, and Git commit SHA **when the program is running inside a Git checkout**.
- All 1,055 rows also downloadable as `EXP-002_all_test_predictions.csv` for manual recomputation.

## Initial local results using original research workbook

**Errors are in original, unresolved source units (W or Wh), NOT kW.** These numbers were produced in the test environment; reproduce them on your own machine before including them in the dissertation.

| Model | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|
| Random Forest | **39.7940** | **89.6830** | **0.95735** |
| XGBoost | 40.8450 | 90.2520 | 0.95681 |
| LSTM | 54.2348 | 102.4104 | 0.94439 |
| 24h persistence | 75.4701 | 190.9175 | 0.80672 |
| 1h persistence | 97.5640 | 174.1817 | 0.83912 |

Unlike EXP-001, the AI models use a common 48-lag input history. This **changes** the Random Forest feature representation, so avoid attributing differences to the addition of XGBoost or LSTM.

## Limitations

No confirmed W-versus-Wh source unit, installed PV kW rating, calendar year, timezone or measured site coordinates. No physical-model benchmark without source PV geometry and forecast-time weather. More rolling validation folds and a second independently measured AC-power dataset are needed before strong generalization claims.

Raw dataset and generated results remain outside GitHub. Tests using synthetic values are software tests, not research observations.
