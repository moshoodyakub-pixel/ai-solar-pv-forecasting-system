import numpy as np
import pandas as pd
import pytest
from backend.forecasting.orientation import evaluate_orientation, is_orientation_dataset
from backend.forecasting.ingestion import DataError


def example(n=500):
    i=np.arange(n)
    hr=(i%24)+1
    power=90*np.maximum(0,np.sin(np.pi*(hr-6)/12))
    frame=pd.DataFrame({'Day':(i//24)+1,'Hour':hr,'Solar Radiation':power*10,
        'Total PV Power':power})
    for x in range(1,6): frame[f'PV-{x} Power']=power/5
    return frame


def test_validation_never_claims_kw_or_invents_year():
    frame=example()
    assert is_orientation_dataset(frame)
    result=evaluate_orientation(frame)
    assert result['unit']=='original_dataset_unit_unresolved_W_or_Wh'
    assert result['data_quality']['calendar_year'] is None
    assert result['data_quality']['timezone'] is None
    assert 'test_generating_hours' in result['scores']['random_forest']
    assert result['sample_predictions'][-1]['day']==21


def test_reject_nonsequential_record():
    frame=example().drop(index=10)
    with pytest.raises(DataError,match='Missing, duplicated or out-of-order'):
        evaluate_orientation(frame)


def test_reject_unavailable_target():
    with pytest.raises(DataError,match='Select Total PV Power'):
        evaluate_orientation(example(), 'Air Temperature')
