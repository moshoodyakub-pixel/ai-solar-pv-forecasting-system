"""One-hour-ahead forecasting evaluated with strictly chronological target periods."""
from __future__ import annotations
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from .ingestion import DataError

FEATURES = ['lag_1','lag_2','lag_24','lag_48','roll_24','sin_hour','cos_hour','sin_year','cos_year']


def as_utc(values, tz_name: str) -> pd.Series:
    try:
        zone=ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DataError(f'Unknown time zone: {tz_name}') from exc
    parsed=pd.to_datetime(values,errors='coerce')
    try:
        if parsed.dt.tz is None:
            parsed=parsed.dt.tz_localize(zone,ambiguous='NaT',nonexistent='NaT')
        return parsed.dt.tz_convert('UTC')
    except (TypeError,AttributeError,ValueError) as exc:
        raise DataError('Timestamp column could not be interpreted consistently. Use ISO timestamps or Excel dates.') from exc


def physical_pvwatts_like(poa: pd.Series, temp_air: pd.Series, dc_capacity: float, ac_capacity:float|None):
    """Simplified engineering benchmark, NOT site-calibrated pvlib simulation.
    Uses FORECAST POA and air temperature for the target hour only. 20 C at 800 W/m2
    cell-temperature rise, -0.4% /C power coefficient and 96% inverter factor.
    """
    poa=np.maximum(0.0,poa.to_numpy(dtype=float))
    temp=temp_air.to_numpy(dtype=float)
    cell_temp=temp+20.0*poa/800.0
    p_dc=np.maximum(0.0,dc_capacity*(poa/1000.0)*(1-0.004*(cell_temp-25.0)))
    p_ac=p_dc*0.96
    if ac_capacity:
        p_ac=np.minimum(p_ac,ac_capacity)
    return p_ac


def metrics(y_true, y_pred, capacity_kw:float|None):
    yt=np.asarray(y_true,dtype=float)
    yp=np.asarray(y_pred,dtype=float)
    if not len(yt):
        raise DataError('Insufficient test samples for evaluation.')
    rmse=float(np.sqrt(mean_squared_error(yt,yp)))
    return {'mae_kw':round(float(mean_absolute_error(yt,yp)),4),
            'rmse_kw':round(rmse,4),
            'nrmse_pct_of_capacity':round(100*rmse/capacity_kw,3) if capacity_kw else None,
            'r2':round(float(r2_score(yt,yp)),4) if len(yt)>=2 and np.std(yt)>0 else None,
            'n':len(yt)}


def evaluate(frame:pd.DataFrame, timestamp_column:str, power_column:str, *,
             timezone:str='UTC',capacity_kw:float|None=None,
             poa_forecast_column:str|None=None,temp_forecast_column:str|None=None,
             ac_capacity_kw:float|None=None)->dict:
    for col in [timestamp_column,power_column,poa_forecast_column,temp_forecast_column]:
        if col is not None and col not in frame.columns:
            raise DataError(f'Column does not exist: {col}')
    if capacity_kw is not None and capacity_kw<=0:
        raise DataError('Rated DC capacity must be positive.')
    if ac_capacity_kw is not None and ac_capacity_kw<=0:
        raise DataError('Rated AC capacity must be positive.')
    if (poa_forecast_column is None) != (temp_forecast_column is None):
        raise DataError('Physical baseline requires both target-hour forecast POA and temperature columns.')
    ts=as_utc(frame[timestamp_column],timezone)
    kw=pd.to_numeric(frame[power_column],errors='coerce')
    valid=ts.notna() & kw.notna()
    if valid.sum()<160:
        raise DataError('At least 160 valid, hourly timestamp / power records are required.')
    if (kw[valid]<0).any():
        raise DataError('Negative measured PV power found; correct or explain the measurements first.')
    work=pd.DataFrame({'time':ts[valid], 'power_kw':kw[valid].to_numpy(dtype=float)},index=frame.index[valid])
    if work['time'].duplicated().any():
        raise DataError('Duplicate timestamps found. Resolve duplicates before modelling.')
    if (work['power_kw']<0).any():
        raise DataError('Negative PV measurements found.')
    if capacity_kw and (work['power_kw']>capacity_kw*1.15).any():
        raise DataError('Measured power exceeds rated DC capacity by >15%; check units or installed capacity.')
    work=work.sort_values('time').set_index('time')
    if len(work)>1 and (work.index.to_series().diff().dropna().dt.total_seconds()<3600).any():
        raise DataError('The file contains sub-hourly observations; resample explicitly to hourly first.')
    # Preserve the complete hourly timeline, including measurement outages.
    full=pd.date_range(work.index.min(),work.index.max(),freq='h',tz='UTC')
    if len(full)>len(work)*2:
        raise DataError('Data are too irregular or sub-hourly for the hourly model. Resample explicitly first.')
    work=work.reindex(full)
    missing_hours=int(work.power_kw.isna().sum())
    work['lag_1']=work.power_kw.shift(1)
    work['lag_2']=work.power_kw.shift(2)
    work['lag_24']=work.power_kw.shift(24)
    work['lag_48']=work.power_kw.shift(48)
    work['roll_24']=work.power_kw.shift(1).rolling(24,min_periods=24).mean()
    # Timestamp features at TARGET hour are safe: time of next hour is known at issue.
    local=work.index.tz_convert(timezone)
    hour=local.hour.to_numpy()
    year_day=local.dayofyear.to_numpy()
    work['sin_hour']=np.sin(2*np.pi*hour/24)
    work['cos_hour']=np.cos(2*np.pi*hour/24)
    work['sin_year']=np.sin(2*np.pi*year_day/365.25)
    work['cos_year']=np.cos(2*np.pi*year_day/365.25)
    future_cols=[]
    if poa_forecast_column:
        extra=frame.loc[valid,[poa_forecast_column,temp_forecast_column]].apply(pd.to_numeric,errors='coerce')
        extras=pd.DataFrame({'poa_fc':extra[poa_forecast_column].to_numpy(),
                             'temp_fc':extra[temp_forecast_column].to_numpy()},index=ts[valid])
        extras=extras.sort_index().reindex(full)
        work[['poa_fc','temp_fc']]=extras[['poa_fc','temp_fc']]
        future_cols=['poa_fc','temp_fc']
    model_features=FEATURES+future_cols
    ready=work.dropna(subset=['power_kw']+FEATURES)
    if len(ready)<100:
        raise DataError('Too few complete hourly target/lag records after preprocessing.')
    # For forecast-weather experiments, do not discard baseline rows. Physical and weather
    # models use only rows where these measurements/predictions are available.
    n=len(ready)
    i=int(n*0.7);j=int(n*0.85)
    if min(i,j-i,n-j)<20:
        raise DataError('Insufficient data after splitting into train/validation/test windows.')
    train,val,test=ready.iloc[:i],ready.iloc[i:j],ready.iloc[j:]
    x_cols=FEATURES # Extend only when TRUE target-time forecasts have complete coverage.
    use_weather=bool(future_cols) and ready[future_cols].notna().all().all()
    if use_weather:
        x_cols=model_features
    rf=RandomForestRegressor(n_estimators=120,random_state=42,min_samples_leaf=3,n_jobs=-1)
    rf.fit(train[x_cols],train.power_kw)
    candidates={
        'persistence_1h': {'validation':val.lag_1.to_numpy(), 'test':test.lag_1.to_numpy()},
        'persistence_24h': {'validation':val.lag_24.to_numpy(), 'test':test.lag_24.to_numpy()},
        'random_forest': {'validation':rf.predict(val[x_cols]), 'test':rf.predict(test[x_cols])},
    }
    if use_weather and capacity_kw:
        candidates['physical_pvwatts_style']={
            'validation':physical_pvwatts_like(val.poa_fc,val.temp_fc,capacity_kw,ac_capacity_kw),
            'test':physical_pvwatts_like(test.poa_fc,test.temp_fc,capacity_kw,ac_capacity_kw)}
    val_errors={k:mean_absolute_error(val.power_kw, v['validation']) for k,v in candidates.items()}
    chosen=min(val_errors,key=val_errors.get)
    scores={k:{'validation':metrics(val.power_kw,v['validation'],capacity_kw),
               'test':metrics(test.power_kw,v['test'],capacity_kw)} for k,v in candidates.items()}
    comparison=sorted(scores.keys(),key=lambda k:val_errors[k])
    tail=min(240,len(test))
    result_rows=[]
    for pos in range(len(test)-tail,len(test)):
        t=test.index[pos]
        result_rows.append({'timestamp_utc':t.isoformat(),
          'actual_kw':round(float(test.power_kw.iloc[pos]),4),
          **{k+'_kw':round(float(candidates[k]['test'][pos]),4) for k in candidates}})
    warnings=['1-hour rolling-origin retrospective test; the previous hour actual must be available at issuance.',
              'Evaluation uses held-out chronological time periods; no random shuffling.',
              'Physical-model forecast is disabled without BOTH target-time forecast POA/temperature and plant capacity.'] if not (use_weather and capacity_kw) else [
              'Forecast POA and temperature must be archived AS-ISSUED weather forecasts, not future observations. Verify provenance.',
              'The simplified physical baseline assumes POA incidence, cell temperature rise and inverter loss; it is not calibrated.']
    if poa_forecast_column and not use_weather:
        warnings.append('Incomplete forecast-weather columns: weather variables excluded from Random Forest and physical baseline.')
    if missing_hours:
        warnings.append(f'{missing_hours} missing hourly values remained gaps; measured power was not imputed.')
    return {'status':'evaluated','target':'measured AC PV power (kW)',
      'forecast_horizon':'1 hour ahead','model_selection':'minimum validation MAE',
      'selected_model':chosen,'ranking_validation':comparison,
      'scores':scores,'data_quality':{'input_valid_records':int(valid.sum()),'hourly_gaps':missing_hours,
         'eligible_rows':n,'training_rows':len(train),'validation_rows':len(val),'test_rows':len(test),
         'first_utc':ready.index[0].isoformat(),'last_utc':ready.index[-1].isoformat(),
         'test_start_utc':test.index[0].isoformat(),
         'used_forecast_weather':use_weather,
         'capacity_kw_dc':capacity_kw,'capacity_kw_ac':ac_capacity_kw},
      'sample_predictions':result_rows,'warnings':warnings}
