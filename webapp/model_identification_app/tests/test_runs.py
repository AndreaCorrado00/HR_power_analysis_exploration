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
        r = c.post('/api/runs',json={'dataset_id':ds['id'],'model_id':'p1d','signal':'raw','config':{'n_starts':2,'max_nfev':500}})
        assert r.status_code == 200, r.text
        key = r.json()['id']
        run = wait_run(c,key)
        assert run['status'] == 'completed'
        result = c.get(f'/api/runs/{key}/results').json()
        assert all(r['identification_valid'] and r['optimizer_success'] for r in result)
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


def test_out_of_domain_solution_is_persisted_as_failed(tmp_path, monkeypatch):
    from webapp.model_identification_app.backend.models import p1d
    original = p1d.least_squares
    def incompatible(*args, **kwargs):
        opt = original(*args, **kwargs)
        opt.x[1] = 12.  # Segment ends at 11 s.
        return opt
    monkeypatch.setattr(p1d, 'least_squares', incompatible)
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload', data={'name':'Guard'},
                    files=[('files', ('a.csv', csv_bytes(0), 'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split", json={'percentages':[100,0,0],'seed':42,'unit':'segment'})
        run = c.post('/api/runs', json={'dataset_id':ds['id'],'model_id':'p1d','signal':'raw','config':{'n_starts':2}}).json()
        complete = wait_run(c, run['id'])
        assert complete['status'] == 'completed_with_errors'
        assert complete['progress']['failed'] == 1
        result = c.get(f"/api/runs/{run['id']}/results").json()[0]
        assert result['status'] == 'failed'
        assert result['optimizer_success'] is True
        assert result['identification_valid'] is False
        assert 'delay_outside_segment' in result['error']
        assert result['effective_bounds']['upper'][1] == 11


def test_structure_manifest_and_run_local_exports(tmp_path):
    import io
    import zipfile
    data = ('activity_id,elapsed_seconds,power_w,heart_rate_bpm\n' +
            ''.join(f'a,{t},{100 if t<0 else 200},{120+.8*max(t-2,0)}\n' for t in range(-10,21))).encode()
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload', data={'name':'Pre-window'}, files=[('files',('a.csv',data,'text/csv'))]).json()
        assert ds['segments'][0]['duration_seconds'] == 20
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        r = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{'model_structure':'short_transient','use_pre_window':True,'n_starts':2}})
        assert r.status_code == 200, r.text
        run = wait_run(c,r.json()['id'])
        assert run['status'] == 'completed'
        assert run['model_structure'] == 'short_transient'
        assert run['pre_window_seconds'] == 10
        assert run['P0_method'] == 'pre_window_mean'
        assert run['pre_window_inventory'][0]['available']
        assert run['diagnostic_schema']['rho']['applicable'] is False
        key = run['id']
        tables = c.post(f'/api/runs/{key}/exports/tables')
        assert tables.status_code == 200, tables.text
        with zipfile.ZipFile(io.BytesIO(tables.content)) as z:
            assert {'fits.csv','parameters.csv','multistart.csv','series.csv','pre_window.csv','manifest.json'} <= set(z.namelist())
            assert 'rho' in z.read('fits.csv').decode()
            assert 'gamma' in z.read('parameters.csv').decode()
        pdf = c.post(f'/api/runs/{key}/exports/pdf')
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b'%PDF')
        assert (tmp_path/'runs'/key/'exports'/'report.pdf').exists()
        replay = c.post(f'/api/runs/{key}/replay').json()
        assert replay['config']['use_pre_window'] is True
        wait_run(c,replay['id'])


def test_absent_window_recorded_even_when_requested(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload',data={'name':'Missing'},files=[('files',('a.csv',csv_bytes(1),'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        run = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{'use_pre_window':True,'n_starts':2}}).json()
        run = wait_run(c,run['id'])
        assert not run['pre_window_inventory'][0]['available']
        result = c.get(f"/api/runs/{run['id']}/results").json()[0]
        assert result['status'] == 'failed'
        assert result['failure_reasons'] == ['pre_window_absent']
        assert result['pre_window']['available'] is False
        assert c.post(f"/api/runs/{run['id']}/exports/pdf").status_code == 200


def test_new_runs_cannot_enable_legacy_protocol(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload',data={'name':'Legacy guard'},files=[('files',('a.csv',csv_bytes(1),'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        response = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{'initialization_protocol':'legacy_v1'}})
        assert response.status_code == 400


def test_historical_replay_preserves_initialization_and_delay_lower(tmp_path):
    data = ('activity_id,elapsed_seconds,power_w,heart_rate_bpm\n' +
            ''.join(f'a,{t},{100 if t<0 else 200},{120+.8*max(t-2,0)}\n' for t in range(-10,21))).encode()
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload',data={'name':'Legacy'},files=[('files',('a.csv',data,'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        run = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{'n_starts':2}}).json()
        run = wait_run(c,run['id'])
        run['schema_version'] = 1
        for k in ('model_structure','use_pre_window','initialization_protocol','pre_window_seconds','search_strategy'): run['config'].pop(k,None)
        run['config']['lower'][1] = 1.
        run['config']['upper'][1] = 20.
        c.app.state.runs.save(run)
        response = c.post(f"/api/runs/{run['id']}/replay")
        assert response.status_code == 200, response.text
        replay = wait_run(c,response.json()['id'])
        result = c.get(f"/api/runs/{replay['id']}/results").json()[0]
        assert result['uncertainty']['N'] == 31
        assert result['pre_window']['included_in_objective'] is True
        assert result['initial_conditions']['P0'] == 100
        assert replay['config']['initialization_protocol'] == 'legacy_v1'
        assert result['effective_bounds']['lower'][1] == 1.
        assert replay['config']['search_strategy'] == 'multistart'


def test_new_run_records_profile_search_and_replays_its_settings(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload',data={'name':'Search'},files=[('files',('a.csv',csv_bytes(1),'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        run = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{'n_starts':2}}).json()
        run = wait_run(c,run['id'])
        assert run['optimizer_settings']['search_strategy'] == 'profile_multistart'
        assert run['optimizer_settings']['grid_delay_points'] == 301
        assert wait_run(c,c.post(f"/api/runs/{run['id']}/replay").json()['id'])['config'] == run['config']
        run['schema_version'] = 2
        run['config'].pop('search_strategy')
        c.app.state.runs.save(run)
        historical = wait_run(c,c.post(f"/api/runs/{run['id']}/replay").json()['id'])
        assert historical['config']['search_strategy'] == 'multistart'


def test_estimated_equilibrium_manifest_results_and_exports(tmp_path):
    import io
    import zipfile
    with TestClient(create_app(tmp_path)) as c:
        ds = c.post('/api/datasets/upload',data={'name':'Initial state'},files=[('files',('a.csv',csv_bytes(1),'text/csv'))]).json()
        c.post(f"/api/datasets/{ds['id']}/split",json={'percentages':[100,0,0],'seed':42,'unit':'activity'})
        response = c.post('/api/runs',json={'dataset_id':ds['id'],'config':{
            'n_starts':2,'initialization_mode':'estimated_equilibrium','equilibrium_bounds':[0.,250.]}})
        assert response.status_code == 200, response.text
        run = wait_run(c,response.json()['id'])
        assert run['status'] == 'completed'
        assert run['initialization_mode'] == 'estimated_equilibrium'
        assert run['HR0_method'] == 'first_segment_sample'
        assert run['B_method'] == 'estimated'
        assert run['parameter_bounds']['keys'] == ['K','L','tau','B']
        assert run['parameter_bounds']['upper'][-1] == 250
        assert run['model']['parameters'][-1] == {'key':'B','unit':'bpm'}
        result = c.get(f"/api/runs/{run['id']}/results").json()[0]
        assert 'B' in result['parameters']
        exported = c.post(f"/api/runs/{run['id']}/exports/tables")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            assert ',B,' in z.read('parameters.csv').decode()
            assert 'initialization_mode' in z.read('fits.csv').decode()
        assert c.post(f"/api/runs/{run['id']}/exports/pdf").content.startswith(b'%PDF')
