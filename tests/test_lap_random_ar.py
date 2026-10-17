import importlib
import sys
from pathlib import Path
import numpy as np
from scipy.linalg import toeplitz,block_diag
from scipy.stats import multivariate_normal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def api():return importlib.import_module('power_response_estimation.lap_random_ar')


def test_integrated_likelihood_matches_dense_covariance_with_gaps():
    a=api();m=a.LapAR(3.,5.,.6,.2,mean=.4)
    parts=[np.array([2.,3.,-1.,4.]),np.array([3.,-2.,6.])]
    labels=[np.array([1,1,2,2]),np.array([2,2,3])]
    prep=a.prepare(parts,labels,m.mean)
    blocks=[]
    for x in parts:
        rho=[1.,m.k1]
        for i in range(2,len(x)):rho.append(m.phi[0]*rho[-1]+m.phi[1]*rho[-2])
        blocks.append(m.w_variance*toeplitz(rho))
    lap=np.concatenate(labels);cov=block_diag(*blocks)+m.sigma_b**2*(lap[:,None]==lap[None,:])
    expected=-multivariate_normal.logpdf(np.concatenate(parts),mean=np.full(7,m.mean),cov=cov)
    np.testing.assert_allclose(a.nll(m,prep),expected,rtol=1e-12)


def test_zero_offset_is_exact_ar_likelihood():
    from power_response_estimation.scaled_ar import ScaledAR
    a=api();m=a.LapAR(3.,0.,.6,.2,mean=.4);r=np.array([2.,3.,-1.,4.])
    simple=ScaledAR(np.sqrt(m.w_variance),np.sqrt(m.w_variance),m.k1,m.k2,mean=m.mean)
    np.testing.assert_allclose(a.nll(m,a.prepare([r],[np.array([1,1,2,2])],m.mean)),simple.nll(r,np.zeros(4)),rtol=1e-12)


def test_free_covariance_and_shared_lap_offset():
    a=api();m=a.LapAR(3.,5.,.6,.2)
    parts=[np.array([1,1,2]),np.array([2,3,3])]
    sims,offsets=m.simulate(parts,40000,np.random.default_rng(9))
    np.testing.assert_array_equal(offsets[0][:,2],offsets[1][:,0])
    cov=np.cov(np.concatenate(sims,axis=1),rowvar=False)
    np.testing.assert_allclose(np.diag(cov),m.w_variance+25,rtol=.025)
    np.testing.assert_allclose(cov[2,3],25,rtol=.035)
    np.testing.assert_allclose(cov[0,3],0,atol=1.)


def test_fit_recovers_nonzero_lap_variance():
    a=api();truth=a.LapAR(5.,12.,.6,.15,mean=.2);rng=np.random.default_rng(74)
    labels=[np.repeat(np.arange(10),100)];prepared=[]
    for _ in range(10):
        sims,_=truth.simulate(labels,1,rng)
        prepared.append(a.prepare([sims[0][0]],labels,truth.mean))
    model,stats=a.fit(prepared,truth.mean,truth.w_variance+144)
    np.testing.assert_allclose(model.sigma_e,5,rtol=.06)
    np.testing.assert_allclose(model.sigma_b,12,rtol=.25)
    np.testing.assert_allclose(model.phi,truth.phi,atol=.05)
