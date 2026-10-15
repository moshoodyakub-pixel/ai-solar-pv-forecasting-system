"""Research adapter for Zenodo 19245713 (orientation-diverse rooftop PV data).

The workbook provides Day 1..295 and Hour 1..24, but no documented year,
timezone, plant capacity, or unambiguous power unit. Never invent these.
Forecast results are retrospective, one-step-ahead values in source units.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from .ingestion import DataError

REQUIRED = {"Day", "Hour", "Total PV Power", "Solar Radiation"}
PV_TARGETS = ["Total PV Power", "PV-1 Power", "PV-2 Power", "PV-3 Power", "PV-4 Power", "PV-5 Power"]
FEATURES = ["lag_1", "lag_2", "lag_24", "lag_48", "rolling_mean_24", "sin_hour", "cos_hour", "sin_day", "cos_day"]


def is_orientation_dataset(frame: pd.DataFrame) -> bool:
    return REQUIRED.issubset(frame.columns) and all(c in frame.columns for c in PV_TARGETS)


def _score(actual: np.ndarray, prediction: np.ndarray) -> dict:
    if len(actual) == 0:
        return {"mae": None, "rmse": None, "r2": None, "sample_count": 0}
    return {"mae": round(float(mean_absolute_error(actual, prediction)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(actual, prediction))), 3),
            "r2": round(float(r2_score(actual, prediction)), 4) if len(actual) > 1 and np.std(actual) > 0 else None,
            "sample_count": len(actual)}


def evaluate_orientation(frame: pd.DataFrame, power_column: str = "Total PV Power") -> dict:
    if not is_orientation_dataset(frame):
        raise DataError("This workbook is not the expected Zenodo PV orientation dataset.")
    if power_column not in PV_TARGETS:
        raise DataError("Select Total PV Power or a single PV panel power measurement.")
    day = pd.to_numeric(frame["Day"], errors="coerce").to_numpy(dtype=float)
    hour = pd.to_numeric(frame["Hour"], errors="coerce").to_numpy(dtype=float)
    pv = pd.to_numeric(frame[power_column], errors="coerce").to_numpy(dtype=float)
    irradiance = pd.to_numeric(frame["Solar Radiation"], errors="coerce").to_numpy(dtype=float)
    if not (np.isfinite(day).all() and np.isfinite(hour).all() and np.isfinite(pv).all() and np.isfinite(irradiance).all()):
        raise DataError("Missing/invalid Day, Hour, solar radiation, or target PV power values.")
    if np.any(day != np.floor(day)) or np.any(hour != np.floor(hour)) or np.any((hour < 1) | (hour > 24)):
        raise DataError("Day must be an integer and Hour an integer between 1 and 24.")
    if (pv < 0).any() or (irradiance < 0).any():
        raise DataError("Unexpected negative PV output or solar radiation must be reviewed.")
    relative_hours = (day.astype(int) - int(day[0])) * 24 + hour.astype(int) - 1
    if not np.array_equal(relative_hours, np.arange(len(relative_hours))):
        raise DataError("Missing, duplicated or out-of-order Day/Hour records. Fix these before evaluation.")
    if len(pv) < 160:
        raise DataError("At least 160 hourly records are required.")
    indices = np.arange(48, len(pv))
    x = np.column_stack([
        pv[indices-1], pv[indices-2], pv[indices-24], pv[indices-48],
        np.array([pv[idx-24:idx].mean() for idx in indices]),
        np.sin(2*np.pi*(hour[indices]-1)/24), np.cos(2*np.pi*(hour[indices]-1)/24),
        np.sin(2*np.pi*day[indices]/365.25), np.cos(2*np.pi*day[indices]/365.25),
    ])
    y = pv[indices]
    n = len(y)
    cutoff_train = int(n * .7)
    cutoff_validation = int(n * .85)
    if min(cutoff_train, cutoff_validation-cutoff_train, n-cutoff_validation) < 20:
        raise DataError("Insufficient complete samples for a three-way chronological split.")
    train = slice(0, cutoff_train)
    validation = slice(cutoff_train, cutoff_validation)
    test = slice(cutoff_validation, n)
    forest = RandomForestRegressor(n_estimators=120, random_state=42, min_samples_leaf=3, n_jobs=-1)
    forest.fit(x[train], y[train])
    candidates = {
        "persistence_1h": pv[indices-1],
        "persistence_24h": pv[indices-24],
        "random_forest": forest.predict(x),
    }
    val_errors = {k: float(mean_absolute_error(y[validation], v[validation])) for k,v in candidates.items()}
    ranking = sorted(candidates, key=lambda name: val_errors[name])
    selected = ranking[0]
    daylight = irradiance[indices] > 0
    scores = {}
    for name, values in candidates.items():
        day_test = daylight[test]
        scores[name] = {
            "validation": _score(y[validation], values[validation]),
            "test": _score(y[test], values[test]),
            "test_generating_hours": _score(y[test][day_test], values[test][day_test]),
        }
    rows = []
    for idx in range(max(cutoff_validation, n - 240), n):
        src_index = int(indices[idx])
        rows.append({"relative_hour_index": src_index + 1,
                     "day": int(day[src_index]), "hour": int(hour[src_index]),
                     "label": f"Day {int(day[src_index])}, H{int(hour[src_index]):02d}",
                     "actual": round(float(y[idx]),3),
                     "forecasts": {name: round(float(values[idx]),3) for name, values in candidates.items()}})
    return {
        "status": "evaluated", "dataset_type": "zenodo_orientation", "source": "Zenodo 19245713",
        "target": power_column, "unit": "original_dataset_unit_unresolved_W_or_Wh",
        "forecast_horizon": "one recorded hour ahead", "selected_model": selected,
        "selection_rule": "lowest validation MAE", "ranking_validation": ranking, "scores": scores,
        "data_quality": {
            "total_source_rows": len(frame), "eligible_rows": n,
            "training_rows": cutoff_train,
            "validation_rows": cutoff_validation-cutoff_train,
            "test_rows": n-cutoff_validation,
            "day_range": [int(day.min()), int(day.max())],
            "first_test_day": int(day[int(indices[cutoff_validation])]),
            "first_test_hour": int(hour[int(indices[cutoff_validation])]),
            "test_generating_hours": int(np.sum(daylight[test])),
            "calendar_year": None, "timezone": None, "installed_capacity": None,
        },
        "sample_predictions": rows,
        "warnings": [
            "Output units are ambiguously documented as W or Wh; errors are reported in ORIGINAL DATASET UNITS, not kW.",
            "The workbook provides Day and Hour but no actual calendar year or timezone. No calendar timestamps have been fabricated.",
            "This is a rolling one-step-ahead retrospective test: the immediately preceding measured output is assumed available before prediction.",
            "Target-hour solar radiation is used only to define generating hours for RETROSPECTIVE reporting; it is not fed to the forecasting model.",
            "Without site capacity and forecast-time plane-of-array irradiance, nRMSE as a percentage of capacity and a physical benchmark cannot be defensibly reported.",
            "The field labelled Dewpoint contains values outside plausible dew-point Celsius ranges; do not use it as temperature/humidity until source metadata is clarified.",
        ]}