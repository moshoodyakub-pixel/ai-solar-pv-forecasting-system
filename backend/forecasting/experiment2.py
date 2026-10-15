"""EXP-002: auditable rolling one-hour-ahead PV power forecasting experiment.

Every model sees the same 48 *past* PV observations plus known target-hour calendar
features. The source workbook lacks verified dates, locations, capacities, and
unambiguous W/Wh output units. Do not silently infer those values.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .ingestion import DataError

SOURCE = "Zenodo 19245713"
EXPERIMENT = "EXP-002"
SEED = 42
WINDOW = 48
MODEL_PARAMS = {
    'random_forest': {'n_estimators': 120, 'min_samples_leaf': 3,
                      'random_state': SEED, 'n_jobs': -1},
    'xgboost': {'n_estimators': 160, 'max_depth': 4, 'learning_rate': 0.06,
                'subsample': 1.0, 'colsample_bytree': 1.0,
                'objective': 'reg:squarederror', 'random_state': SEED,
                'n_jobs': 2},
    'lstm': {'hidden_size': 24, 'batch_size': 256, 'max_epochs': 14,
              'patience': 4, 'learning_rate': 0.004, 'random_seed': SEED,
              'device': 'cpu'}
}


def _parse(frame: pd.DataFrame, target: str):
    targets = {'Total PV Power', *(f'PV-{k} Power' for k in range(1, 6))}
    if target not in targets:
        raise DataError('Select Total PV Power or one of the five measured PV panel outputs.')
    required = ['Day', 'Hour', 'Solar Radiation', target]
    if any(c not in frame.columns for c in required):
        raise DataError('Upload the original orientation-diverse PV dataset with Day, Hour and power fields.')
    values = {}
    for field in required:
        values[field] = pd.to_numeric(frame[field], errors='coerce').to_numpy(dtype=float)
        if not np.all(np.isfinite(values[field])):
            raise DataError(f'{field}: missing or invalid source observations; do not impute.')
    day, hour, power, radiation = [values[c] for c in ['Day', 'Hour', target, 'Solar Radiation']]
    if len(power) < 250:
        raise DataError('Insufficient hourly history: at least 250 observations required.')
    if (power < 0).any() or (radiation < 0).any():
        raise DataError('Negative power or radiation detected; review source measurements.')
    if (day != np.floor(day)).any() or (hour != np.floor(hour)).any() or ((hour < 1) | (hour > 24)).any():
        raise DataError('Day and Hour must be integer, with Hour in 1–24.')
    sequence = (day.astype(np.int64) - 1)*24 + hour.astype(np.int64) - 1
    if not np.array_equal(sequence, np.arange(len(sequence))):
        raise DataError('Day/Hour order is not a complete consecutive series starting at Day 1 Hour 1.')
    return day, hour, power, radiation


def _feature_matrix(day, hour, power):
    index = np.arange(WINDOW, len(power))
    history = np.lib.stride_tricks.sliding_window_view(power, WINDOW)[:len(index)]
    # history[i] = power[t-48:t], never power[t].
    clock = np.column_stack([
        np.sin(2*np.pi*(hour[index]-1)/24),
        np.cos(2*np.pi*(hour[index]-1)/24),
        np.sin(2*np.pi*day[index]/365.25),
        np.cos(2*np.pi*day[index]/365.25)
    ])
    return index, history.copy(), clock


def _metric(y, p):
    if len(y) == 0:
        return {'mae': None, 'rmse': None, 'r2': None, 'sample_count': 0}
    err = np.asarray(p) - np.asarray(y)
    return {'mae': round(float(np.mean(np.abs(err))), 4),
            'rmse': round(float(np.sqrt(np.mean(err**2))), 4),
            'r2': round(float(r2_score(y, p)), 5) if len(y) > 1 and np.std(y)>0 else None,
            'sample_count': int(len(y))}


def _code_sha():
    value = os.environ.get('GIT_COMMIT_SHA') or os.environ.get('GITHUB_SHA')
    if value:
        return value
    try:
        root = Path(__file__).resolve().parents[2]
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, stderr=subprocess.DEVNULL, timeout=2).decode().strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _packages():
    names = ['numpy', 'pandas', 'scikit-learn', 'xgboost', 'torch']
    results = {}
    for name in names:
        try:
            results[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            results[name] = None
    return results


def _train_lstm(train_hist, train_clock, ytrain, val_hist, val_clock, yval,
                all_hist, all_clock):
    """Single-variable past-power sequence + deterministic calendar covariates.

    Normalize using TRAINING data only. Early stopping uses validation MAE;
    test labels are never read here.
    """
    try:
        import torch
        from torch import nn
        from torch.utils.data import TensorDataset, DataLoader
    except ImportError as exc:
        raise DataError('LSTM requires PyTorch: python -m pip install -r requirements-ml.txt') from exc
    torch.set_num_threads(min(4, torch.get_num_threads()))
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    if hasattr(torch, 'use_deterministic_algorithms'):
        torch.use_deterministic_algorithms(True)
    scale = max(1.0, float(np.percentile(ytrain, 99)))
    dtype = np.float32
    def tensor(x): return torch.from_numpy(np.asarray(x, dtype=dtype))
    class Forecaster(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=MODEL_PARAMS['lstm']['hidden_size'], batch_first=True)
            self.out = nn.Sequential(nn.Linear(MODEL_PARAMS['lstm']['hidden_size'] + 4, 32),
                                     nn.ReLU(), nn.Linear(32, 1))
        def forward(self, history, clock):
            seq, _ = self.lstm(history)
            return self.out(torch.cat([seq[:, -1, :], clock], dim=1)).squeeze(-1)
    model = Forecaster()
    optimizer = torch.optim.Adam(model.parameters(), lr=MODEL_PARAMS['lstm']['learning_rate'])
    training_data = TensorDataset(tensor(train_hist[:, :, None]/scale),tensor(train_clock),tensor(ytrain/scale))
    loader = DataLoader(training_data, batch_size=MODEL_PARAMS['lstm']['batch_size'],shuffle=True,
                        generator=torch.Generator().manual_seed(SEED))
    val_h, val_c = tensor(val_hist[:, :, None]/scale), tensor(val_clock)
    best_score = float('inf')
    best_state = None
    bad_epochs = 0
    best_epoch = 0
    for epoch in range(MODEL_PARAMS['lstm']['max_epochs']):
        model.train()
        for bh, bc, by in loader:
            optimizer.zero_grad()
            pred = model(bh,bc)
            loss = torch.mean((pred-by)**2)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            raw = model(val_h,val_c).numpy()*scale
            score = float(mean_absolute_error(yval, np.maximum(0.0,raw)))
        if score < best_score - 1e-5:
            best_score = score
            best_state = {k: v.detach().clone() for k,v in model.state_dict().items()}
            best_epoch = epoch+1
            bad_epochs=0
        else:
            bad_epochs += 1
            if bad_epochs >= MODEL_PARAMS['lstm']['patience']:
                break
    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()
    preds=[]
    with torch.no_grad():
        for start in range(0, len(all_hist), 512):
            end = min(len(all_hist),start+512)
            prediction = model(tensor(all_hist[start:end,:,None]/scale),tensor(all_clock[start:end]))
            preds.extend(prediction.numpy().tolist())
    return np.maximum(0.0,np.array(preds)*scale), {'best_epoch':best_epoch,
      'epochs_run':epoch+1,'scaler_p99_train_source_units':round(scale,4),
      'selected_validation_mae':round(best_score,4)}


def run_experiment(frame: pd.DataFrame, *, target: str='Total PV Power',
                   source_bytes: bytes|None=None, include_xgboost: bool=True,
                   include_lstm: bool=True) -> dict:
    day,hour,power,radiation = _parse(frame,target)
    idx,hist,clock = _feature_matrix(day,hour,power)
    features=np.column_stack([hist,clock])
    labels=power[idx]
    n=len(idx)
    train_end=int(.7*n)
    validation_end=int(.85*n)
    train=slice(0,train_end)
    val=slice(train_end,validation_end)
    test=slice(validation_end,n)
    val_mask = radiation[idx[val]]>0
    test_mask = radiation[idx[test]]>0
    ytrain,yval=labels[train],labels[val]
    scores={}
    timing={}
    details={}
    predictions={
        'persistence_1h': hist[:,-1].copy(),
        'persistence_24h': hist[:,-24].copy()
    }
    t0=perf_counter()
    rf=RandomForestRegressor(**MODEL_PARAMS['random_forest'])
    rf.fit(features[train],ytrain)
    predictions['random_forest']=np.maximum(0,rf.predict(features))
    timing['random_forest']=round(perf_counter()-t0,3)
    if include_xgboost:
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise DataError('XGBoost is not installed: python -m pip install -r requirements-ml.txt') from exc
        t0=perf_counter()
        booster=XGBRegressor(**MODEL_PARAMS['xgboost'])
        booster.fit(features[train], ytrain, verbose=False)
        predictions['xgboost']=np.maximum(0,booster.predict(features))
        timing['xgboost']=round(perf_counter()-t0,3)
    if include_lstm:
        t0=perf_counter()
        predictions['lstm'],details['lstm']=_train_lstm(hist[train],clock[train],ytrain,
             hist[val],clock[val],yval,hist,clock)
        timing['lstm']=round(perf_counter()-t0,3)
    for name,pred in predictions.items():
        scores[name] = {
            'validation':_metric(labels[val],pred[val]),
            'test':_metric(labels[test],pred[test]),
            'test_generating_hours':_metric(labels[test][test_mask],pred[test][test_mask]),
            'validation_generating_hours':_metric(labels[val][val_mask],pred[val][val_mask]),
        }
    ranking=sorted(scores,key=lambda k:(scores[k]['validation']['mae'],k))
    selected=ranking[0]
    test_rows=[]
    # Full, not downsampled, holdout prediction export for audit/recomputed metrics.
    for i in range(validation_end,n):
        origin=int(idx[i])
        test_rows.append({'source_row_1based':origin+1,'day':int(day[origin]),
            'hour':int(hour[origin]),'relative_hour_index':origin+1,
            'actual':float(labels[i]),'generating_hour_ex_post':bool(radiation[origin]>0),
            'forecasts':{k:float(v[i]) for k,v in predictions.items()}})
    result={
        'schema_version':'2.0','experiment_id':EXPERIMENT,
        'status':'evaluated','source':SOURCE,'target':target,
        'unit':'original_dataset_unit_unresolved_W_or_Wh',
        'prediction_horizon':'one recorded hour ahead, rolling-origin retrospective',
        'forecast_information_set':'previous 48 observed power values and known cyclical target-hour/day index',
        'selected_model':selected,'selection_rule':'lowest validation MAE; final test not used for selection',
        'ranking_validation':ranking,'scores':scores,
        'data_quality':{'source_rows':len(frame),'eligible_rows':n,
                        'train_rows':train_end,'validation_rows':validation_end-train_end,
                        'test_rows':n-validation_end,'test_generating_hours':int(test_mask.sum()),
                        'train_end_day':int(day[idx[train_end-1]]),
                        'test_start_day':int(day[idx[validation_end]]),
                        'test_start_hour':int(hour[idx[validation_end]]),
                        'calendar_year':None,'timezone':None,'installed_capacity':None},
        'provenance':{'dataset_filename_sha256':hashlib.sha256(source_bytes).hexdigest() if source_bytes is not None else None,
                      'dataset_fingerprint_basis':'raw uploaded workbook bytes; none means not provided',
                      'source_url':'https://zenodo.org/records/19245713',
                      'generated_utc':datetime.now(timezone.utc).isoformat(),
                      'source_code_commit':_code_sha(),
                      'python':sys.version.split()[0],
                      'platform':platform.platform(),
                      'packages':_packages(),
                      'seed':SEED,'window_hours':WINDOW,
                      'splits':{'train_pct':70,'validation_pct':15,'test_pct':15},
                      'model_parameters':{k:MODEL_PARAMS[k] for k in ('random_forest','xgboost','lstm') if k in predictions},
                      'training_seconds':timing,'training_metadata':details},
        'predictions':test_rows,
        'warnings':[
          'Original PV measurement units are unresolved (source says W or Wh); metrics are NOT kW.',
          'No real calendar date, source timezone, rated capacity or site coordinates are assumed.',
          'Target-hour observed irradiance defines generating-hour REPORTING only, not prediction inputs.',
          'The 48 immediately prior power measurements are assumed available before the one-hour-ahead issue time.',
          'This is a single time holdout; repeated rolling windows and another measured PV site are required for stronger generalization.',
          'Physical pvlib baseline unavailable without plant ratings and meteorological predictions issued before the target hour.',
          'The LSTM, RF, and XGBoost models have fixed initial hyperparameters; no test-set tuning was performed.',
        ]
    }
    return result
