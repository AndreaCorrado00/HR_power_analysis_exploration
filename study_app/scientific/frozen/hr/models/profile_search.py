"""Deterministic P1D profile grid; gains solved exactly at each nonlinear pair."""
import numpy as np


def bounded_linear_pair(f, g, target, lo, hi):
    """Box-constrained two-column least squares, including singular designs.

    Evaluate the unconstrained solution and minima on all four box edges.
    Edge candidates also cover corners and rank-deficient cases.
    """
    ff = np.sum(f*f, axis=1)
    gg = float(g@g)
    fg, fy, gy = f@g, f@target, float(g@target)
    def gain(numerator):
        return np.clip(np.divide(numerator, ff, out=np.full(len(f),lo[0]), where=ff>0),lo[0],hi[0])
    pairs = []
    for b in (lo[3],hi[3]):
        pairs.append((gain(fy-b*fg), np.full(len(f),b)))
    for k in (lo[0],hi[0]):
        b = np.clip((gy-k*fg)/gg,lo[3],hi[3]) if gg>0 else np.full(len(f),lo[3])
        pairs.append((np.full(len(f),k),b))
    determinant = ff*gg-fg*fg
    regular = determinant > np.finfo(float).eps*16*np.maximum(ff*gg,1e-300)
    k = np.divide(fy*gg-gy*fg,determinant,out=np.zeros(len(f)),where=regular)
    b = np.divide(gy*ff-fy*fg,determinant,out=np.zeros(len(f)),where=regular)
    interior = regular & (k>=lo[0]) & (k<=hi[0]) & (b>=lo[3]) & (b<=hi[3])
    pairs.append((k,b))
    errors = np.array([np.sum((target[None,:]-k[:,None]*f-b[:,None]*g)**2,axis=1) for k,b in pairs])
    errors[-1,~interior] = np.inf
    best = np.argmin(errors,axis=0)
    col = np.arange(len(f))
    return np.array([p[0] for p in pairs])[best,col],np.array([p[1] for p in pairs])[best,col],errors[best,col]


def candidates(t, power, hr, p0, hr0, lo, hi, config):
    delays = np.linspace(lo[1], hi[1], config['grid_delay_points']) if hi[1] > lo[1] else np.array([lo[1]])
    taus = np.geomspace(lo[2], hi[2], config['grid_tau_points'])
    u = power-p0
    delayed = t[None, :]-delays[:, None]
    idx = np.searchsorted(t, delayed, side='right')-1
    safe = np.maximum(idx, 0)
    duration = np.maximum(delayed-t[safe], 0.)
    target = hr-hr0
    scores, vectors = [], []
    for tau in taus:
        state = np.zeros(len(t))
        decay = -np.expm1(-np.diff(t)/tau)
        for i in range(1, len(t)):
            state[i] = state[i-1]+(u[i-1]-state[i-1])*decay[i-1]
        f = np.where(idx < 0, 0., state[safe]+(u[safe]-state[safe])*(-np.expm1(-duration/tau)))
        if config['initialization_mode'] == 'estimated_equilibrium':
            g = -np.expm1(-t/tau)
            gains, baselines, error = bounded_linear_pair(f,g,hr-hr0*np.exp(-t/tau),lo,hi)
            vectors.extend(np.column_stack([gains,delays,np.full(len(delays),tau),baselines]))
        else:
            denominator = np.sum(f*f, axis=1)
            gains = np.clip(np.divide(f@target, denominator, out=np.full(len(delays), lo[0]), where=denominator>0), lo[0], hi[0])
            residual = target[None, :]-gains[:, None]*f
            error = np.sum(residual*residual, axis=1)
            vectors.extend(np.column_stack([gains, delays, np.full(len(delays), tau)]))
        scores.extend(error.tolist())
    # Separate grid neighborhoods before refining, rather than spend every start
    # on adjacent cells of the best sampled basin. Selection is deterministic.
    selected, cells = [], []
    for index in np.argsort(scores, kind='stable'):
        cell = np.array([index % len(delays)/max(1, len(delays)-1), index // len(delays)/(len(taus)-1)])
        if any(np.linalg.norm(cell-other) < .05 for other in cells):
            continue
        selected.append(vectors[index])
        cells.append(cell)
        if len(selected) >= config['grid_refinements']:
            break
    return selected, {'grid_evaluations': len(scores), 'grid_best_SSE': min(scores),
                      'grid_delay_points_effective': len(delays), 'grid_tau_points': len(taus),
                      'candidate_separation_normalized': .05}
