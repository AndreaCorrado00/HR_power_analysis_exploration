"""No future information, variance targeting and context variance recovery."""
import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def api():
    return importlib.import_module('power_response_estimation.variance_models')


def test_context_uses_only_current_and_past_target():
    x = api().context_features(np.array([100.,100.,200.,200.,150.]))
    np.testing.assert_allclose(x[:,1],[1,1,2,2,1.5])
    np.testing.assert_allclose(x[:,2],[0,0,1,np.exp(-1/30),.5])
    changed = api().context_features(np.array([100.,100.,200.,200.,500.]))
    np.testing.assert_array_equal(x[:4],changed[:4])


def test_targeting_keeps_training_variance_and_gradient():
    from scipy.optimize._numdiff import approx_derivative
    parts = [np.random.default_rng(9).normal(size=700)]
    x = np.array([.12,.75])
    value,grad = api().targeted_objective(x,parts)
    numeric = approx_derivative(lambda a:api().targeted_objective(a,parts)[0],x).ravel()
    np.testing.assert_allclose(grad,numeric,rtol=1e-5,atol=1e-6)
    m,stats = api().fit_targeted(parts)
    assert m.unconditional_variance == pytest.approx(np.mean(parts[0]**2))
    assert stats['converged']


def test_context_fit_recovers_variance_instead_of_mean():
    rng = np.random.default_rng(2026)
    target = np.tile(np.repeat([100.,200.,350.,150.],80),100)
    x = api().context_features(target)
    expected = np.array([4.,.4,.6])
    e = rng.normal(size=len(x))*np.exp(x@expected/2)
    beta,stats = api().fit_context([x],[e],['workout'])
    np.testing.assert_allclose(beta,expected,atol=.12)
    assert stats['converged']


def test_free_simulation_scale_reproduces_constant_ar_variance():
    from power_response_estimation.ar import ARModel
    ar = ARModel(1,0,[.5],1,sigma2=4)
    z = np.random.default_rng(5).normal(size=(20000,1))
    initial = np.random.default_rng(6).normal(size=(20000,1))
    sim = api().simulate_context(ar,np.array([4.]),z,initial)
    assert sim.var() == pytest.approx(4/(1-.5**2),rel=.04)


def test_context_simulation_does_not_depend_on_observed_errors():
    from power_response_estimation.ar import ARModel
    ar = ARModel(2,1,[.5,.1],2,sigma2=4)
    rng = np.random.default_rng(7)
    z,initial = rng.normal(size=(20,100)),rng.normal(size=(20,2))
    h = np.linspace(2,10,100)
    a = api().simulate_context(ar,h,z,initial)
    b = api().simulate_context(ar,h,z,initial)
    np.testing.assert_array_equal(a,b)
