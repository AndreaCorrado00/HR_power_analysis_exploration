import numpy as np
import pytest

from webapp.model_identification_app.backend.models.p1d import fit, simulate, default_config


def step_fixture():
    t = np.arange(0., 241.)
    p = np.full_like(t, 150.)
    hr = np.full_like(t, 120.)
    for at, delta in [(20, 120), (90, -80), (150, 60)]:
        p[t >= at] += delta
        hr += .28 * delta * (-np.expm1(-np.maximum(t-at-4.3, 0)/27.))
    return t, p, hr


def test_exact_fractional_delay_on_irregular_samples():
    t = np.array([0., 1., 2., 3.5, 6., 10., 20.])
    p = np.array([100., 100., 200., 200., 200., 200., 200.])
    expected = 110 + 30 * (-np.expm1(-np.maximum(t-2.-1.25, 0)/4.))
    np.testing.assert_allclose(simulate(t, p, 110., [.3, 1.25, 4.]), expected, atol=1e-12)


def test_recovers_known_parameters_and_reports_uncertainty():
    t, p, hr = step_fixture()
    result = fit(t, p, hr, default_config())
    np.testing.assert_allclose([result['parameters'][k]['estimate'] for k in ['K','L','tau']], [.28,4.3,27], atol=1e-4)
    assert result['metrics']['RMSE'] < 1e-6
    assert result['optimizer']['success']
    assert len([s for s in result['starts'] if s['source']=='multistart']) == 8
    assert len([s for s in result['starts'] if s['source']=='profile_grid']) == 8
    assert result['uncertainty']['rank'] == 3
    assert result['parameters']['K']['se'] is not None


def test_constant_input_never_reports_false_precision():
    result = fit(np.arange(20.), np.full(20, 200.), np.full(20, 140.), default_config())
    assert result['uncertainty']['rank'] < 3
    assert result['parameters']['K']['se'] is None
    assert 'rank_deficient' in result['warnings']
    assert result['metrics']['residual_autocorrelation_lag1'] is None


def test_covariance_matches_analytic_step_sensitivities():
    t,p,hr = step_fixture()
    result = fit(t,p,hr + .15*np.sin(t*.3),dict(default_config(),n_starts=2))
    K,L,tau = [result['parameters'][k]['estimate'] for k in ['K','L','tau']]
    jac = np.zeros((len(t),3))
    for at, delta in [(20,120),(90,-80),(150,60)]:
        elapsed=np.maximum(t-at-L,0)
        active=t>at+L
        decay=np.exp(-elapsed/tau)
        jac[:,0] += delta*(1-decay)
        jac[:,1] -= active*K*delta*decay/tau
        jac[:,2] -= K*delta*decay*elapsed/tau**2
    expected = result['metrics']['SSE']/(len(t)-3)*np.linalg.inv(jac.T@jac)
    np.testing.assert_allclose(result['uncertainty']['covariance'],expected,rtol=1e-4,atol=1e-9)


@pytest.mark.parametrize('t,p,hr', [([0,1,1,3],[1]*4,[120]*4), ([0,1,2,3],[1,np.nan,1,1],[120]*4)])
def test_invalid_data_are_not_silently_removed(t,p,hr):
    with pytest.raises(ValueError):
        fit(t,p,hr,default_config())


@pytest.mark.parametrize('limit,expected', [(None, 19.), (5., 5.), (120., 19.), (0., 0.)])
def test_delay_domain_and_constant_output_metrics(limit, expected):
    c = default_config()
    c['upper'][1] = limit
    r = fit(np.arange(20.) + 100, np.full(20, 200.), np.full(20, 140.), c)
    assert r['effective_bounds']['upper'][1] == expected
    assert all(0 <= s['theta'][1] <= expected for s in r['starts'])
    assert r['optimizer_success'] is True
    assert r['identification_valid'] is True
    assert r['metrics']['R2'] is None
    assert r['metrics']['amplitude_ratio'] is None
    assert all('near_bound' in p for p in r['parameters'].values())


def test_trajectory_metrics_are_independent_of_parameter_precision():
    t, p, hr = step_fixture()
    r = fit(t,p,hr,default_config())
    assert r['metrics']['R2'] == pytest.approx(1.)
    assert r['metrics']['amplitude_ratio'] == pytest.approx(1.)


@pytest.mark.parametrize('delay', [-.01, 240.01])
def test_internal_guard_rejects_temporally_incompatible_solution(monkeypatch, delay):
    from webapp.model_identification_app.backend.models import p1d
    original = p1d.least_squares
    def incompatible(*args, **kwargs):
        opt = original(*args, **kwargs)
        opt.x[1] = delay
        return opt
    monkeypatch.setattr(p1d, 'least_squares', incompatible)
    r = fit(*step_fixture(), default_config())
    assert r['optimizer_success'] is True
    assert r['identification_valid'] is False
    assert 'delay_outside_segment' in r['failure_reasons']


def test_nonconverged_solution_is_invalid_with_diagnostics(monkeypatch):
    from webapp.model_identification_app.backend.models import p1d
    original = p1d.least_squares
    def unconverged(*args, **kwargs):
        opt = original(*args, **kwargs)
        opt.success = False
        opt.status = 0
        return opt
    monkeypatch.setattr(p1d, 'least_squares', unconverged)
    r = fit(*step_fixture(), default_config())
    assert r['optimizer_success'] is False
    assert r['identification_valid'] is False
    assert r['failure_reasons'] == ['optimizer_not_converged']
    assert r['metrics']['RMSE'] < 1e-6


def test_bound_flags_use_distinct_explicit_tolerances():
    from webapp.model_identification_app.backend.models.p1d import bound_diagnostics
    d = bound_diagnostics(np.array([0., .999999, .5]), np.zeros(3), np.ones(3))
    assert d['K']['at_bound'] and d['K']['near_bound']
    assert not d['L']['at_bound'] and d['L']['near_bound']
    assert not d['tau']['near_bound']
    assert d['L']['near_bound_tolerance'] == 1e-5
