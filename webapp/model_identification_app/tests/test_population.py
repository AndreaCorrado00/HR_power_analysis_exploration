import copy
import numpy as np
import pytest


def fixture(n=30):
    rng = np.random.default_rng(42)
    keys = ['K', 'L', 'tau', 'B']
    covariance = np.diag([.000004, .04, .25, .25])
    manifest = {'id': 'population-test', 'model': {'id': 'p1d', 'parameters': [
        {'key': k, 'unit': u} for k, u in zip(keys, ['bpm/W', 's', 's', 'bpm'])]},
        'model_structure': 'p1d_full', 'config': {'initialization_mode': 'estimated_equilibrium',
        'initialization_protocol': 'segment_v2', 'use_pre_window': True},
        'parameter_bounds': {'keys': keys, 'lower': [1e-6, 0, .01, None], 'upper': [5, None, 1800, None]},
        'split': {'unit': 'activity', 'assignments': {'train': [str(i) for i in range(n)], 'val': [], 'test': ['test']}},
        'dataset': {'segments': [{'id': str(i), 'activity_id': str(i)} for i in range(n)]}}
    fits = []
    for i, theta in enumerate(rng.normal([.3, 5, 45, 120], [.02, 1, 4, 3], (n, 4))):
        fits.append({'segment_id': str(i), 'filename': str(i)+'.csv', 'status': 'fitted', 'warnings': [],
            'parameters': {k: {'estimate': float(x), 'se': float(np.sqrt(covariance[j,j])),
                'rse_pct': float(100*np.sqrt(covariance[j,j])/abs(x)), 'at_bound': False, 'fixed': False}
                for j, (k,x) in enumerate(zip(keys, theta))},
            'uncertainty': {'covariance': covariance.tolist(), 'rank': 4, 'p': 4}})
    return manifest, fits


def test_reml_separates_sampling_variance_from_population_variance():
    from webapp.model_identification_app.backend.population import fit_reml
    y = np.array([[-2.], [-1.], [0.], [1.], [2.]])
    model = fit_reml(y, np.repeat([[[.5]]], 5, axis=0))
    assert model['mean'][0] == pytest.approx(0, abs=1e-5)
    assert model['covariance'][0][0] == pytest.approx(2., abs=2e-3)


def test_screening_preserves_originals_and_ignores_nontrain_results():
    from webapp.model_identification_app.backend.population import analyze
    manifest, fits = fixture()
    fits[0]['parameters']['K']['at_bound'] = True
    before = copy.deepcopy(fits)
    extra = copy.deepcopy(fits[-1]); extra['segment_id'] = 'test'
    extra['parameters']['B']['estimate'] = 10000
    a = analyze(manifest, fits)
    b = analyze(manifest, fits+[extra])
    assert fits == before
    assert a['model'] == b['model']
    assert a['screening'][0]['parameters']['K'] == ['at_bound']
    assert a['retained_vectors'] == len(fits)-1
    assert a['model']['mean'][3] == pytest.approx(120, abs=3)


def test_power_only_prediction_starts_at_B_and_never_reads_test_hr():
    from webapp.model_identification_app.backend.population import analyze, predict
    manifest, fits = fixture()
    a = analyze(manifest, fits)
    t = np.arange(-10, 101, dtype=float)
    power = np.where(t < 0, 100., 200.)
    first = predict(manifest, a, t, power, np.full(len(t), 130.))
    second = predict(manifest, a, t, power, np.full(len(t), np.nan))
    assert first['series']['predicted'] == second['series']['predicted']
    assert first['series']['lower'] == second['series']['lower']
    assert first['series']['predicted'][0] == a['model']['mean'][3]
    assert first['P0'] == 100
    assert second['metrics'] is None
    assert first['series']['predicted'][-1] > first['series']['predicted'][0]


def test_unidentifiable_or_missing_B_blocks_prediction_without_fallback():
    from webapp.model_identification_app.backend.population import analyze, predict
    manifest, fits = fixture(3)
    a = analyze(manifest, fits)
    assert a['model'] is None
    assert a['status'] == 'insufficient_data'
    assert a['fit_correlations']['all']['n'] == 3
    assert len(a['fit_correlations']['all']['matrix']) == 4
    with pytest.raises(ValueError): predict(manifest, a, np.arange(10.), np.ones(10), np.ones(10))
    manifest['config']['initialization_mode'] = 'equilibrium'
    assert analyze(manifest, fits)['status'] == 'incompatible'


def test_fixed_delay_is_not_excluded_and_has_zero_population_variance():
    from webapp.model_identification_app.backend.population import analyze
    manifest, fits = fixture(12)
    manifest['parameter_bounds']['lower'][1] = 0
    manifest['parameter_bounds']['upper'][1] = 0
    for r in fits:
        r['parameters']['L'].update(estimate=0, se=None, at_bound=True, fixed=True)
        r['uncertainty'].update(rank=3, p=3)
        c = np.asarray(r['uncertainty']['covariance']); c[1,:] = 0; c[:,1] = 0
        r['uncertainty']['covariance'] = c.tolist()
    a = analyze(manifest, fits)
    assert a['retained_vectors'] == 12
    assert a['model']['mean'][1] == 0
    assert a['model']['sd'][1] == 0


def test_reml_zero_heterogeneity_boundary_and_covariance_recovery():
    from webapp.model_identification_app.backend.population import fit_reml
    result = fit_reml(np.zeros((10,2)), np.repeat([np.eye(2)],10,axis=0))
    assert np.max(np.abs(result['covariance'])) < 1e-6
    rng = np.random.default_rng(123)
    y = rng.multivariate_normal([2,5], [[2, .8],[.8, 3]], 200)
    s = np.repeat([np.eye(2)*.2],200,axis=0)
    result = fit_reml(y,s)
    np.testing.assert_allclose(result['covariance'], np.cov(y,rowvar=False)-np.eye(2)*.2, atol=.005)


def test_invalid_covariance_and_multistart_failures_are_excluded():
    from webapp.model_identification_app.backend.population import analyze
    manifest, fits = fixture(12)
    fits[0]['uncertainty']['covariance'] = None
    fits[1]['warnings'] = ['equivalent_predictions_different_parameters']
    fits[2]['uncertainty']['rank'] = 2
    a = analyze(manifest, fits)
    assert a['retained_vectors'] == 9
    assert not any(s['included'] for s in a['screening'][:3])


@pytest.mark.parametrize('mode', ['legacy_power_only', 'observed_hr', 'local_B_10s'])
def test_population_api_persistence_and_export(tmp_path, mode):
    import io
    import zipfile
    from fastapi.testclient import TestClient
    from webapp.model_identification_app.backend.app import create_app
    manifest, fits = fixture(12)
    manifest.update(manifest_filename='population-test.json', status='completed', created_at='2026-09-29',
                    progress={'done':12,'total':12,'failed':0}, signal='raw', environment={})
    manifest['dataset']['name'] = 'Synthetic population'
    manifest['config']['use_pre_window'] = False
    with TestClient(create_app(tmp_path)) as c:
        service = c.app.state.runs
        data = ('elapsed_seconds,power_w,heart_rate_bpm\n'+''.join(f'{i},100,120\n' for i in range(31))).encode()
        digest = service.store.blob(data)
        manifest['dataset']['segments'].append({'id':'test','filename':'test.csv','sha256':digest,'activity_id':'unseen'})
        folder = tmp_path/'runs'/manifest['id']; folder.mkdir()
        for r in fits: service.store.write_path(folder/(r['segment_id']+'.json'),r)
        service.save(manifest)
        assert c.get('/api/runs/population-test/population').json() is None
        response = c.post('/api/runs/population-test/population',json={'draws':50, 'prediction_mode':mode})
        assert response.status_code == 200, response.text
        analysis = response.json()
        assert analysis['config']['prediction_mode'] == mode
        assert analysis['test'][0]['series']['predicted'][0] == (analysis['model']['mean'][3] if mode == 'legacy_power_only' else 120)
        assert c.get('/api/runs/population-test/population').json() == analysis
        assert len(c.get('/api/runs/population-test/results').json()) == 12
        assert (folder/'population'/(analysis['id']+'.json')).exists()
        review_url = '/api/runs/population-test/population/reviews/test'
        body = {'analysis_id':analysis['id'], 'verdict':'negative', 'labels':['systematic_overestimate'], 'notes':'Offset < 10 bpm & recupero'}
        reviewed = c.put(review_url, json=body)
        assert reviewed.status_code == 200, reviewed.text
        reopened = c.get('/api/runs/population-test/population').json()
        assert reopened['reviews']['test']['notes'] == body['notes']
        assert reopened['reviews']['test']['verdict'] == 'negative'
        assert c.put(review_url, json={**body,'analysis_id':'stale'}).status_code == 409
        assert c.put(review_url, json={**body,'labels':['invented']}).status_code == 400
        exported_review = c.post('/api/runs/population-test/population/exports/json', json={'analysis_id':analysis['id']})
        assert exported_review.status_code == 200
        assert exported_review.json()['reviews']['test']['labels'] == ['systematic_overestimate']
        assert exported_review.json()['review_context']['warnings']
        review_pdf = c.post('/api/runs/population-test/population/exports/pdf', json={'analysis_id':analysis['id']})
        assert review_pdf.status_code == 200, review_pdf.text[:100]
        assert review_pdf.content.startswith(b'%PDF')
        exported = c.post('/api/runs/population-test/exports/tables')
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            assert 'population.json' in z.namelist()
            assert 'test' in z.read('population_test_metrics.csv').decode()
        pdf = c.post('/api/runs/population-test/exports/pdf')
        assert pdf.status_code == 200, pdf.text[:100] if not pdf.content.startswith(b'%PDF') else ''
        assert pdf.content.startswith(b'%PDF')
        assert c.post('/api/runs/population-test/population',json={'draws':1}).status_code == 422
        fresh = c.post('/api/runs/population-test/population', json={'draws':50, 'prediction_mode':mode}).json()
        assert fresh['reviews'] == {}
        assert c.put(review_url, json=body).status_code == 409


def test_review_colors_use_full_set_absolute_bias_and_fixed_bounds():
    from webapp.model_identification_app.backend.population_review import review_context
    manifest, _ = fixture(12)
    manifest['parameter_bounds']['upper'][1] = 0
    a = {'config':{'prediction_mode':'observed_hr'}, 'test':[
        {'metrics':{'MAE':1, 'bias':-10}}, {'metrics':{'MAE':5,'bias':0}},
        {'metrics':{'MAE':None,'bias':5}}]}
    context = review_context(manifest,a)
    assert context['scales']['MAE'] == {'min':1, 'max':5, 'absolute':False}
    assert context['scales']['bias'] == {'min':0, 'max':10, 'absolute':True}
    assert context['fixed_parameters'] == [{'key':'L','value':0,'unit':'s'}]
    assert 'P(t)-P0' in context['equation']


@pytest.mark.parametrize('mode', ['observed_hr', 'local_B_10s'])
def test_initialization_uses_only_allowed_hr_and_scores_after_window(mode):
    from webapp.model_identification_app.backend.population import analyze, predict
    manifest, fits = fixture(12)
    a = analyze(manifest, fits, {'prediction_mode': mode, 'draws': 50})
    t = np.arange(-10., 101.)
    power = np.full(len(t), 100.)
    tau = a['model']['mean'][a['model']['keys'].index('tau')]
    hr = 110 - 50*np.exp(-np.maximum(t, 0)/tau)
    first = predict(manifest, a, t, power, hr)
    changed = hr.copy(); changed[t >= 10] = 999
    second = predict(manifest, a, t, power, changed)
    assert first['series']['predicted'] == second['series']['predicted']
    assert first['series']['lower'] == second['series']['lower']
    assert first['initial_HR'] == 60
    assert first['metrics']['N'] == 91
    if mode == 'local_B_10s':
        assert a['model']['keys'] == ['K', 'L', 'tau']
        assert first['equilibrium_B'] == pytest.approx(110)
        assert first['metrics']['RMSE'] < 1e-8
    else:
        assert first['equilibrium_B'] == a['model']['mean'][3]
    hr[t == 0] = np.nan
    with pytest.raises(ValueError, match='HR'):
        predict(manifest, a, t, power, hr)


def test_local_population_does_not_screen_on_B_only_bounds():
    from webapp.model_identification_app.backend.population import analyze
    manifest, fits = fixture(12)
    for fit in fits: fit['parameters']['B']['at_bound'] = True
    a = analyze(manifest, fits, {'prediction_mode': 'local_B_10s'})
    assert a['retained_vectors'] == 12
    assert a['model']['keys'] == ['K', 'L', 'tau']


def test_local_B_bounds_and_fixed_zero_delay():
    from webapp.model_identification_app.backend.population import analyze, predict
    manifest, fits = fixture(12)
    manifest['parameter_bounds']['upper'][1] = 0
    manifest['parameter_bounds']['upper'][3] = 100
    for fit in fits:
        fit['parameters']['L'].update(estimate=0, se=None, at_bound=True)
        fit['uncertainty']['rank'] = 3
        cov = np.asarray(fit['uncertainty']['covariance']); cov[1,:] = 0; cov[:,1] = 0
        fit['uncertainty']['covariance'] = cov.tolist()
    a = analyze(manifest, fits, {'prediction_mode':'local_B_10s', 'draws':50})
    assert a['model']['mean'][1] == 0
    t = np.arange(-10., 31.)
    result = predict(manifest, a, t, np.full(len(t),100.), np.full(len(t),140.))
    assert result['equilibrium_B'] == 100
    assert result['calibration']['at_bound']
    assert result['calibration']['warnings']
    with pytest.raises(ValueError, match='valutazione'):
        predict(manifest, a, t[t<10], np.full(sum(t<10),100.), np.full(sum(t<10),140.))
