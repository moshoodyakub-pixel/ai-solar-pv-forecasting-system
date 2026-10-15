from fastapi.testclient import TestClient
from backend.main import app
from tests.test_experiment2_api import workbook

client=TestClient(app)

def test_experiment3_api_predicts_without_scoring_test():
    r=client.post('/api/experiment3',
        files={'file':('PV_Data.xlsx',workbook(n=900))},
        data={'include_xgboost':'false','include_lstm':'false',
              'fold_count':'2','fold_days':'2'})
    assert r.status_code==200,r.text[:500]
    result=r.json()
    assert result['experiment_id']=='EXP-003'
    assert result['data_quality']['validation_predictions']==96
    assert result['data_quality']['last_evaluated_source_row_1based'] < result['data_quality']['reserved_15pct_start_source_row_1based']

def test_reject_zero_fold_days():
    r=client.post('/api/experiment3',files={'file':('PV_Data.xlsx',workbook(n=900))},
        data={'fold_days':'0'})
    assert r.status_code==422
