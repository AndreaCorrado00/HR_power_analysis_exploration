"""Causal simulation on explicit 1-s support; no observed HR argument."""
import hashlib
import numpy as np


def stream(segment_id, component, seed=42):
    digest=hashlib.sha256(f'{segment_id}:{component}'.encode()).digest()
    words=np.frombuffer(digest[:16],dtype='<u4').tolist()
    return np.random.default_rng(np.random.SeedSequence([seed,*words]))


def sample_parameters(bundle, segment_id, draws=1000):
    analysis=bundle['analysis']; model=analysis['model']
    if analysis['status']!='estimated' or model is None:
        raise ValueError('HR population unavailable; no arbitrary fallback')
    bounds=bundle['manifest']['parameter_bounds']
    indices=[bounds['keys'].index(k) for k in model['keys']]
    lo=np.asarray(bounds['lower'])[indices]; hi=np.asarray(bounds['upper'])[indices]
    rng=stream(segment_id,'hr')
    candidates=rng.multivariate_normal(model['mean'],model['covariance'],size=20*draws,check_valid='raise')
    valid=np.all((candidates>=lo)&(candidates<=hi),axis=1)
    accepted=candidates[valid][:draws]
    if len(accepted)!=draws:
        raise ValueError('Insufficient admissible HR draws; no band published')
    return accepted, float(valid.mean())


def hr_trajectories(power, theta, intercept, hr0):
    """Vectorized exact existing P1D ZOH solution, dt=1, fractional delay.

    Rows are independent trajectories with fixed K,L,tau. B=A+K*P(0).
    Reset only at an explicitly supplied segment boundary.
    """
    power=np.asarray(power,float);theta=np.asarray(theta,float)
    if power.ndim!=2 or theta.shape!=(len(power),3) or power.shape[1]<2:
        raise ValueError('Expected power (draws,time), theta (draws,3)')
    if not np.isfinite(power).all() or not np.isfinite(theta).all():
        raise ValueError('Nonfinite simulation inputs')
    if np.any(theta[:,0]<=0) or np.any(theta[:,1]<0) or np.any(theta[:,2]<=0):
        raise ValueError('Invalid HR parameter domain')
    gain,delay,tau=theta.T
    n=power.shape[1]; t=np.arange(n)
    p0=power[:,0]
    u=power-p0[:,None]
    state=np.zeros_like(u)
    decay=-np.expm1(-1/tau)
    for i in range(1,n):
        state[:,i]=state[:,i-1]+(u[:,i-1]-state[:,i-1])*decay
    # Process rows to avoid allocating several draws x time index matrices.
    out=np.empty_like(power)
    for j in range(len(power)):
        shifted=t-delay[j]
        idx=np.floor(shifted).astype(int)
        safe=np.maximum(idx,0)
        duration=np.maximum(shifted-safe,0)
        response=state[j,safe]+(u[j,safe]-state[j,safe])*(-np.expm1(-duration/tau[j]))
        base=hr0+(intercept+gain[j]*p0[j]-hr0)*(-np.expm1(-t/tau[j]))
        out[j]=base+gain[j]*np.where(idx<0,0.,response)
    return out


def metrics(observed, predicted, lower=None, upper=None):
    observed=np.asarray(observed,float);predicted=np.asarray(predicted,float)
    valid=np.isfinite(observed)&np.isfinite(predicted)
    if not valid.any(): return dict(N=0,MAE=None,RMSE=None,bias=None,residual_sd=None,coverage=None,width=None)
    e=observed[valid]-predicted[valid]
    return dict(N=int(valid.sum()),MAE=float(abs(e).mean()),RMSE=float(np.sqrt(np.mean(e**2))),
        bias=float(e.mean()),residual_sd=float(e.std(ddof=1)) if len(e)>1 else None,
        coverage=float(np.mean((observed[valid]>=lower[valid])&(observed[valid]<=upper[valid]))) if lower is not None else None,
        width=float(np.mean(upper[valid]-lower[valid])) if lower is not None else None)
