import numpy as np
import pandas as pd
import pytest
from backend.forecasting.experiment2 import _feature_matrix, run_experiment
from backend.forecasting.ingestion import DataError


def make_frame(n=300):
    i=np.arange(n)
    hour=i%24+1
    v=50*np.maximum(0,np.sin(np.pi*(hour-7)/12))+(i%5)*.05
    return pd.DataFrame({'Day':i//24+1,'Hour':hour,'Solar Radiation':v*10,
                         'Total PV Power':v})


def test_features_have_no_target_hour_power():
    f=make_frame(400)
    idx,hist,clock=_feature_matrix(f.Day.to_numpy(),f.Hour.to_numpy(),f['Total PV Power'].to_numpy())
    assert len(idx)==352
    assert hist[0,0]==f['Total PV Power'].iloc[0]
    assert hist[0,-1]==f['Total PV Power'].iloc[47]
    assert idx[0]==48
    assert clock.shape==(352,4)


def test_fair_split_and_full_export_and_manifest():
    f=make_frame(400)
    r=run_experiment(f,source_bytes=b'source-fingerprint',include_lstm=False,include_xgboost=False)
    assert r['status']=='evaluated'
    assert len(r['predictions'])==r['data_quality']['test_rows']
    assert r['unit']=='original_dataset_unit_unresolved_W_or_Wh'
    assert r['provenance']['dataset_filename_sha256'] is not None
    assert r['data_quality']['calendar_year'] is None
    assert r['selected_model'] in r['scores']
    for model in r['scores']:
        y=np.array([item['actual'] for item in r['predictions']])
        yp=np.array([item['forecasts'][model] for item in r['predictions']])
        assert abs(np.mean(np.abs(yp-y))-r['scores'][model]['test']['mae'])<0.0001


def test_no_invented_missing_hour():
    f=make_frame(400).drop(index=77).reset_index(drop=True)
    with pytest.raises(DataError,match='complete consecutive'):
        run_experiment(f,include_xgboost=False,include_lstm=False)


def test_reject_target_hour_alias():
    with pytest.raises(DataError,match='Select Total PV Power'):
        run_experiment(make_frame(400),target='Solar Radiation',include_xgboost=False,include_lstm=False)


def test_xgb_and_lstm_same_index_and_sample_count():
    pytest.importorskip('torch')
    pytest.importorskip('xgboost')
    r=run_experiment(make_frame(290),include_xgboost=True,include_lstm=True)
    assert set(r['scores'])=={'persistence_1h','persistence_24h','random_forest','xgboost','lstm'}
    for model in r['scores']:
        assert r['scores'][model]['test']['sample_count']==r['data_quality']['test_rows']
        assert np.isfinite([v['forecasts'][model] for v in r['predictions']]).all()
    assert r['provenance']['training_metadata']['lstm']['best_epoch']>=1
