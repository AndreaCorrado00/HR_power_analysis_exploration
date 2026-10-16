"""Stable output-error models fitted by free-simulation weighted LS."""
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import lfilter
from scipy.stats import t as student_t


def input_delta(target):
    target = np.asarray(target, float)
    if target.ndim != 1 or not len(target) or not np.isfinite(target).all():
        raise ValueError('Need a nonempty finite target vector')
    return np.r_[0., np.diff(target)]


@dataclass
class ResponseModel:
    order: int
    a: list
    b: list
    mean: float

    def response(self, target):
        return lfilter(self.b, self.a, input_delta(target))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        model = cls(**value)
        if (model.order not in (2, 3, 4) or len(model.a) != model.order+1
                or len(model.b) != model.order+1 or model.a[0] != 1
                or not np.isfinite([*model.a, *model.b, model.mean]).all()
                or np.max(np.abs(np.roots(model.a))) >= 1):
            raise ValueError('Invalid or unstable response model')
        return model


def denominator(eta):
    """Schur step-up recursion; |reflection|<1 guarantees stable real poles."""
    a = np.array([1.])
    for k in np.tanh(eta):
        a = np.r_[a, 0.] + k*np.r_[0., a[::-1]]
    return a


def reflection(a):
    a = np.asarray(a, float)
    ks = []
    while len(a) > 1:
        k = a[-1]
        ks.append(k)
        a = (a[:-1]-k*a[:0:-1])/(1-k*k)
    return np.arctanh(np.clip(ks[::-1], -.9999, .9999))


def prepare(segments):
    if not segments:
        raise ValueError('No segments')
    counts = {}
    for s in segments:
        if len(s.target) != len(s.residual) or not np.isfinite(s.residual).all():
            raise ValueError('Finite aligned residuals required')
        counts[s.workout_id] = counts.get(s.workout_id, 0) + len(s.target)
    us = [input_delta(s.target) for s in segments]
    if not any(np.any(u) for u in us):
        raise ValueError('No target transitions: dynamics not identifiable')
    weights = np.concatenate([np.full(len(s.target), 1/np.sqrt(counts[s.workout_id])) for s in segments])
    return us, weights


def natural_jacobian(segments, a, b):
    """Derivatives of r+mean w.r.t. [a1..an,b0..bn,mean]."""
    n = len(a)-1
    rows = []
    for s in segments:
        u = input_delta(s.target)
        r = lfilter(b, a, u)
        columns = []
        for i in range(1, n+1):
            shifted = np.zeros(len(u))
            if i < len(u):
                shifted[i:] = -r[:-i]
            columns.append(lfilter([1.], a, shifted))
        for j in range(n+1):
            shifted = np.zeros(len(u))
            if j == 0:
                shifted[:] = u
            elif j < len(u):
                shifted[j:] = u[:-j]
            columns.append(lfilter([1.], a, shifted))
        rows.append(np.column_stack([*columns, np.ones(len(u))]))
    return np.vstack(rows)


def parameter_statistics(model, segments, weights, residual, loss):
    jac = natural_jacobian(segments, model.a, model.b)*weights[:, None]
    _, sv, vt = np.linalg.svd(jac, full_matrices=False)
    threshold = sv[0]*max(jac.shape)*np.finfo(float).eps
    rank = int(np.sum(sv > threshold))
    k = jac.shape[1]
    ids = list(dict.fromkeys(s.workout_id for s in segments))
    scores = {wid: np.zeros(k) for wid in ids}
    offset = 0
    for s in segments:
        end = offset+len(s.target)
        scores[s.workout_id] += jac[offset:end].T@residual[offset:end]
        offset = end
    covariance = None
    if len(ids) > 1 and rank == k and loss == 'linear':
        bread = (vt.T/sv**2)@vt
        meat = sum(np.outer(v, v) for v in scores.values())
        correction = len(ids)/(len(ids)-1)*(len(residual)-1)/(len(residual)-k)
        covariance = bread@meat@bread*correction
    se = np.sqrt(np.maximum(0, np.diag(covariance))) if covariance is not None else [None]*k
    critical = student_t.ppf(.975, len(ids)-1) if len(ids) > 1 else None
    names = [f'a{i}' for i in range(1, model.order+1)]+[f'b{i}' for i in range(model.order+1)]+['mean_w']
    values = [*model.a[1:], *model.b, model.mean]
    parameters = [dict(name=name, estimate=float(value), standard_error=None if err is None else float(err),
                       ci95=None if err is None else [float(value-critical*err), float(value+critical*err)],
                       unit='W' if name == 'mean_w' else '1')
                  for name, value, err in zip(names, values, se)]
    poles = np.roots(model.a)
    zeros = np.roots(np.trim_zeros(model.b, 'f')) if np.any(model.b) else np.array([])
    distances = [float(np.min(np.abs(zeros-p))) for p in poles] if len(zeros) else []
    return dict(parameters=parameters, clusters=len(ids), jacobian_rank=rank, parameter_count=k,
                jacobian_condition=float(sv[0]/sv[-1]) if sv[-1] > 0 else None,
                spectral_radius=float(np.max(np.abs(poles))),
                poles=[dict(real=float(p.real), imag=float(p.imag), magnitude=float(abs(p))) for p in poles],
                zeros=[dict(real=float(z.real), imag=float(z.imag)) for z in zeros],
                pole_zero_distances=distances,
                minimum_pole_zero_distance=min(distances) if distances else None,
                uncertainty='Local workout-cluster sandwich; t(G-1) intervals. Weak identification and boundary effects not resolved. Huber intervals unavailable.',
                covariance=None if covariance is None else covariance.tolist())


def fit_response(segments, order, *, loss='linear', scale=None, starts=6, max_nfev=250, seed=42):
    if order not in (2, 3, 4) or loss not in ('linear', 'huber') or starts < 1 or max_nfev < 1:
        raise ValueError('Require order 2/3/4, linear/huber loss and positive optimization limits')
    us, weights = prepare(segments)
    y = np.concatenate([s.residual for s in segments])
    scale = max(1., float(np.median(np.abs(y-np.median(y)))*1.4826)) if scale is None else float(scale)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be positive')
    n = order
    cache = {}

    def calculate(x):
        if 'x' not in cache or not np.array_equal(x, cache['x']):
            a, b = denominator(x[:n]), x[n:-1]
            pred = np.concatenate([lfilter(b, a, u) for u in us])+x[-1]
            cache.update(x=x.copy(), a=a, b=b, error=pred-y)
        return cache

    def fun(x):
        error = calculate(x)['error']
        if loss == 'linear':
            return error*weights
        # Transform unweighted residuals BEFORE workout weighting. This keeps
        # the Huber threshold in W and identical across differently sized workouts.
        z = error/scale
        absolute = np.abs(z)
        rho = np.where(absolute <= 1, z*z, 2*absolute-1)
        return np.sign(z)*np.sqrt(rho)*scale*weights

    def jac(x):
        c = calculate(x)
        natural = natural_jacobian(segments, c['a'], c['b'])
        step = 1e-5
        da = np.column_stack([(denominator(x[:n]+np.eye(n)[j]*step)[1:]-
                               denominator(x[:n]-np.eye(n)[j]*step)[1:])/(2*step) for j in range(n)])
        result = np.column_stack([natural[:, :n]@da, natural[:, n:]])
        if loss == 'huber':
            z = np.abs(c['error']/scale)
            factor = np.ones(len(z))
            outside = z > 1
            factor[outside] = 1/np.sqrt(2*z[outside]-1)
            result *= factor[:, None]
        return result*weights[:, None]

    rng = np.random.default_rng(seed)
    results, attempts = [], []
    for attempt in range(starts):
        taus = np.geomspace(1.5, 25., n) if attempt == 0 else np.exp(rng.uniform(np.log(.5), np.log(90), n))
        eta = np.clip(reflection(np.poly(np.exp(-1/taus))), -5., 5.)
        a = denominator(eta)
        linear = natural_jacobian(segments, a, np.zeros(n+1))[:, n:]
        beta = np.linalg.lstsq(linear*weights[:, None], y*weights, rcond=None)[0]
        x0 = np.r_[eta, beta]
        result = least_squares(fun, x0, jac=jac, x_scale='jac',
                               bounds=(np.r_[np.full(n, -7.), np.full(n+2, -np.inf)],
                                       np.r_[np.full(n, 7.), np.full(n+2, np.inf)]),
                               max_nfev=max_nfev, ftol=1e-9, xtol=1e-9, gtol=1e-7)
        results.append(result)
        attempts.append(dict(start=attempt, cost=float(result.cost), success=bool(result.success),
                             nfev=result.nfev, optimality=float(result.optimality), message=result.message))
    converged = [r for r in results if r.success]
    best = min(converged or results, key=lambda r: r.cost)
    model = ResponseModel(n, denominator(best.x[:n]).tolist(), best.x[n:-1].tolist(), float(best.x[-1]))
    weighted_error = calculate(best.x)['error']*weights
    stats = parameter_statistics(model, segments, weights, weighted_error, loss)
    stats.update(converged=bool(best.success), loss=loss, scale_w=scale, objective=float(best.cost),
                 weighted_rmse_w=float(np.sqrt(weighted_error@weighted_error/len({s.workout_id for s in segments}))),
                 attempts=attempts, n_samples=len(y), seed=seed,
                 reflection_boundary=bool(np.any(np.abs(best.x[:n]) > 6.9)))
    return model, stats
