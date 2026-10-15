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
