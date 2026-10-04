"""User-specified P1D, conditional on equilibrium at the first observation."""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

KEYS = ('K', 'L', 'tau')
METADATA = {
    'id': 'p1d', 'version': '1.0.0', 'name': 'P1D · primo ordine + ritardo',
    'parameters': [{'key': k, 'unit': u} for k, u in zip(KEYS, ['bpm/W', 's', 's'])],
    'equation': 'tau dx/dt + x = K (P(t-L)-P0); HRhat = HR0+x',
    'source': 'P1D richiesto nel protocollo utente; nessuna replica bibliografica rivendicata',
    'initial_conditions': 'P0=P(0), HR0=HR(0), x(0)=0; P(t<0)=P0; equilibrio iniziale assunto',
    'input_reconstruction': 'zero-order hold, integrazione esatta; ritardo continuo in secondi',
    'uncertainty': 'SSE/(N-3) inv(J.T J); CI95 Wald non troncati; condizionati a P0 e HR0',
    'residual_conventions': 'e=HR-HRhat; SD ddof=1; ACF1=sum(centered[1:]*centered[:-1])/sum(centered**2); lag in campioni',
    'multistart_conventions': 'PCG64 seed; primo start [0.3,5,45] clipped; altri log-uniformi K/tau e uniformi L nei bounds; selezione SSE minimo',
}


def default_config():
    return {'lower': [1e-6, 0., .01], 'upper': [5., 120., 1800.],
            'n_starts': 8, 'seed': 42, 'max_nfev': 500,
            'method': 'trf', 'loss': 'linear', 'jac': '3-point',
            'ftol': 1e-8, 'xtol': 1e-8, 'gtol': 1e-8, 'x_scale': 'jac'}


def validate_config(config):
    c = default_config()
    if set(config) - set(c):
        raise ValueError('Impostazioni modello sconosciute')
    c.update(config)
    lo, hi = np.asarray(c['lower'], float), np.asarray(c['upper'], float)
    if lo.shape != (3,) or hi.shape != (3,) or not np.isfinite([lo,hi]).all():
        raise ValueError('Bounds: servono tre limiti inferiori e superiori finiti')
    if np.any(lo >= hi) or lo[0] <= 0 or lo[1] < 0 or lo[2] <= 0:
        raise ValueError('Bounds non validi: K>0, L>=0, tau>0 e lower<upper')
    for key, low, high in [('n_starts', 2, 64), ('max_nfev', 10, 10000), ('seed', 0, 2**32-1)]:
        if not isinstance(c[key], int) or not low <= c[key] <= high:
            raise ValueError(f'{key}: intero tra {low} e {high}')
    for key in ['method', 'loss', 'jac', 'x_scale', 'ftol', 'xtol', 'gtol']:
        if c[key] != default_config()[key]:
            raise ValueError(f'{key} è fissato dal protocollo P1D v1')
    return c


def simulate(t, power, hr0, theta):
    """Exact ZOH response at arbitrary observation times, including fractional L."""
    t, power = np.asarray(t, float), np.asarray(power, float)
    K, L, tau = theta
    u = power - power[0]
    # Solve the undelayed system at input knots, then evaluate at t-L.
    decay = -np.expm1(-np.diff(t)/tau)
    state = np.zeros(len(t))
    for i in range(1, len(t)):
        state[i] = state[i-1] + (u[i-1] - state[i-1]) * decay[i-1]
    delayed_t = t - L
    idx = np.searchsorted(t, delayed_t, side='right') - 1
    idx_safe = np.maximum(idx, 0)
    duration = np.maximum(delayed_t - t[idx_safe], 0)
    out = state[idx_safe] + (u[idx_safe]-state[idx_safe]) * (-np.expm1(-duration/tau))
    return hr0 + K * np.where(idx < 0, 0., out)


def fit(t, power, hr, config):
    c = validate_config(config)
    t, power, hr = (np.asarray(v, float) for v in (t, power, hr))
    if t.ndim != 1 or len(t) <= 3 or power.shape != t.shape or hr.shape != t.shape:
        raise ValueError('Servono almeno 4 osservazioni con dimensioni coerenti')
    if not np.isfinite([t,power,hr]).all() or np.any(np.diff(t) <= 0):
        raise ValueError('Campioni mancanti/non finiti o tempi non strettamente crescenti')
    t = t - t[0]
    lo, hi = np.asarray(c['lower']), np.asarray(c['upper'])
    rng = np.random.default_rng(c['seed'])
    initial = []
    for i in range(c['n_starts']):
        # Interior points: broad log coverage for positive gain/time constant.
        q = rng.uniform(.05, .95, 3)
        start = lo + q*(hi-lo)
        for j in (0,2):
            start[j] = np.exp(np.log(lo[j]) + q[j]*np.log(hi[j]/lo[j]))
        if i == 0:
            start = np.clip([.3, 5., 45.], lo+1e-6*(hi-lo), hi-1e-6*(hi-lo))
        initial.append(start)
    solutions, starts = [], []
    residual = lambda theta: hr - simulate(t, power, hr[0], theta)
    for start in initial:
        opt = least_squares(residual, start, bounds=(lo,hi), **{
            key: c[key] for key in ['method','loss','jac','ftol','xtol','gtol','x_scale','max_nfev']})
        solutions.append(opt)
        starts.append({'initial': start.tolist(), 'theta': opt.x.tolist(),
                       'SSE': float(opt.fun@opt.fun), 'success': bool(opt.success),
                       'status': int(opt.status), 'nfev': int(opt.nfev)})
    opt = min(solutions, key=lambda o: float(o.fun@o.fun))
    e = opt.fun
    sse = float(e@e)
    centered = e - e.mean()
    denom = float(centered@centered)
    acf = float(centered[1:]@centered[:-1]/denom) if denom > 1e-20 else None
    _, singular, vt = np.linalg.svd(opt.jac, full_matrices=False)
    tolerance = np.finfo(float).eps * max(opt.jac.shape) * singular[0]
    rank = int(np.sum(singular > tolerance))
    cond = float(singular[0]/singular[-1]) if rank == 3 else None
    cov = ((vt.T / singular**2) @ vt) * sse/(len(t)-3) if rank == 3 else None
    se = np.sqrt(np.maximum(np.diag(cov), 0)) if cov is not None else [None]*3
    warnings = []
    if rank < 3: warnings.append('rank_deficient')
    if cond is not None and cond > 1e8: warnings.append('ill_conditioned')
    active = (opt.active_mask != 0) | (np.minimum(opt.x-lo,hi-opt.x)/(hi-lo) < 1e-5)
    if active.any(): warnings.append('at_bounds')
    if not opt.success: warnings.append('optimizer_not_converged')
    if np.ptp(power) < 1e-10: warnings.append('constant_power')
    if acf is not None and abs(acf) > .5: warnings.append('autocorrelated_residuals')
    dt = np.diff(t)
    if np.max(dt) > 1.5*np.median(dt): warnings.append('recording_gaps')
    if not np.allclose(dt, np.median(dt), rtol=.01): warnings.append('irregular_sampling')
    equivalent = [o for o in solutions if float(o.fun@o.fun) <= sse + max(1e-8, sse*.01)]
    stable = all(np.allclose(o.x, opt.x, rtol=.05, atol=.01) for o in equivalent)
    all_agree = all(o.success and np.allclose(o.x, opt.x, rtol=.05, atol=.01) for o in solutions)
    if not stable: warnings.append('equivalent_predictions_different_parameters')
    if not all_agree: warnings.append('multistart_disagreement')
    parameters = {}
    for i, k in enumerate(KEYS):
        estimate = float(opt.x[i])
        err = None if se[i] is None else float(se[i])
        parameters[k] = {'estimate': estimate, 'se': err,
                         'ci95': None if err is None else [estimate-1.96*err,estimate+1.96*err],
                         'rse_pct': None if err is None or abs(estimate) < 1e-8 else 100*err/abs(estimate),
                         'at_bound': bool(active[i])}
    return {'parameters': parameters, 'metrics': {'RMSE': float(np.sqrt(sse/len(e))),
            'SSE': sse, 'residual_mean': float(e.mean()), 'residual_sd': float(e.std(ddof=1)),
            'residual_autocorrelation_lag1': acf},
            'optimizer': {'success': bool(opt.success), 'status': int(opt.status),
                          'message': str(opt.message), 'nfev': int(opt.nfev)},
            'uncertainty': {'rank': rank, 'jacobian_condition': cond,
                            'covariance': None if cov is None else cov.tolist(),
                            'sigma2': sse/(len(t)-3), 'N': len(t), 'p': 3},
            'initial_conditions': {'P0': float(power[0]), 'HR0': float(hr[0])},
            'starts': starts, 'all_starts_agree': all_agree, 'warnings': warnings,
            'series': {'time': t.tolist(), 'power': power.tolist(), 'observed': hr.tolist(),
                       'predicted': (hr-e).tolist(), 'residual': e.tolist()}}
