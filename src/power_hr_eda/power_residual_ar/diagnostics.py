"""Per-segment biased ACF and Yule-Walker PACF; never concatenate signals."""
from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd


def acf_pacf(values, max_lag):
    values = np.asarray(values, float)
    if max_lag < 1 or max_lag >= len(values) or not np.isfinite(values).all():
        raise ValueError('ACF/PACF require finite data and 1 <= lag < n')
    x = values-values.mean()
    energy = x@x
    acf = np.full(max_lag+1, np.nan)
    pacf = np.full(max_lag+1, np.nan)
    acf[0] = pacf[0] = 1.
    if energy <= np.finfo(float).eps*max(1., float(values@values)):
        return acf, pacf
    acf[1:] = [x[:-k]@x[k:]/energy for k in range(1, max_lag+1)]
    phi = np.empty(0)
    variance = 1.
    # Levinson-Durbin recursion on autocovariances with common denominator n.
    for k in range(1, max_lag+1):
        if variance <= np.finfo(float).eps:
            break
        reflection = (acf[k]-phi@acf[1:k][::-1])/variance
        pacf[k] = reflection
        phi = np.r_[phi-reflection*phi[::-1], reflection]
        variance *= 1-reflection**2
    return acf, pacf


def quantile(values, q, axis=0):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)  # unavailable long lags stay NaN
        return np.nanquantile(values, q, axis=axis)


def curves_for_segments(segments, max_lag):
    meta, acfs, pacfs = [], [], []
    for segment in segments:
        n = len(segment.residual)
        lag = min(max_lag, n//2-1)
        row = dict(workout_id=segment.workout_id, segment_id=segment.segment_id, n=n,
                   start_s=float(segment.time[0]), end_s=float(segment.time[-1]),
                   target_w=float(segment.target[0]), mean_residual_w=float(segment.residual.mean()),
                   sd_residual_w=float(segment.residual.std()), available_lag=max(0, lag),
                   status='too_short' if lag < 1 else 'ok')
        a, p = np.full(max_lag+1, np.nan), np.full(max_lag+1, np.nan)
        if lag >= 1:
            a0, p0 = acf_pacf(segment.residual, lag)
            a[:lag+1], p[:lag+1] = a0, p0
            if not np.isfinite(a[1]):
                row['status'] = 'constant'
        meta.append(row)
        acfs.append(a)
        pacfs.append(p)
    if not meta:
        raise ValueError('No valid segments for diagnostics')
    return pd.DataFrame(meta), np.asarray(acfs), np.asarray(pacfs)


def summarize_curves(meta, acfs, pacfs, max_order):
    """Equal workout weight. Nominal white-noise bounds guide, not decide, p."""
    workout_acfs, workout_pacfs, workout_ratios = [], [], []
    for wid in meta.workout_id.unique():
        mask = meta.workout_id.eq(wid).to_numpy() & meta.status.eq('ok').to_numpy()
        if not mask.any():
            continue
        workout_acfs.append(quantile(acfs[mask], .5))
        workout_pacfs.append(quantile(pacfs[mask], .5))
        bounds = 1.96/np.sqrt(meta.loc[mask, 'n'].to_numpy())
        workout_ratios.append(quantile(np.abs(pacfs[mask])/bounds[:, None], .5))
    if not workout_acfs:
        raise ValueError('No nonconstant segment available for ACF/PACF')
    aa, pp, rr = map(np.asarray, (workout_acfs, workout_pacfs, workout_ratios))
    summary = pd.DataFrame(dict(lag_s=np.arange(acfs.shape[1]),
                               acf_median=quantile(aa, .5), acf_p10=quantile(aa, .1), acf_p90=quantile(aa, .9),
                               pacf_median=quantile(pp, .5), pacf_p10=quantile(pp, .1), pacf_p90=quantile(pp, .9),
                               pacf_nominal_ratio=quantile(rr, .5),
                               segments_available=np.isfinite(pacfs).sum(axis=0),
                               workouts_available=np.isfinite(pp).sum(axis=0)))
    significant = summary.query('lag_s >= 1 and lag_s <= @max_order and pacf_nominal_ratio >= 1').lag_s
    knee = int(significant.max()) if len(significant) else 1
    candidates = sorted(set([1, knee, min(max_order, knee+1)]))
    return summary, dict(orders=candidates, pacf_last_supported_lag=knee,
                         rule='AR(1) + last median PACF/bound ratio >= 1 + next lag, capped at max_order',
                         caution='Exploratory heuristic, not a hypothesis test. Inspect plots; select on validation only.')


def diagnose(segments, output, max_lag=60, max_order=20):
    from .plots import acf_summary_plot, workout_acf_plots
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    meta, acfs, pacfs = curves_for_segments(segments, max_lag)
    summary, candidates = summarize_curves(meta, acfs, pacfs, max_order)
    meta.to_csv(output/'segments.csv', index=False)
    summary.to_csv(output/'acf_pacf_summary.csv', index=False)
    np.savez_compressed(output/'segment_curves.npz', acf=acfs, pacf=pacfs, lag_s=np.arange(max_lag+1))
    (output/'candidates.json').write_text(json.dumps(candidates, indent=2), encoding='utf-8')
    acf_summary_plot(summary, output/'acf_pacf.png', 'Training: residuo P reale - P target')
    workout_acf_plots(meta, acfs, pacfs, output/'by_workout')
    return candidates
