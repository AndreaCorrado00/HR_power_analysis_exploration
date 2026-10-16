"""Autonomous conditional OLS fit: no splitting, plotting or validation here."""
from dataclasses import asdict, dataclass, field
import numpy as np


@dataclass
class ARModel:
    p: int
    intercept: float
    coefficients: list[float]
    hold_back: int
    nobs: int = 0
    sigma2: float = 0.
    aic: float = 0.
    bic: float = 0.
    condition_number: float = 0.
    standard_errors: list[float] = field(default_factory=list)

    @property
    def spectral_radius(self):
        return float(np.max(np.abs(np.roots(np.r_[1., -np.asarray(self.coefficients)]))))

    @property
    def stable(self):
        return self.spectral_radius < 1.

    def to_dict(self):
        return {**asdict(self), 'stable': self.stable, 'spectral_radius': self.spectral_radius}

    @classmethod
    def from_dict(cls, value):
        return cls(**{key: val for key, val in value.items() if key in cls.__dataclass_fields__})


def design_matrix(segments, p, hold_back):
    if not isinstance(p, int) or p < 1 or hold_back < p:
        raise ValueError('Require integer 1 <= p <= hold_back')
    xs, ys = [], []
    for segment in segments:
        y = np.asarray(segment.residual, float)
        if not np.isfinite(y).all():
            raise ValueError('AR input segments must be finite')
        if len(y) <= hold_back:
            continue
        xs.append(np.column_stack([np.ones(len(y)-hold_back)] +
                                  [y[hold_back-j:len(y)-j] for j in range(1, p+1)]))
        ys.append(y[hold_back:])
    if not xs:
        raise ValueError('No segment has enough history')
    return np.vstack(xs), np.concatenate(ys)


def fit_ar(segments, p, hold_back=None):
    """Estimate shared c, phi and conditional Gaussian ICs on common support.

    Stacking regression rows is permitted; constructing lags across segments is not.
    OLS standard errors assume iid homoskedastic innovations (diagnostic only).
    """
    hold_back = p if hold_back is None else hold_back
    x, y = design_matrix(segments, p, hold_back)
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != p+1 or len(y) <= p+2:
        raise ValueError('AR fit is not identifiable: insufficient data or rank')
    errors = y-x@beta
    sse = float(errors@errors)
    sigma2 = sse/len(y)
    if sigma2 <= np.finfo(float).tiny:
        raise ValueError('Degenerate innovation variance; Gaussian ICs undefined')
    minus2loglik = len(y)*(np.log(2*np.pi*sigma2)+1)
    k = p+2  # p lags, intercept, estimated innovation variance
    _, sv, vt = np.linalg.svd(x, full_matrices=False)
    covariance = (vt.T/sv**2)@vt * (sse/(len(y)-p-1))
    return ARModel(p, float(beta[0]), beta[1:].tolist(), hold_back, len(y), sigma2,
                   float(minus2loglik+2*k), float(minus2loglik+np.log(len(y))*k),
                   float(singular[0]/singular[-1]), np.sqrt(np.diag(covariance)).tolist())


import hashlib

def stationary_state(model):
    """Exact Gaussian state moments from the discrete Lyapunov equation."""
    phi = np.asarray(model.coefficients, float)
    if (len(phi) != model.p or model.p < 1 or not np.isfinite(phi).all()
            or not np.isfinite(model.intercept) or not np.isfinite(model.sigma2)
            or model.sigma2 <= 0 or not model.stable):
        raise ValueError('Stationary simulation needs a stable AR with positive finite variance')
    transition = np.zeros((model.p, model.p))
    transition[0] = phi
    transition[1:, :-1] = np.eye(model.p-1)
    noise = np.zeros_like(transition)
    noise[0,0] = model.sigma2
    covariance = np.linalg.solve(np.eye(model.p**2)-np.kron(transition, transition),
                                 noise.ravel(order='F')).reshape((model.p,model.p), order='F')
    covariance = (covariance+covariance.T)/2
    mean = np.full(model.p, model.intercept/(1-phi.sum()))
    return mean, covariance


def simulate_residual(model, n, paths, rng):
    """All n samples simulated, including the start; no teacher forcing."""
    if n < 1 or paths < 1:
        raise ValueError('Need positive sample and trajectory counts')
    mean, covariance = stationary_state(model)
    history = rng.multivariate_normal(mean, covariance, size=paths, check_valid='raise')
    innovations = rng.normal(0, np.sqrt(model.sigma2), size=(paths,n))
    values = np.empty((paths,n))
    phi = np.asarray(model.coefficients)
    for t in range(n):
        values[:,t] = model.intercept+history@phi+innovations[:,t]
        history[:,1:] = history[:,:-1].copy()
        history[:,0] = values[:,t]
    return values


def simulate_workout(model, segments, seed=42, paths=100):
    if not segments or len({s.workout_id for s in segments}) != 1 or seed < 0:
        raise ValueError('Need one nonempty workout and a nonnegative seed')
    # Stable across input ordering, processes, and Python hash randomization.
    digest = hashlib.sha256(segments[0].workout_id.encode()).digest()
    words = [int.from_bytes(digest[i:i+4], 'little') for i in range(0,16,4)]
    rng = np.random.default_rng(np.random.SeedSequence([seed, *words]))
    return [simulate_residual(model, len(s.target), paths, rng) for s in segments]


def pooled_acf(parts, lag):
    """Biased ACF pooled by within-segment energy; never cross a real gap."""
    numerator, denominator = None, None
    for part in parts:
        x = np.atleast_2d(part)
        if x.shape[1] <= lag:
            continue
        x = x-x.mean(axis=1, keepdims=True)
        num = np.sum(x[:,:-lag]*x[:,lag:], axis=1)
        den = np.sum(x*x, axis=1)
        numerator = num if numerator is None else numerator+num
        denominator = den if denominator is None else denominator+den
    if numerator is None:
        return None
    return np.divide(numerator, denominator, out=np.full_like(numerator,np.nan), where=denominator > 0)


