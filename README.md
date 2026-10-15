# AI-Driven Solar PV Forecasting System

A research prototype for **validated, one-hour-ahead solar photovoltaic (PV) power forecasting** using measured PV generation and chronological evaluation.

**Project:** Design of an AI-Driven Solar PV Forecasting System  
**Institution:** Miva Open University — Information Technology  
**Status:** v0.1 research prototype; retrospective evaluation, **not live operational forecasting**.

## Features

- Inspect CSV/XLSX measured PV datasets, including spreadsheets with numeric headers.
- Select timestamps and measured **AC PV power (kW)**; check data quality and hourly coverage.
- Chronologically split data into training (70%), validation (15%) and test (15%) sets.
- Benchmark one-hour and 24-hour persistence against Random Forest.
- Report MAE, RMSE, normalized RMSE and R² using an unseen test set.
- Optional simplified physical benchmark **only** when properly documented weather-forecast inputs are available.
- View genuine evaluation results in a custom responsive dashboard and export research-ready JSON.
- Enter site coordinates as metadata; coordinates alone do not prove site-specific forecast accuracy.

## Run locally

Use Python 3.12 (3.11 is also suitable):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. To run tests: `python -m pytest -q`.

## Data and research integrity

Measured hourly AC PV power is required for quantitative validation. The prototype does not contain a training dataset or pretrained model. Dataset files, secrets, learned artifacts and experimental outputs are excluded from version control. Do not claim results until they have been reproduced using documented measured data and forecast inputs.

Read [Methodology](docs/METHODOLOGY.md), [Data dictionary](docs/DATA_DICTIONARY.md) and [Implementation plan](docs/IMPLEMENTATION_PLAN.md).

## Planned work

Audit the measured PV dataset; integrate trustworthy forecasting-time meteorological inputs; add XGBoost and LSTM with fair tuning; extend validation across seasons and sites; improve reproducibility and reporting. These items are **not yet implemented**.

**Author:** Moshood Yakub Olalekan
