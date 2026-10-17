"""Gaussian lap random intercept with continuous stationary AR(2) errors."""
from dataclasses import dataclass,asdict
import numpy as np
from scipy.sparse import csr_matrix,hstack
from scipy.linalg import cho_factor,cho_solve
from scipy.optimize import minimize
from .ar import ARModel
from .variance_models import simulate_context


@dataclass(frozen=True)
class LapAR:
    sigma_e: float
    sigma_b: float
    k1: float
    k2: float
    mean: float=0.

    def __post_init__(self):
        if not np.isfinite([self.sigma_e,self.sigma_b,self.k1,self.k2,self.mean]).all() or self.sigma_e<=0 or self.sigma_b<0 or max(abs(self.k1),abs(self.k2))>=1:
            raise ValueError('Finite positive innovation SD, nonnegative offset SD and stable PACF required')

    @property
    def phi(self):return np.array([self.k1*(1-self.k2),self.k2])

    @property
    def q(self):return (1-self.k1**2)*(1-self.k2**2)

    @property
    def w_variance(self):return self.sigma_e**2/self.q

    def simulate(self,lap_parts,paths,rng):
        """No observed powers. One offset per workout/lap, w reset only at gaps."""
        labels=np.unique(np.concatenate(lap_parts));draw=rng.normal(0,self.sigma_b,(paths,len(labels)))
        ar=ARModel(2,0.,self.phi.tolist(),2,sigma2=self.sigma_e**2)
        sims,offsets=[],[]
        for laps in lap_parts:
            n=len(laps);b=draw[:,np.searchsorted(labels,laps)]
            w=simulate_context(ar,np.full(n,self.sigma_e**2),rng.standard_normal((paths,n)),rng.standard_normal((paths,2)))
            sims.append(self.mean+b+w);offsets.append(b)
        return sims,offsets


def prepare(parts,lap_parts,mean):
    """Sufficient cross-products for exact integrated likelihood, one workout."""
    labels=np.unique(np.concatenate(lap_parts));dim=len(labels)+1
    cross=np.zeros((3,3,dim,dim));initial=np.zeros((dim,dim));initial_cross=np.zeros_like(initial)
    for r,laps in zip(parts,lap_parts):
        if len(r)<3:raise ValueError('At least three samples per continuous segment')
        z=csr_matrix((np.ones(len(r)),(np.arange(len(r)),np.searchsorted(labels,laps))),shape=(len(r),len(labels)))
        a=hstack([csr_matrix((r-mean)[:,None]),z],format='csr')
        lagged=[a[2-i:len(r)-i] for i in range(3)]
        for i in range(3):
            for j in range(3):cross[i,j]+=(lagged[i].T@lagged[j]).toarray()
        x,y=a[:2].toarray();initial+=np.outer(x,x)+np.outer(y,y);initial_cross+=np.outer(x,y)+np.outer(y,x)
    return dict(n=sum(map(len,parts)),segments=len(parts),laps=len(labels),cross=cross,initial=initial,initial_cross=initial_cross)


def nll(model,prepared):
    c=np.r_[1.,-model.phi]
    s=np.einsum('i,j,ijab->ab',c,c,prepared['cross'])
    s+=(1-model.k2**2)*(prepared['initial']-model.k1*prepared['initial_cross'])
    s/=model.sigma_e**2
    logdet=prepared['n']*np.log(model.sigma_e**2)+prepared['segments']*(np.log(1-model.k1**2)-2*np.log(model.q))
    yy=s[0,0]
    if model.sigma_b>0:
        factor=cho_factor(np.eye(prepared['laps'])+model.sigma_b**2*s[1:,1:],lower=True)
        logdet+=2*np.log(np.diag(factor[0])).sum()
        yy-=model.sigma_b**2*s[0,1:]@cho_solve(factor,s[1:,0])
    return float(.5*(prepared['n']*np.log(2*np.pi)+logdet+yy))


def fit(prepared,mean,reference_variance,offset=True):
    n=sum(p['n'] for p in prepared)
    def unpack(x):return LapAR(float(np.exp(x[0])),float(np.sqrt(x[3]*reference_variance)) if offset else 0.,*np.tanh(x[1:3]),mean)
    def loss(x):return sum(nll(unpack(x),p) for p in prepared)/n
    attempts=[]
    for k1,k2,fraction in [(.79,.08,0.),(.65,.15,.1),(.4,.2,.5),(.9,-.1,.01)]:
        x=[np.log(np.sqrt(reference_variance*.4)),np.arctanh(k1),np.arctanh(k2)]+([fraction] if offset else [])
        opt=minimize(loss,x,method='L-BFGS-B',bounds=[(-5,10),(-4,4),(-4,4)]+([(0,100)] if offset else []),
            options={'ftol':1e-12,'gtol':1e-7,'maxiter':500})
        attempts.append(opt)
    valid=[x for x in attempts if x.success and np.isfinite(x.fun)]
    if not valid:raise RuntimeError('No converged lap AR fit')
    best=min(valid,key=lambda x:x.fun);model=unpack(best.x)
    statistics=dict(parameters=asdict(model),phi=model.phi.tolist(),w_sd=float(np.sqrt(model.w_variance)),
        total_sd=float(np.sqrt(model.w_variance+model.sigma_b**2)),nobs=n,nll=float(best.fun),
        attempts=[dict(converged=bool(x.success),nll=float(x.fun),iterations=int(x.nit),parameters=asdict(unpack(x.x))) for x in attempts],
        offset_at_boundary=bool(model.sigma_b<1e-4),uncertainty='No Wald CI: variance boundary and offset/persistence confounding require care')
    return model,statistics
