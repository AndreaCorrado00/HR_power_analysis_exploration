"""Read-only viewer contracts, including fixed training standardization."""
import importlib.util
import json
from pathlib import Path
import threading
import urllib.request
import urllib.error
import uuid

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT/'webapp/ar_validation_viewer/server.py'
    assert path.exists(), 'Viewer server not yet implemented'
    spec = importlib.util.spec_from_file_location('ar_viewer_server', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def dataset():
    root = ROOT/'tests/_generated'/('viewer_'+uuid.uuid4().hex)
    (root/'validation').mkdir(parents=True)
    (root/'manifest.json').write_text(json.dumps({'split':{'validation':['260101120000','260102120000'],'test':['private']}}))
    (root/'train_model.json').write_text(json.dumps(dict(p=1,intercept=2.,coefficients=[.5],hold_back=1,sigma2=3.)))
    for wid, offset in [('260101120000',0),('260102120000',100)]:
        pd.DataFrame(dict(segment_id=[1,1,2],elapsed_seconds=[0,1,5],
            observed_power_w=[204+offset,206+offset,202+offset],prescribed_power_w=[200,200,200],
            simulated_power_w=[202,204,206],observed_residual_w=[4+offset,6+offset,2+offset],
            simulated_residual_w=[2,4,6])).to_csv(root/'validation'/f'{wid}.csv.gz',index=False)
    return root


def test_scaling_is_from_training_and_identical_for_both_series_and_workouts():
    store = module().ViewerData(dataset())
    assert store.catalog()['model']['residual_mean_w'] == 4.
    assert store.catalog()['model']['residual_sd_w'] == 2.
    first = store.workout('260101120000')
    second = store.workout('260102120000')
    assert first['segments'][0]['rows'][0] == [0.,204.,200.,202.,4.,2.,0.,-1.]
    assert second['segments'][0]['rows'][0][-2] == 50.  # never normalize validation locally
    assert [len(s['rows']) for s in first['segments']] == [2,1]
    assert first['samples'] == 3
    with pytest.raises(KeyError):
        store.workout('private')
    with pytest.raises(KeyError):
        store.workout('../train_model')


def test_http_only_serves_validation_and_fixed_assets():
    mod = module()
    server = mod.create_server(dataset(), host='127.0.0.1', port=0)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        catalog = json.load(urllib.request.urlopen(base+'/api/workouts'))
        assert len(catalog['workouts']) == 2
        response = urllib.request.urlopen(base+'/api/workouts/260101120000')
        assert response.headers['Cache-Control'] == 'no-store'
        assert json.load(response)['id'] == '260101120000'
        assert urllib.request.urlopen(base+'/').status == 200
        for path in ['/api/workouts/private','/../train_model.json','/api/workouts/%2e%2e','/reports/','/server.py']:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(base+path)
            assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_acf_excludes_boundaries_and_handles_constant_series():
    mod = module()
    real = [np.array([1., 2., 3., 4.]), np.array([101., 102., 103., 104.])]
    simulated = [np.tile(x, (5, 1)) for x in real]
    result = mod.acf_comparison(real, simulated, max_lag=2)
    assert result['rows'][0] == [1, .25, .25, .25, .25, 6]
    assert result['rows'][1] == [2, -.3, -.3, -.3, -.3, 4]
    constant = mod.acf_comparison([np.ones(4)], [np.ones((5, 4))], max_lag=1)
    assert constant['rows'][0][1:5] == [None] * 4
