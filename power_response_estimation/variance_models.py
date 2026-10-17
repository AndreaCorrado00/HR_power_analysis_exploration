"""Variance targeting and exploratory target-context Gaussian variance."""
from dataclasses import replace
import numpy as np
from scipy.optimize import minimize
from .garch import GARCH11, objective
from .ar import stationary_state


def context_features(target):
    target = np.asarray(target, float)
    transient = np.zeros(len(target))
    jump, age = 0., 0
    for i in range(1, len(target)):
        if target[i] != target[i-1]:
            jump, age = abs(target[i]-target[i-1]), 0
        else:
            age += 1
        transient[i] = jump/100*np.exp(-age/30)
    return np.column_stack([np.ones(len(target)), target/100, transient])


def targeted_objective(theta, parts):
    a, b = theta
    value, gradient = objective([1-a-b, a, b], parts)
    return value, gradient[1:]-gradient[0]


def fit_targeted(parts):
    v = sum(x@x for x in parts)/sum(map(len, parts))
    normalized = [x/np.sqrt(v) for x in parts]
    attempts = [minimize(targeted_objective, start, args=(normalized,), jac=True,
        method='SLSQP', bounds=[(0, .999999)]*2,
        constraints={'type':'ineq','fun':lambda x:.999999-x.sum()},
        options={'ftol':1e-10,'maxiter':350})
        for start in [[.05,.9],[.15,.75],[.35,.4],[.6,.05],[.05,.2]]]
    valid = [x for x in attempts if x.success and np.isfinite(x.fun)]
    if not valid:
        raise RuntimeError('Variance targeting failed')
    best = min(valid, key=lambda x:x.fun)
    a,b = best.x
    return GARCH11(float((1-a-b)*v),float(a),float(b)), dict(
        converged=True, variance_target_w2=float(v), nobs=sum(map(len,parts)),
        nll=float(best.fun+.5*np.log(v)), uncertainty='Not estimated; frozen mean model',
        attempts=[dict(success=bool(x.success),nll_scaled=float(x.fun),parameters=x.x.tolist()) for x in attempts])


def fit_context(features, parts, clusters):
    x, e = np.concatenate(features), np.concatenate(parts)
    def loss(beta):
        eta = x@beta
        ratio = e*e*np.exp(-eta)
        return .5*np.mean(np.log(2*np.pi)+eta+ratio), .5*x.T@(1-ratio)/len(e)
    opt = minimize(loss,[np.log(np.mean(e*e)),0,0],jac=True,method='BFGS',options={'gtol':1e-7})
    if not opt.success:
        raise RuntimeError(str(opt.message))
    return opt.x, dict(converged=True,nobs=len(e),nll=float(opt.fun),
        training_workouts=len(set(clusters)),uncertainty='Not estimated; exploratory context specification')


def simulate_context(ar, h, z, initial):
    mu,cov = stationary_state(replace(ar,sigma2=float(h[0])))
    history = mu+initial@np.linalg.cholesky(cov).T
    out = np.empty_like(z)
    for i in range(len(h)):
        value = ar.intercept+history@ar.coefficients+np.sqrt(h[i])*z[:,i]
        history[:,1:] = history[:,:-1].copy()
        history[:,0] = value
        out[:,i] = value
    return out
