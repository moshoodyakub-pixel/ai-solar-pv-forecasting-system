from io import BytesIO
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)


def workbook(n=300):
    # Synthetic *unit-test fixture* matching the source schema; not academic findings.
    i=np.arange(n)
    h=i%24+1
    p=90*np.maximum(0,np.sin(np.pi*(h-7)/12))
    labels=['Day','Cosine of Day','Hour','Cosine of Hour','Air Temperature','Dewpoint',
        'Wind Speed','Air Pressure','Weather Condition','Solar Radiation',
        'PV-1 Cosine Value of the Solar Incidence Angle','PV-1 Power',
        'PV-2 Cosine Value of the Solar Incidence Angle','PV-2 Power',
        'PV-3 Cosine Value of the Solar Incidence Angle','PV-3 Power',
        'PV-4 Cosine Value of the Solar Incidence Angle','PV-4 Power',
        'PV-5 Cosine Value of the Solar Incidence Angle','PV-5 Power','Total PV Power']
    rows=[]
    for day,hr,pow in zip(i//24+1,h,p):
        rows.append([day,0,hr,0,25,10,4,900,1,pow*10,0,pow/5,0,pow/5,0,pow/5,0,pow/5,0,pow/5,pow])
    output=BytesIO()
    with pd.ExcelWriter(output,engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer,sheet_name='DATA',header=False,index=False)
        pd.DataFrame([list(range(1,22)),labels]).to_excel(writer,sheet_name='DATA DESCRIPTION',header=False,index=False)
    return output.getvalue()


def test_workbook_api_exports_every_prediction():
    r=client.post('/api/experiment2',
        files={'file':('PV_Data.xlsx',workbook())},
        data={'include_lstm':'false','include_xgboost':'false'})
    assert r.status_code==200,r.text[:1000]
    result=r.json()
    assert result['data_quality']['test_rows']==len(result['predictions'])
    assert result['provenance']['dataset_filename_sha256'] is not None
    assert result['schema_version']=='2.0'


def test_reject_invalid_workbook():
    r=client.post('/api/experiment2',files={'file':('invalid.xlsx',b'not-an-excel-file')})
    assert r.status_code==422
