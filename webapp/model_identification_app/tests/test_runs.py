import json
import time

from fastapi.testclient import TestClient
from webapp.model_identification_app.backend.app import create_app


def csv_bytes(i):
    return ('activity_id,elapsed_seconds,power_w,heart_rate_bpm\n'+
            ''.join(f'a{i},{t},{100 if t<4 else 200},{120 if t<4 else 130}\n' for t in range(12))).encode()


def wait_run(client, key):
    for _ in range(500):
        run = client.get('/api/runs/'+key).json()
        snapshot = client.get('/api/runs/'+key+'/manifest')
        assert snapshot.status_code == 200
        assert snapshot.json()['id'] == key
        if run['status'] not in ('queued','running'): return run
        time.sleep(.02)
    raise AssertionError('run timeout')


def test_train_only_persistence_replay_and_manifest_archive(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        r = c.post('/api/datasets/upload', data={'name':'Test'}, files=[('files',(f'{i}.csv',csv_bytes(i),'text/csv')) for i in range(10)])
        assert r.status_code == 200, r.text
        ds = r.json()
        split = c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[70,10,20],'seed':42,'unit':'segment'}).json()
        assert len(split['assignments']['train']) == 7
        r = c.post('/api/runs',json={'dataset_id':ds['id'],'model_id':'p1d','signal':'raw','config':{'n_starts':2,'max_nfev':10}})
        assert r.status_code == 200, r.text
        key = r.json()['id']
        run = wait_run(c,key)
        assert run['status'] == 'completed'
        result = c.get(f'/api/runs/{key}/results').json()
        assert {r['segment_id'] for r in result} == set(split['assignments']['train'])
        assert (tmp_path/'runs'/run['manifest_filename']).exists()
        c.patch(f"/api/datasets/{ds['id']}",json={'name':'Renamed'})
        assert c.get('/api/runs/'+key).json()['dataset']['name'] == 'Test'
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/runs/'+key).json()['status']=='completed'
        replay = c.post(f'/api/runs/{key}/replay').json()
        assert replay['split']==run['split']
        wait_run(c,replay['id'])
        assert c.delete('/api/runs/'+key).status_code==200
        assert c.get('/api/runs/'+key).status_code==404
        archived = list((tmp_path/'archived_manifests').glob('*.json'))
        assert len(archived)==1
        assert json.loads(archived[0].read_text(encoding='utf-8'))['id']==key
        assert not (tmp_path/'runs'/key).exists()
        assert c.get('/api/datasets').json()[0]['name']=='Renamed'


def test_restart_marks_incomplete_manifest_interrupted(tmp_path):
    from webapp.model_identification_app.backend.storage import Store
    s=Store(tmp_path)
    manifest={'id':'abc','status':'running','manifest_filename':'incomplete.json'}
    s.write_path(tmp_path/'runs'/'incomplete.json',manifest)
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/runs/abc').json()['status']=='interrupted'
