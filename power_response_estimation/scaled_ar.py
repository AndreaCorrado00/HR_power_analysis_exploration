"""Heteroscedastic Gaussian AR correlation: covariance D R D (GLS family)."""
from dataclasses import dataclass,asdict
import numpy as np
from scipy.optimize import minimize
from .ar import ARModel
from .variance_models import simulate_context


def transition_phase(target):
    phase=np.zeros(len(target),dtype=bool)
    for i in np.flatnonzero(np.diff(target)!=0)+1:phase[i:i+30]=True
    return phase


@dataclass(frozen=True)
class ScaledAR:
    plateau_sd: float
    transition_sd: float
    k1: float
    k2: float
    mean: float=0.

    def __post_init__(self):
        if min(self.plateau_sd,self.transition_sd)<=0 or max(abs(self.k1),abs(self.k2))>=1:
            raise ValueError('Positive scales and stable partial correlations required')

    @property
    def phi(self):return np.array([self.k1*(1-self.k2),self.k2])

    @property
    def q(self):return (1-self.k1**2)*(1-self.k2**2)

    def scales(self,phase):return np.where(phase,self.transition_sd,self.plateau_sd)

    def nll(self,residual,phase):
        scale=self.scales(phase);u=(residual-self.mean)/scale;n=len(u)
        if n<2:raise ValueError('At least two samples required')
        initial=(u[0]**2+u[1]**2-2*self.k1*u[0]*u[1])/(1-self.k1**2)
        e=u[2:]-self.phi[0]*u[1:-1]-self.phi[1]*u[:-2]
        return float(.5*(n*np.log(2*np.pi)+np.log(1-self.k1**2)+initial+(n-2)*np.log(self.q)+e@e/self.q)+np.log(scale).sum())

    def conditional(self,residual,phase):
        scale=self.scales(phase);u=(residual-self.mean)/scale
        mu=np.full(len(u),np.nan);h=np.full(len(u),np.nan)
        mu[2:]=self.mean+scale[2:]*(self.phi[0]*u[1:-1]+self.phi[1]*u[:-2])
        h[2:]=scale[2:]**2*self.q
        return mu,h

    def simulate(self,phase,paths,rng):
        ar=ARModel(2,0.,self.phi.tolist(),2,sigma2=self.q)
        z=rng.standard_normal((paths,len(phase)));initial=rng.standard_normal((paths,2))
        u=simulate_context(ar,np.full(len(phase),self.q),z,initial)
        return self.mean+self.scales(phase)*u


def fit(parts,phases,mean,two_scales=True):
    n=sum(map(len,parts));sd=np.sqrt(sum(np.sum((r-mean)**2) for r in parts)/n)
    def unpack(x):
        scales=np.exp(x[:2]) if two_scales else np.repeat(np.exp(x[0]),2)
        k=np.tanh(x[-2:]);return ScaledAR(*scales,*k,mean=mean)
    def loss(x):
        m=unpack(x);return sum(m.nll(r,p) for r,p in zip(parts,phases))/n
    attempts=[]
    for k1,k2 in [(.75,.08),(.4,.2),(.9,-.1)]:
        initial=[np.log(sd)]*(2 if two_scales else 1)+[np.arctanh(k1),np.arctanh(k2)]
        result=minimize(loss,initial,method='L-BFGS-B',bounds=[(-5,10)]*(2 if two_scales else 1)+[(-4,4)]*2,
            options={'ftol':1e-12,'gtol':1e-7,'maxiter':500})
        attempts.append(result)
    converged=[r for r in attempts if r.success and np.isfinite(r.fun)]
    if not converged:raise RuntimeError('No converged fit')
    best=min(converged,key=lambda r:r.fun);model=unpack(best.x)
    return model,dict(nobs=n,nll=float(best.fun),parameters=asdict(model),phi=model.phi.tolist(),innovation_variance_unit=model.q,
        attempts=[dict(success=bool(r.success),nll=float(r.fun),iterations=int(r.nit)) for r in attempts],
        uncertainty='Not estimated; compare robustness and validation before adoption')
