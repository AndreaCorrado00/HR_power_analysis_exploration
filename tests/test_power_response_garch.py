"""GARCH recursion, training estimation and absence of future information."""
import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def api():
    return importlib.import_module('power_response_estimation.garch')


def test_recursion_uses_past_error_only_and_resets():
    m = api().GARCH11(2.,.2,.6)
    np.testing.assert_allclose(m.variance([3.,4.,100.]),[10.,9.8,11.08])
    np.testing.assert_allclose(m.variance([3.,4.,-1000.]),[10.,9.8,11.08])
    assert m.variance([50.])[0] == pytest.approx(10.)


def test_invalid_variance_models_rejected():
    for pars in [(0,.2,.6),(2,-.1,.6),(2,.6,.5),(np.nan,.1,.2)]:
        with pytest.raises(ValueError):
            api().GARCH11(*pars)


def test_likelihood_gradient_matches_numerical_difference():
    from scipy.optimize._numdiff import approx_derivative
    parts = [np.random.default_rng(4).normal(size=250),np.arange(10.)/5]
    theta = np.array([.2,.15,.6])
    value,grad = api().objective(theta,parts)
    numerical = approx_derivative(lambda x:api().objective(x,parts)[0],theta).ravel()
    np.testing.assert_allclose(grad,numerical,rtol=1e-5,atol=1e-6)
    assert np.isfinite(value)


def test_fit_recovers_synthetic_conditional_variance():
    rng = np.random.default_rng(123)
    parts = []
    for _ in range(4):
        h = 4.
        e = []
        for i in range(6000):
            value = rng.normal()*np.sqrt(h)
            h = .4+.2*value**2+.7*h
            if i>=1000:
                e.append(value)
        parts.append(np.array(e))
    model,stats = api().fit_garch(parts)
    assert stats['converged']
    assert model.alpha == pytest.approx(.2,abs=.06)
    assert model.beta == pytest.approx(.7,abs=.09)
    assert model.unconditional_variance == pytest.approx(4.,rel=.25)


def test_simulation_reproducibility_and_finite_values():
    from power_response_estimation.ar import ARModel
    ar = ARModel(2,0,[.5,.1],2,sigma2=4)
    m = api().GARCH11(.4,.2,.7)
    a = api().simulate(m,ar,100,30,np.random.default_rng(42))
    b = api().simulate(m,ar,100,30,np.random.default_rng(42))
    np.testing.assert_array_equal(a,b)
    assert a.shape==(30,100) and np.isfinite(a).all()


def test_constant_variance_gaussian_metrics():
    r = api().conditional_metrics(np.array([-2.,0.,2.]),np.full(3,4.))
    assert r['coverage80'] == 1
    assert r['width80_w'] == pytest.approx(5.126206262,rel=1e-8)
