"""Gaussian QML GARCH(1,1) on frozen AR innovations (Bollerslev, 1986)."""
from dataclasses import dataclass,asdict
import numpy as np
from scipy.signal import lfilter
from scipy.optimize import minimize
from scipy.stats import norm


@dataclass(frozen=True)
class GARCH11:
    omega: float
    alpha: float
    beta: float

    def __post_init__(self):
        if (not np.isfinite([self.omega,self.alpha,self.beta]).all() or self.omega<=0
                or min(self.alpha,self.beta)<0 or self.alpha+self.beta>=1):
            raise ValueError('Require omega>0, alpha,beta>=0 and alpha+beta<1')

    @property
    def unconditional_variance(self):
        return self.omega/(1-self.alpha-self.beta)

    def variance(self,errors):
        e = np.asarray(errors,float)
        if e.ndim!=1 or not len(e) or not np.isfinite(e).all():
            raise ValueError('Finite, nonempty continuous innovations required')
        initial = self.unconditional_variance
        inputs = self.omega+self.alpha*np.r_[initial,e[:-1]**2]
        return lfilter([1.],[1.,-self.beta],inputs,zi=[self.beta*initial])[0]

    def to_dict(self):
        return {**asdict(self),'unconditional_variance_w2':self.unconditional_variance,
                'persistence':self.alpha+self.beta}


def objective(theta,parts):
    """Mean Gaussian negative log likelihood and analytic gradient, scaled units."""
    omega,alpha,beta = theta
    if omega<=0 or alpha<0 or beta<0 or alpha+beta>=1:
        return 1e20,np.zeros(3)
    model = GARCH11(*theta)
    h0 = model.unconditional_variance
    d0 = np.array([1/(1-alpha-beta),omega/(1-alpha-beta)**2,omega/(1-alpha-beta)**2])
    total,gradient,n = 0.,np.zeros(3),0
    for e in parts:
        h = model.variance(e)
        total += .5*np.sum(np.log(2*np.pi*h)+e*e/h)
        drivers = np.column_stack([np.ones(len(e)),np.r_[0,e[:-1]**2],np.r_[0,h[:-1]]])
        drivers[0] = d0
        derivatives = lfilter([1.],[1.,-beta],drivers,axis=0)
        gradient += np.sum((.5*(1-e*e/h)/h)[:,None]*derivatives,axis=0)
        n += len(e)
    return float(total/n),gradient/n


def fit_garch(parts,clusters=None):
    if not parts or any(len(x)<1 or not np.isfinite(x).all() for x in parts):
        raise ValueError('Finite nonempty segments required')
    n = sum(len(x) for x in parts)
    scale = sum(float(x@x) for x in parts)/n
    if n<100 or scale<=1e-12:
        raise ValueError('Insufficient or degenerate training innovations')
    normalized = [np.asarray(x,float)/np.sqrt(scale) for x in parts]
    constraint = {'type':'ineq','fun':lambda x:1-1e-6-x[1]-x[2],
                  'jac':lambda x:np.array([0.,-1.,-1.])}
    attempts,results = [],[]
    for alpha,beta in [(0.05,.9),(.15,.75),(.35,.4),(.6,.05),(.05,.2),(.25,.7)]:
        opt = minimize(objective,[1-alpha-beta,alpha,beta],args=(normalized,),jac=True,
            method='SLSQP',bounds=[(1e-8,None),(0,1-1e-6),(0,1-1e-6)],
            constraints=constraint,options={'ftol':1e-10,'maxiter':350})
        ok = bool(opt.success and np.isfinite(opt.fun) and opt.x[0]>0
                  and min(opt.x[1:])>=0 and opt.x[1:].sum()<1)
        attempts.append(dict(initial_alpha=alpha,initial_beta=beta,converged=ok,
            nll_scaled=float(opt.fun),iterations=int(opt.nit),message=str(opt.message),parameters=opt.x.tolist()))
        if ok:
            results.append(opt)
    if not results:
        raise RuntimeError('No converged GARCH fit; existing artifacts not replaced')
    best = min(results,key=lambda x:x.fun)
    theta = best.x
    model = GARCH11(float(theta[0]*scale),float(theta[1]),float(theta[2]))
    warnings = []
    if model.alpha+model.beta>.98:
        warnings.append('High persistence: sensitivity to initialization and long forecast horizon')
    if min(theta[1:])<1e-5 or 1-theta[1:].sum()<1e-5:
        warnings.append('Estimate near constraint boundary; local Wald inference unreliable')
    stats = dict(converged=True,nobs=n,scale_w2=scale,attempts=attempts,
        nll=float(best.fun+.5*np.log(scale)),warnings=warnings,parameters=[])
    # Local cluster sandwich conditional on the frozen mean model; no iid SE claim.
    covariance = None
    if clusters is not None and len(clusters)==len(parts) and len(set(clusters))>=4 and not warnings:
        hessian = np.empty((3,3))
        for j in range(3):
            step = 1e-5*max(abs(theta[j]),.01)
            delta = np.eye(3)[j]*step
            hessian[:,j] = (objective(theta+delta,normalized)[1]-objective(theta-delta,normalized)[1])/(2*step)*n
        hessian = (hessian+hessian.T)/2
        stats['hessian_condition'] = float(np.linalg.cond(hessian))
        if np.linalg.eigvalsh(hessian).min()>0 and stats['hessian_condition']<1e12:
            scores = []
            for cluster in dict.fromkeys(clusters):
                group = [x for x,c in zip(normalized,clusters) if c==cluster]
                scores.append(objective(theta,group)[1]*sum(map(len,group)))
            scores = np.asarray(scores)
            inv = np.linalg.inv(hessian)
            covariance = inv@(scores.T@scores)@inv*len(scores)/(len(scores)-1)
            transform = np.diag([scale,1,1])
            covariance = transform@covariance@transform
        else:
            warnings.append('Ill-conditioned curvature; uncertainty not reported')
    for j,(name,value,unit) in enumerate(zip(['omega','alpha','beta'],[model.omega,model.alpha,model.beta],['W²','1','1'])):
        se = float(np.sqrt(max(0,covariance[j,j]))) if covariance is not None else None
        stats['parameters'].append(dict(name=name,estimate=value,unit=unit,se_cluster=se,
            ci95_local=[value-1.96*se,value+1.96*se] if se is not None else None))
    return model,stats


def burn_in(model,ar):
    rho = max(model.alpha+model.beta,ar.spectral_radius)
    needed = max(2000,int(np.ceil(np.log(1e-8)/np.log(rho)))) if rho>0 else 2000
    if needed>100000:
        raise ValueError('Stationary burn-in exceeds 100000 samples; simulation not reliable enough')
    return needed


def simulate(model,ar,n,paths,rng):
    """Joint AR-GARCH warm-up, then autonomous Gaussian-innovation trajectories."""
    if n<1 or paths<1 or not ar.stable:
        raise ValueError('Positive sizes and stable AR required')
    warm = burn_in(model,ar)
    history = np.full((paths,ar.p),ar.intercept/(1-sum(ar.coefficients)))
    h = np.full(paths,model.unconditional_variance)
    out = np.empty((paths,n))
    for i in range(warm+n):
        epsilon = np.sqrt(h)*rng.standard_normal(paths)
        value = ar.intercept+history@ar.coefficients+epsilon
        h = model.omega+model.alpha*epsilon**2+model.beta*h
        history[:,1:] = history[:,:-1].copy()
        history[:,0] = value
        if i>=warm:
            out[:,i-warm] = value
    return out


def interval_metrics(errors,low,high):
    width = high-low
    score = width+10*np.maximum(low-errors,0)+10*np.maximum(errors-high,0)
    return dict(n=len(errors),coverage80=float(np.mean((errors>=low)&(errors<=high))),
        width80_w=float(np.mean(width)),interval_score80_w=float(np.mean(score)))


def conditional_metrics(errors,variance):
    half = norm.ppf(.9)*np.sqrt(variance)
    return {**interval_metrics(errors,-half,half),
        'nll':float(np.mean(.5*(np.log(2*np.pi*variance)+errors**2/variance))),
        'standardized_mean':float(np.mean(errors/np.sqrt(variance))),
        'standardized_variance':float(np.var(errors/np.sqrt(variance),ddof=1))}
