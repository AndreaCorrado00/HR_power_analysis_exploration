import numpy as np
import pytest

from webapp.model_identification_app.backend.models import p1d


def test_profile_search_improves_short_response_and_preserves_multistart():
    t = np.arange(63.)
    power = np.where(t < 30, 600., 80.)
    hr = p1d.simulate(t, power, 170., [.02, 22., .06], 100.)
    # The first lap power is the reference when pre-window is disabled.
    t = np.r_[np.arange(-10., 0), t]
    power = np.r_[np.full(10, 100.), power]
    hr = np.r_[np.full(10, 170.), hr]
    cfg = dict(use_pre_window=True, n_starts=2)
    old = p1d.fit(t, power, hr, dict(cfg, search_strategy='multistart'))
    result = p1d.fit(t, power, hr, dict(cfg, search_strategy='profile_multistart'))
    assert result['metrics']['SSE'] <= old['metrics']['SSE'] + 1e-9
    assert result['metrics']['RMSE'] < .01
    assert result['search']['grid_evaluations'] == 301 * 141
    assert len([s for s in result['starts'] if s['source'] == 'multistart']) == 2
    assert any(s['source'] == 'profile_grid' for s in result['starts'])
    assert result['search']['baseline_SSE'] == pytest.approx(old['metrics']['SSE'])


def test_profile_search_handles_zero_excitation_and_fixed_delay():
    result = p1d.fit(np.arange(20.), np.ones(20)*100, np.ones(20)*120,
                     dict(search_strategy='profile_multistart', upper=[5., 0., 1800.], n_starts=2))
    assert result['identification_valid']
    assert result['uncertainty']['rank'] == 0
    assert result['parameters']['K']['se'] is None
    assert result['parameters']['L']['fixed']
    assert result['search']['grid_evaluations'] == 141


def test_bounded_gain_equilibrium_profile_matches_independent_solver():
    from scipy.optimize import lsq_linear
    from webapp.model_identification_app.backend.models.profile_search import bounded_linear_pair
    rng = np.random.default_rng(7)
    g = np.linspace(0,1,30)
    f = np.array([rng.normal(size=30), np.zeros(30), 2*g, -3*g])
    target = rng.normal(size=30)*10+20*g
    lo, hi = np.array([.01,0,.1,-5.]),np.array([2.,30.,100.,8.])
    k,b,sse = bounded_linear_pair(f,g,target,lo,hi)
    for i in range(len(f)):
        reference = lsq_linear(np.column_stack([f[i],g]),target,bounds=([lo[0],lo[3]],[hi[0],hi[3]]),tol=1e-12)
        assert sse[i] == pytest.approx(2*reference.cost,rel=1e-10)
        assert lo[0] <= k[i] <= hi[0] and lo[3] <= b[i] <= hi[3]
