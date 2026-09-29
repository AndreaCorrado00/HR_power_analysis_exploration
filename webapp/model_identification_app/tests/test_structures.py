import numpy as np
import pytest

from webapp.model_identification_app.backend.models import p1d


def transient():
    t = np.arange(-10., 41.)
    power = np.where(t < 0, 100., 200.)
    hr = 120 + .2 * 100 * (-np.expm1(-np.maximum(t-2.5, 0)/15))
    return t, power, hr


def test_prewindow_is_context_only_and_initializes_baselines():
    r = p1d.fit(*transient(), {'use_pre_window': True, 'n_starts': 3})
    assert r['initial_conditions']['P0'] == 100
    assert r['initial_conditions']['HR0'] == 120
    assert r['pre_window']['used'] is True
    assert len(r['pre_window']['time']) == 10
    assert r['series']['time'][0] == 0
    assert r['uncertainty']['N'] == 41
    assert r['segment_duration_seconds'] == 40
    assert r['metrics']['RMSE'] < 1e-6
    assert r['rho'] == pytest.approx((40-2.5)/15, abs=1e-5)
    assert r['identifiability']['correlation_K_tau'] is not None


def test_disabled_window_uses_first_lap_sample_but_excludes_negative_times():
    r = p1d.fit(*transient(), {'use_pre_window': False, 'n_starts': 2})
    assert r['initial_conditions']['P0'] == 200
    assert not r['pre_window']['used']
    assert r['pre_window']['available']
    assert len(r['series']['time']) == 41


def test_requested_absent_window_fails_without_fallback():
    with pytest.raises(ValueError, match='pre_window_absent'):
        p1d.fit(np.arange(10.), np.ones(10), np.ones(10), {'use_pre_window': True})


def test_short_transient_recovers_gamma_and_delay_without_k_tau():
    t = np.arange(-10., 31.)
    p = np.where(t < 0, 100., 200.)
    hr = 120 + .012 * 100 * np.maximum(t-2.3, 0)
    r = p1d.fit(t, p, hr, {'model_structure': 'short_transient', 'use_pre_window': True, 'n_starts': 3})
    assert set(r['parameters']) == {'gamma', 'L'}
    assert r['parameters']['gamma']['estimate'] == pytest.approx(.012, abs=1e-7)
    assert r['parameters']['L']['estimate'] == pytest.approx(2.3, abs=1e-5)
    assert r['rho'] is None
    assert r['metrics']['MAE'] < 1e-6
    assert r['metrics']['bias'] == r['metrics']['residual_mean']
    assert 'residual_autocorrelation_lag5' in r['metrics']
    assert len(r['residual_acf']['lags']) > 5


def test_short_transient_fixed_delay_and_invalid_prewindow():
    t, p, hr = transient()
    r = p1d.fit(t, p, hr, {'model_structure': 'short_transient', 'upper': [1., 0.], 'use_pre_window': True, 'n_starts': 2})
    assert r['parameters']['L']['fixed']
    assert r['uncertainty']['p'] == 1
    p[1] = np.nan
    with pytest.raises(ValueError, match='pre_window_nonfinite'):
        p1d.fit(t, p, hr, {'use_pre_window': True})


def test_nonfinite_unused_context_is_preserved_without_affecting_fit():
    t,p,hr = transient()
    p[1] = np.nan
    r = p1d.fit(t,p,hr,{'use_pre_window':False,'n_starts':2})
    assert r['pre_window']['power'][1] is None
    assert r['uncertainty']['N'] == 41


def test_short_transient_irregular_samples_fractional_delay():
    t = np.array([0.,1.,2.,3.5,6.,10.,20.])
    power = np.array([100.,100.,200.,200.,200.,200.,200.])
    expected = 110 + .012*100*np.maximum(t-2-1.25,0)
    np.testing.assert_allclose(p1d.simulate(t,power,110,[.012,1.25],structure='short_transient'),expected)


def test_quality_and_residual_metrics_match_saved_objective_series():
    t,p,hr = transient()
    hr += .1*np.sin(t)
    r = p1d.fit(t,p,hr,{'use_pre_window':True,'n_starts':2})
    e = np.array(r['series']['residual'])
    obs = np.array(r['series']['observed'])
    pred = np.array(r['series']['predicted'])
    c = e-e.mean()
    assert r['metrics']['MAE'] == pytest.approx(np.mean(abs(e)))
    assert r['metrics']['R2'] == pytest.approx(1-(e@e)/np.sum((obs-obs.mean())**2))
    assert r['metrics']['amplitude_ratio'] == pytest.approx(np.ptp(pred)/np.ptp(obs))
    assert r['metrics']['residual_autocorrelation_lag5'] == pytest.approx(c[5:]@c[:-5]/(c@c))


def test_gamma_multistart_does_not_confuse_distinct_small_gains(monkeypatch):
    original = p1d.least_squares
    gains = iter([.001,.009])
    def alternatives(*args, **kwargs):
        result = original(*args, **kwargs)
        result.x[0] = next(gains)
        result.x[1] = 2.
        return result
    monkeypatch.setattr(p1d,'least_squares',alternatives)
    r = p1d.fit(np.arange(20.),np.ones(20)*100,np.ones(20)*120,{'model_structure':'short_transient','n_starts':2})
    assert not r['all_starts_agree']
    assert 'equivalent_predictions_different_parameters' in r['warnings']
