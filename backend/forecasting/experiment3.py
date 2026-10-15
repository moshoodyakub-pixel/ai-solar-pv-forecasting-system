"""EXP-003 expanding-origin development validation with no holdout scoring."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .ingestion import DataError
from .experiment2 import _parse, _feature_matrix, _metric, _packages, _code_sha, MODEL_PARAMS, SEED, WINDOW

EXPERIMENT_ID = "EXP-003"
FOLDS = 4
FOLD_HOURS = 336


def make_folds(n_eligible: int, count: int = FOLDS, hours: int = FOLD_HOURS):
    """Expand training and validate on nonoverlapping consecutive blocks in the first 85%."""
    if not (2 <= count <= 8 and 24 <= hours <= 1008):
        raise DataError("Choose 2–8 folds and a validation window of 24–1008 hours.")
    dev_end = int(.85 * n_eligible)
    first_train = dev_end - count * hours
    if first_train < max(240, 4 * WINDOW):
        raise DataError("Not enough development history for these fold settings.")
    folds = []
    for index in range(count):
        stop = first_train + index * hours
        folds.append({"fold": index+1, "training_start": 0, "training_end_exclusive": stop,
                      "validation_start": stop, "validation_end_exclusive": stop+hours})
    assert folds[-1]["validation_end_exclusive"] == dev_end
    return dev_end, folds


def _period(hour):
    if 7 <= hour <= 10:
        return "morning_07_10"
    if 11 <= hour <= 15:
        return "midday_11_15"
    if 16 <= hour <= 20:
        return "evening_16_20"
    return "other_hours"


def _lstm_inner_training(hist, clock, y, train_end, val_hist, val_clock):
    """Early-stop only on an INNER training split, not outer validation labels."""
    from .experiment2 import _train_lstm
    split = int(train_end * .9)
    if split < 200 or train_end-split < 24:
        raise DataError("Too little inner training data for LSTM early stopping.")
    p, extra = _train_lstm(hist[:split], clock[:split], y[:split],
        hist[split:train_end], clock[split:train_end], y[split:train_end],
        val_hist, val_clock)
    extra["inner_early_stopping_rows"] = train_end-split
    extra["inner_fit_rows"] = split
    return p, extra


def run_experiment3(frame: pd.DataFrame, *, target: str="Total PV Power",
                    source_bytes: bytes|None=None,
                    include_xgboost: bool=True, include_lstm: bool=True,
                    fold_count: int=FOLDS, fold_hours: int=FOLD_HOURS):
    day,hour,power,radiation = _parse(frame,target)
    idx,hist,clock = _feature_matrix(day,hour,power)
    x=np.column_stack([hist,clock])
    y=power[idx]
    development_end,specs=make_folds(len(idx),fold_count,fold_hours)
    model_names=["persistence_1h","persistence_24h","random_forest"]
    if include_xgboost:
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise DataError("Install XGBoost using requirements-ml.txt.") from exc
        model_names.append("xgboost")
    if include_lstm:
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise DataError("Install PyTorch using requirements-ml.txt.") from exc
        model_names.append("lstm")

    records=[]
    fold_metrics=[]
    fit_seconds={name:0.0 for name in model_names if name not in {"persistence_1h","persistence_24h"}}
    for spec in specs:
        tr_stop=spec["training_end_exclusive"]
        lo,hi=spec["validation_start"],spec["validation_end_exclusive"]
        val=slice(lo,hi)
        actual=y[val]
        sunlight=radiation[idx[val]]>0
        # This threshold is fitted using training-only observed generation ramps.
        train_indices=idx[:tr_stop]
        train_ramps=np.abs(power[train_indices]-power[train_indices-1])
        generating_train=radiation[train_indices]>0
        threshold=float(np.percentile(train_ramps[generating_train],90)) if generating_train.any() else 0.0
        ex_post_ramps=np.abs(power[idx[val]]-power[idx[val]-1])
        high=(ex_post_ramps>=threshold)&sunlight if threshold>0 else np.zeros_like(sunlight)
        preds={"persistence_1h":hist[val,-1].copy(),
               "persistence_24h":hist[val,-24].copy()}
        durations={}
        details={}
        start=perf_counter()
        rf=RandomForestRegressor(**MODEL_PARAMS["random_forest"])
        rf.fit(x[:tr_stop],y[:tr_stop])
        preds["random_forest"]=np.maximum(0,rf.predict(x[val]))
        durations["random_forest"]=round(perf_counter()-start,4)
        if include_xgboost:
            start=perf_counter()
            boost=XGBRegressor(**MODEL_PARAMS["xgboost"])
            boost.fit(x[:tr_stop],y[:tr_stop],verbose=False)
            preds["xgboost"]=np.maximum(0,boost.predict(x[val]))
            durations["xgboost"]=round(perf_counter()-start,4)
        if include_lstm:
            start=perf_counter()
            preds["lstm"],details["lstm"]=_lstm_inner_training(hist,clock,y,tr_stop,hist[val],clock[val])
            durations["lstm"]=round(perf_counter()-start,4)
        for name,seconds in durations.items():
            fit_seconds[name]+=seconds
        metrics={}
        for name in model_names:
            predicted=np.asarray(preds[name],dtype=float)
            if len(predicted)!=len(actual) or not np.isfinite(predicted).all():
                raise DataError(f"{name} returned invalid forecasts.")
            metrics[name]={
                "all_hours":_metric(actual,predicted),
                "generating_hours_ex_post":_metric(actual[sunlight],predicted[sunlight]),
                "high_ramp_ex_post":_metric(actual[high],predicted[high]),
                "bias_source_unit":round(float(np.mean(predicted-actual)),4)}
        for i,position in enumerate(range(lo,hi)):
            source=int(idx[position])
            records.append({
                "fold":spec["fold"],"source_row_1based":source+1,
                "relative_hour_index":source+1,"day":int(day[source]),
                "hour":int(hour[source]),"period":_period(int(hour[source])),
                "actual":float(y[position]),"generating_hour_ex_post":bool(sunlight[i]),
                "observed_abs_ramp_source_unit_ex_post":float(ex_post_ramps[i]),
                "high_ramp_ex_post":bool(high[i]),
                "forecasts":{name:float(preds[name][i]) for name in model_names}})
        spec=dict(spec)
        spec.update({
            "train_rows":tr_stop,"validation_rows":hi-lo,
            "validation_first_day":int(day[idx[lo]]),
            "validation_last_day":int(day[idx[hi-1]]),
            "validation_start_source_row":int(idx[lo])+1,
            "validation_end_source_row":int(idx[hi-1])+1,
            "ramp_threshold_p90_train_source_units":round(threshold,4),
            "metrics":metrics,"training_seconds":durations,"training_details":details})
        fold_metrics.append(spec)

    truth=np.array([r["actual"] for r in records])
    generating=np.array([r["generating_hour_ex_post"] for r in records],dtype=bool)
    high=np.array([r["high_ramp_ex_post"] for r in records],dtype=bool)
    periods=["morning_07_10","midday_11_15","evening_16_20","other_hours"]
    summaries,hourly={},{}
    for name in model_names:
        pred=np.array([r["forecasts"][name] for r in records])
        hourly[name]={period:_metric(truth[np.array([r["period"]==period for r in records])],
            pred[np.array([r["period"]==period for r in records])]) for period in periods}
        dif=pred-truth
        fold_mae=[f["metrics"][name]["all_hours"]["mae"] for f in fold_metrics]
        summaries[name]={
            "pooled_validation":_metric(truth,pred),
            "generating_hours_ex_post":_metric(truth[generating],pred[generating]),
            "high_ramp_ex_post":_metric(truth[high],pred[high]),
            "low_or_zero_ramp":_metric(truth[~high],pred[~high]),
            "signed_bias_source_unit":round(float(np.mean(dif)),4),
            "fold_mae_std":round(float(np.std(fold_mae,ddof=1)),4),
            "fold_mae_mean":round(float(np.mean(fold_mae)),4),
            "total_fit_seconds":round(fit_seconds.get(name,0.0),4)}
    ranking=sorted(model_names,key=lambda name:summaries[name]["pooled_validation"]["mae"])
    return {
        "schema_version":"3.0","experiment_id":EXPERIMENT_ID,"status":"evaluated",
        "source":"Zenodo 19245713","target":target,
        "unit":"original_dataset_unit_unresolved_W_or_Wh",
        "forecast_horizon":"one recorded hour ahead; rolling retrospective",
        "selection_rule":"lowest pooled outer-validation MAE; no reserved holdout accessed",
        "ranked_models":ranking,"development_recommendation":ranking[0],
        "data_quality":{
            "source_rows":len(frame),"eligible_rows":len(idx),
            "development_end_exclusive_eligible":development_end,
            "reserved_15pct_start_source_row_1based":int(idx[development_end])+1,
            "reserved_rows_NOT_evaluated":int(len(idx)-development_end),
            "fold_count":fold_count,"fold_hours":fold_hours,
            "validation_predictions":len(records),
            "last_evaluated_source_row_1based":records[-1]["source_row_1based"]},
        "model_scores":summaries,"time_of_day_metrics":hourly,
        "folds":fold_metrics,"predictions":records,
        "provenance":{
            "dataset_sha256":sha256(source_bytes).hexdigest() if source_bytes is not None else None,
            "generated_utc":datetime.now(timezone.utc).isoformat(),
            "source_code_commit":_code_sha(),"packages":_packages(),
            "seed":SEED,"window_hours":WINDOW,
            "model_parameters":{name:MODEL_PARAMS[name] for name in ["random_forest","xgboost","lstm"] if name in model_names},
            "fold_configuration":{
                "type":"expanding_train_disjoint_validation",
                "count":fold_count,"hours":fold_hours,"reserved_holdout_fraction":0.15,
                "high_ramp_cutoff":"fold-specific TRAIN-only generating-hour 90th percentile of abs(t minus t-1)"}
        },
        "warnings":[
            "All scored predictions are confined to the first 85% development period. EXP-002 test observations were NOT evaluated.",
            "EXP-002 test results have already been inspected. That historical period is no longer genuinely fresh unseen data. Obtain external measurements for final confirmation.",
            "Source PV output units unresolved W or Wh: metrics are source units, not kW.",
            "Hour buckets use the recorded Hour 1–24, not a verified local timezone.",
            "High-ramp and generating-hour labels use actual target-hour data ONLY for ex-post evaluation, never model inputs.",
            "LSTM inner early stopping uses only outer training data and fits the earlier 90% of each outer training fold; RF/XGBoost use all outer training samples.",
            "No verified capacity or site metadata; repeated folds on one plant do not establish cross-site generalisation."]}
