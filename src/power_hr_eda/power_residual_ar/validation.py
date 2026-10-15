"""Evaluate fixed AR coefficients on unseen workouts and causal rolling origins."""
import numpy as np
import pandas as pd


def forecast_segment(model, segment, horizon=1, hold_back=None):
    hold_back = model.hold_back if hold_back is None else hold_back
    if horizon < 1 or hold_back < model.p:
        raise ValueError('Invalid prediction horizon or history')
    y = segment.residual
    # Origin o knows y[:o]; prediction endpoint is o+h-1.
    origins = np.arange(hold_back, len(y)-horizon+1)
    indices = origins+horizon-1
    history = np.column_stack([y[origins-j] for j in range(1, model.p+1)])
    pred = np.empty(len(origins))
    for _ in range(horizon):
        pred = model.intercept + history@np.asarray(model.coefficients)
        history = np.column_stack([pred, history[:, :-1]])
    if not np.isfinite(pred).all():
        raise ValueError('Nonfinite recursive predictions')
    return dict(index=indices, predicted_residual=pred, observed_residual=y[indices])


def error_metrics(errors):
    errors = np.asarray(errors, float)
    if not len(errors) or not np.isfinite(errors).all():
        raise ValueError('Metrics need finite observations')
    return dict(n=len(errors), rmse_w=float(np.sqrt(np.mean(errors**2))),
                mae_w=float(np.mean(np.abs(errors))), bias_w=float(np.mean(errors)))


def evaluate(model, segments, horizons=(1, 10, 30), hold_back=None):
    groups = {}
    for segment in segments:
        for horizon in horizons:
            prediction = forecast_segment(model, segment, horizon, hold_back)
            if not len(prediction['index']):
                continue
            key = (segment.workout_id, horizon)
            groups.setdefault(key, [[], []])
            groups[key][0].append(prediction['observed_residual']-prediction['predicted_residual'])
            groups[key][1].append(prediction['observed_residual'])
    rows = []
    for (wid, horizon), (ar_errors, baseline_errors) in groups.items():
        for label, errors in [('ar', ar_errors), ('target', baseline_errors)]:
            rows.append(dict(workout_id=wid, horizon_s=horizon, model=label,
                             **error_metrics(np.concatenate(errors))))
    if not rows:
        raise ValueError('No eligible forecast endpoints')
    return pd.DataFrame(rows)


def macro_metrics(rows):
    return rows.groupby(['horizon_s', 'model'], as_index=False).agg(
        rmse_w=('rmse_w', 'mean'), mae_w=('mae_w', 'mean'),
        workouts=('workout_id', 'nunique'), samples=('n', 'sum'))
