import io
import json
import zipfile
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from test_processing import archive
from test_loaded_source import loaded


def test_reconstruction_exports_queued_parts_from_multiple_imports_with_identical_csv_names(tmp_path,monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS',str(tmp_path))
    c=TestClient(create_app())
    first=c.post('/api/reconstruction/import',content=archive(range(5),[100]*5)).json()['datasetId']
    second=c.post('/api/reconstruction/import',content=archive(range(5),[300]*5)).json()['datasetId']
    assert c.post('/api/reconstruction/propose',json={'datasetId':first,'sourceId':'a.csv'}).status_code==200
    parts=[{'datasetId':dataset,'sourceId':'a.csv','start':0,'end':5,
            'blocks':[{'start':0,'end':5,'power':target}]} for dataset,target in [(first,110),(second,310)]]
    r=c.post('/api/reconstruction/export',json={'segments':parts})
    assert r.status_code==200,r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        manifest=json.loads(z.read('manifest.json'))
        entries=manifest['segments']
        assert len(entries)==2
        frames=[pd.read_csv(z.open(e['csv_file'])) for e in entries]
        assert [f.power_w.tolist() for f in frames]==[[100]*5,[300]*5]
        assert [f.power_target_w.tolist() for f in frames]==[[110]*5,[310]*5]
        assert {e['source_dataset_id'] for e in entries}=={first,second}
        assert all(e['source_csv_file']=='a.csv' for e in entries)
    assert c.post('/api/reconstruction/import',content=r.content).status_code==200
    assert c.post('/api/processing/import',content=r.content).status_code==200


def test_processing_can_return_to_and_export_previous_results_after_new_import(tmp_path,monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS',str(tmp_path))
    c=TestClient(create_app())
    first=c.post('/api/processing/import',content=archive(range(5),[100]*5)).json()['datasetId']
    request={'datasetId':first,'selected':['a.csv'],'windowSeconds':3}
    before=c.post('/api/processing/preview',json=request).json()
    c.post('/api/processing/import',content=archive(range(5),[300]*5))
    again=c.post('/api/processing/preview',json=request)
    assert again.status_code==200,again.text
    assert again.json()==before
    exported=c.post('/api/processing/export',json=request)
    assert exported.status_code==200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        entry=json.loads(z.read('manifest.json'))['segments'][0]
        assert pd.read_csv(z.open(entry['csv_file'])).power_w.tolist()==[100]*5


@pytest.mark.parametrize('page',['processing','reconstruction'])
def test_loading_another_fit_selection_keeps_previous_snapshot(tmp_path,page):
    c,source=loaded(tmp_path)
    request={'datasetId':source['datasetId'],'segments':[{'activityId':'ride.fit','firstLap':1,'lastLap':1}]}
    first=c.post(f'/api/{page}/from-loaded',json=request).json()
    assert c.post(f'/api/{page}/from-loaded',json=request).status_code==200
    if page=='processing':
        response=c.post('/api/processing/preview',json={'datasetId':first['datasetId'],'selected':[first['segments'][0]['id']]})
        assert response.status_code==200,response.text
        points=response.json()['segments'][0]['points']
    else:
        response=c.post('/api/reconstruction/propose',json={'datasetId':first['datasetId'],'sourceId':first['segments'][0]['id']})
        assert response.status_code==200,response.text
        points=response.json()['points']
    assert [p['power_w'] for p in points]==[200,250]
