import importlib
import sys
from pathlib import Path
import numpy as np
from scipy.stats import multivariate_normal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def api():return importlib.import_module('power_response_estimation.scaled_ar')


def test_likelihood_matches_dense_gaussian_covariance():
    from scipy.linalg import toeplitz
    m=api().ScaledAR(20.,40.,.6,.2,mean=.3)
    r=np.array([10.,-5.,20.,40.]); phase=np.array([0,0,1,1])
    rho=[1.,.6]
    for _ in range(2):rho.append(m.phi[0]*rho[-1]+m.phi[1]*rho[-2])
    s=m.scales(phase); cov=toeplitz(rho)*s[:,None]*s[None,:]
    np.testing.assert_allclose(m.nll(r,phase),-multivariate_normal.logpdf(r,mean=np.full(4,.3),cov=cov),rtol=1e-12)


def test_conditional_uses_scale_ratio_and_past_only():
    m=api().ScaledAR(10.,30.,.6,.2,mean=1.)
    r=np.array([3.,4.,8.,9.]); phase=np.array([0,0,1,1])
    mu,h=m.conditional(r,phase)
    expected=1+30*(m.phi[0]*(4-1)/10+m.phi[1]*(3-1)/10)
    np.testing.assert_allclose(mu[2],expected)
    changed=r.copy();changed[2:]=500
    np.testing.assert_allclose(m.conditional(changed,phase)[0][2],mu[2])
    np.testing.assert_allclose(h[2:],30**2*m.q)


def test_stationary_marginal_scale_and_covariance():
    m=api().ScaledAR(10.,30.,.6,.2)
    sims=m.simulate(np.array([0,0,1,1]),50000,np.random.default_rng(4))
    np.testing.assert_allclose(sims.std(axis=0),[10,10,30,30],rtol=.02)
    np.testing.assert_allclose(np.corrcoef(sims.T)[1,2],.6,atol=.02)


def test_phase_causal_no_fake_initial_transition():
    phase=api().transition_phase(np.r_[np.full(40,100),np.full(40,200)])
    assert not phase[:40].any()
    assert phase[40:70].all() and not phase[70:].any()


def test_joint_fit_recovers_known_scales_and_correlation():
    truth=api().ScaledAR(20.,45.,.65,.15,mean=.2)
    phase=np.tile(np.r_[np.ones(30,dtype=bool),np.zeros(170,dtype=bool)],30)
    sims=truth.simulate(phase,4,np.random.default_rng(21))
    fitted,stats=api().fit(list(sims),[phase]*4,.2,True)
    np.testing.assert_allclose([fitted.plateau_sd,fitted.transition_sd],[20,45],rtol=.08)
    np.testing.assert_allclose(fitted.phi,truth.phi,atol=.03)
    assert all(x['success'] for x in stats['attempts'])
