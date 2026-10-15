from fastapi.testclient import TestClient
from backend.main import app
client=TestClient(app)

def test_root_and_health():
    assert client.get('/').status_code==200
    assert client.get('/api/health').json()['status']=='ok'

def test_csv_preview_api():
    res=client.post('/api/preview',files={'file':('pv.csv',b'timestamp,power_kw\n2025-01-01 00:00:00,0\n2025-01-01 01:00:00,1','text/csv')},data={'header_row':'0'})
    assert res.status_code==200
    assert res.json()['suggested_power']=='power_kw'
