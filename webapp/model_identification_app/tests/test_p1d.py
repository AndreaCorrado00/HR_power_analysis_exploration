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
    assert len(result['starts']) == 8
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
