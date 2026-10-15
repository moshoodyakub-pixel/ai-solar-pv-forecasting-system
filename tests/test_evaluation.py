import numpy as np
import pandas as pd
import pytest
from backend.forecasting.evaluation import evaluate,metrics,physical_pvwatts_like
from backend.forecasting.ingestion import DataError


def dataset(n=500):
    t=pd.date_range('2025-01-01',periods=n,freq='h',tz='UTC')
    hours=t.hour.to_numpy()
    power=100*np.maximum(0,np.sin(np.pi*(hours-6)/12))
    return pd.DataFrame({'timestamp':t.astype(str),'power_kw':power})


def test_metrics_exact_match():
    m=metrics([0,10,20],[0,10,20],100)
    assert m['mae_kw']==0
    assert m['rmse_kw']==0
    assert m['nrmse_pct_of_capacity']==0
    assert m['r2']==1


def test_physical_power_night_and_capacity_ceiling():
    value=physical_pvwatts_like(pd.Series([0,1200]),pd.Series([25,25]),100,90)
    assert value[0]==0
    assert 0<value[1]<=90


def test_evaluation_chronological_and_truthful():
    r=evaluate(dataset(),'timestamp','power_kw',capacity_kw=100)
    q=r['data_quality']
    assert r['forecast_horizon']=='1 hour ahead'
    assert q['training_rows']+q['validation_rows']+q['test_rows']==q['eligible_rows']
    assert r['selected_model'] in {'random_forest','persistence_1h','persistence_24h'}
    assert 'physical_pvwatts_style' not in r['scores']
    assert r['sample_predictions'][-1]['timestamp_utc']==q['last_utc']


def test_reject_duplicate_times():
    df=dataset()
    df.loc[10,'timestamp']=df.loc[9,'timestamp']
    with pytest.raises(DataError,match='Duplicate timestamps'):
        evaluate(df,'timestamp','power_kw')


def test_reject_subhourly_input():
    df=dataset().copy()
    df['timestamp']=pd.date_range('2025-01-01',periods=len(df),freq='15min',tz='UTC').astype(str)
    with pytest.raises(DataError,match='sub-hourly'):
        evaluate(df,'timestamp','power_kw')


def test_forecast_physical_baseline_only_when_supplied():
    df=dataset()
    df['poa_fc']=np.maximum(0,np.sin(np.pi*(pd.to_datetime(df.timestamp).dt.hour-6)/12))*950
    df['temperature_fc']=25.0
    r=evaluate(df,'timestamp','power_kw',capacity_kw=100,
       poa_forecast_column='poa_fc',temp_forecast_column='temperature_fc')
    assert 'physical_pvwatts_style' in r['scores']
    assert r['data_quality']['used_forecast_weather']


def test_no_fake_timestamps():
    df=dataset().drop(columns=['timestamp'])
    with pytest.raises(DataError,match='does not exist'):
        evaluate(df,'timestamp','power_kw')
