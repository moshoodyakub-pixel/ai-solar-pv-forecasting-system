# Experiment 003 — Expanding-Window Validation and Error Diagnostics

**Status:** Implemented; local results are preliminary development-validation evidence. No newly untouched external dataset has been evaluated.

## Start on Windows / PyCharm

```powershell
git pull origin main
python -m pip install -r requirements-ml.txt
python -m pytest -q
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`, upload the original `PV_Data.xlsx`, click **Inspect file**, scroll to **Experiment 003**, then click **Run Experiment 003**. Default: four expanding folds, each 14 days (336 hours), XGBoost and LSTM included.

Download **full validation JSON** and **every validation prediction CSV**. The API is `POST /api/experiment3` with the original XLSX `file`, `power_column`, `fold_count` (2–8), `fold_days` (1–42), and boolean `include_xgboost` and `include_lstm`. The original XLSX stays in memory and is never saved in GitHub.

## Why this experiment is different

EXP-002 used one chronological 70/15/15 split and we have **already inspected its final 15% test scores**. EXP-003 treats the **earliest 85% as a development pool** and scores only disjoint expanding-window validation blocks inside that pool. The previously inspected test-period labels are not used in model fitting, diagnostics or evaluation. Nevertheless, they are *not a genuinely new unseen test set anymore*. Obtain a second externally documented measured-PV dataset for genuinely fresh final confirmation.

Default fold indices are 0-based after 48-hour lag warm-up. The 7,080 source records yield 7,032 eligible targets. Early 85% contains 5,977 eligible targets. The last 1,055 eligible targets (source rows 6,026–7,080) are excluded.

| Fold | Expanding training examples | Validation examples | Validation relative days |
|---|---:|---:|---|
| 1 | 4,633 | 336 | Day 196–210 |
| 2 | 4,969 | 336 | Day 210–224 |
| 3 | 5,305 | 336 | Day 224–238 |
| 4 | 5,641 | 336 | Day 238–252 |

The label at each validation time is forecast one hour ahead, assuming the previous actual PV measurement becomes available before issuance. No target-hour observed irradiance is supplied as a feature. RF and XGBoost use 48 prior hourly measurements and 4 known calendar cycles; LSTM sees the same sequence and cycles. RF/XGBoost train on all outer-training rows; LSTM uses the earliest 90% for fitting and the latest 10% of **outer training only** for inner early stopping. This sample-size distinction must be retained when comparing results.

## Diagnostics (ex-post, not forecast input)

- **All hours:** pooled MAE, RMSE, R² from every one of the disjoint validation observations, not averages of rounded fold errors.
- **Generating hours:** only target hours with measured observed solar radiation greater than zero; this source value is used *only for reporting*, never as an available target-time forecast.
- **High-ramp hours:** target generating-hour absolute PV change \|PV(t)−PV(t−1)\| at least the **90th percentile of training-only generating-hour absolute changes** in the corresponding fold. Threshold is recomputed using each fold's training history only.
- **Clock-hour groups:** recorded hours 07–10, 11–15, 16–20, others. These do not establish actual sunrise/sunset because real timezone is unknown.
- **Model stability:** MAE per fold and sample standard deviation of fold MAEs, as well as signed forecast bias and total training runtime.

### Preliminary local development results

Original source output units unresolved W or Wh, **not kW**:

| Method | Pooled MAE | Generating-hour MAE | High-ramp MAE |
|---|---:|---:|---:|
| Random Forest | **27.7445** | **55.5005** | **112.6007** |
| XGBoost | 31.4093 | 61.7208 | 123.8001 |
| 24h persistence | 39.7321 | 80.2855 | 122.1803 |
| LSTM | 47.9624 | 86.2157 | 233.2877 |
| 1h persistence | 98.7827 | 189.9411 | 462.1475 |

1,344 development validation predictions, including 662 generating-hour observations and 61 high-ramp observations in the first local run. The production model is **not retrained or deployed** by this experiment.

## Reproducibility limitations

- Dataset SHA-256, full fold definitions, time-specific threshold, selected hyperparameters, model runtime, source commit where available and every validation prediction are present in the JSON export.
- The published PV measurement units remain ambiguous (W vs Wh), with no known panel capacity, calendar year, actual zone or location. Do not report kW, physical performance or country-specific accuracy.
- Validation windows in one site do not establish external generalisation, and LSTM's early stopping has a different effective training sample size.
- Any new hyperparameter tuning should occur within the development protocol; published EXP-002 test scores cannot be treated as an untouched tuning target.

See [EXP-002](EXPERIMENT_002.md) and [EXP-001](../experiments/EXP-001/README.md).
