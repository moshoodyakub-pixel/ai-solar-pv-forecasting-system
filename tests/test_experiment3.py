"""EXP-003 safeguards: fold boundaries, no holdout peeking, metric recomputation."""
import numpy as np
import pandas as pd
import pytest
from backend.forecasting.experiment3 import make_folds,run_experiment3
from backend.forecasting.ingestion import DataError

def fixture(n=3000):
    x=np.arange(n)
    hour=(x%24)+1
    p=100*np.maximum(0,np.sin(np.pi*(hour-7)/12))+(x%11)*0.2
    return pd.DataFrame({'Day':x//24+1,'Hour':hour,
        'Solar Radiation':p*8,'Total PV Power':p})

def test_disjoint_expanding_folds_and_untouched_test_boundary():
    dev,folds=make_folds(7032,4,336)
    assert dev==5977 and len(folds)==4
    assert folds[0]['training_end_exclusive']==4633
    assert folds[-1]['validation_end_exclusive']==dev
    for a,b in zip(folds,folds[1:]):
        assert a['validation_end_exclusive']==b['validation_start']
        assert b['training_end_exclusive']==b['validation_start']

def test_all_validation_predictions_reproduce_metrics():
    report=run_experiment3(fixture(),include_xgboost=False,include_lstm=False,
        fold_count=3,fold_hours=96,source_bytes=b'test-fixture')
    records=report['predictions']
    assert len(records)==288
    assert len(set(r['source_row_1based'] for r in records))==len(records)
    assert records[-1]['source_row_1based']<report['data_quality']['reserved_15pct_start_source_row_1based']
    for model,score in report['model_scores'].items():
        a=np.array([r['actual'] for r in records])
        p=np.array([r['forecasts'][model] for r in records])
        assert abs(np.mean(np.abs(p-a))-score['pooled_validation']['mae'])<.00005

def test_changing_reserved_labels_cannot_change_fold_scores():
    orig=fixture()
    altered=orig.copy()
    start=48+int(.85*(len(orig)-48))
    altered.loc[start:,'Total PV Power']=99999.
    a=run_experiment3(orig,include_xgboost=False,include_lstm=False,fold_count=2,fold_hours=48)
    b=run_experiment3(altered,include_xgboost=False,include_lstm=False,fold_count=2,fold_hours=48)
    for rowa,rowb in zip(a['predictions'],b['predictions']):
        assert rowa['actual']==rowb['actual']
        for model in rowa['forecasts']:
            assert np.isclose(rowa['forecasts'][model],rowb['forecasts'][model],atol=1e-8)
    for model in a['model_scores']:
        assert np.isclose(a['model_scores'][model]['pooled_validation']['mae'],
             b['model_scores'][model]['pooled_validation']['mae'],atol=1e-8)

def test_observed_target_hour_irradiance_not_a_feature():
    f=fixture()
    a=run_experiment3(f,include_xgboost=False,include_lstm=False,fold_count=2,fold_hours=48)
    f['Solar Radiation']=0
    b=run_experiment3(f,include_xgboost=False,include_lstm=False,fold_count=2,fold_hours=48)
    for rowa,rowb in zip(a['predictions'],b['predictions']):
        for name in rowa['forecasts']:
            assert np.isclose(rowa['forecasts'][name],rowb['forecasts'][name],atol=1e-8)
    assert a['model_scores']['random_forest']['generating_hours_ex_post']['sample_count']>0
    assert b['model_scores']['random_forest']['generating_hours_ex_post']['sample_count']==0

def test_bad_fold_parameters_rejected():
    with pytest.raises(DataError,match='2–8'):
        make_folds(7032,1,336)
    with pytest.raises(DataError,match='Not enough'):
        make_folds(400,4,300)
