"""One frozen decomposition model; ablations never refit or resample."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .ar import ARModel, simulate_workout, stationary_state
from .data import Segment
from .dynamics import ResponseModel, input_delta


@dataclass
class DecompositionModel:
    dynamics: ResponseModel
    ar: ARModel
    seed: int = 42
    paths: int = 100

    def to_dict(self):
        return dict(dynamics=self.dynamics.to_dict(), ar=self.ar.to_dict(), seed=self.seed, paths=self.paths)

    @classmethod
    def from_dict(cls, value):
        model = cls(ResponseModel.from_dict(value['dynamics']), ARModel.from_dict(value['ar']),
                    int(value['seed']), int(value['paths']))
        if model.seed < 0 or model.paths < 1:
            raise ValueError('Invalid stochastic configuration')
        stationary_state(model.ar)  # Reject unstable/degenerate models explicitly.
        return model

    def residual_segments(self, segments):
        return [Segment(s.workout_id, s.segment_id, s.time,
                        s.residual-self.dynamics.response(s.target), s.target) for s in segments]

    def decompose(self, segments):
        """Generate once per workout, independently of observed residuals."""
        ar_mean = float(stationary_state(self.ar)[0][0])
        frames = []
        for wid in dict.fromkeys(s.workout_id for s in segments):
            parts = [s for s in segments if s.workout_id == wid]
            sims = simulate_workout(self.ar, parts, seed=self.seed, paths=self.paths)
            for s, simulated in zip(parts, sims, strict=True):
                response = self.dynamics.response(s.target)
                e = s.residual-response
                innovation = np.full(len(e), np.nan)
                if len(e) > self.ar.p:
                    p = self.ar.p
                    innovation[p:] = e[p:]-self.ar.intercept
                    for j, coef in enumerate(self.ar.coefficients, 1):
                        innovation[p:] -= coef*e[p-j:len(e)-j]
                low, high = np.quantile(simulated, [.1,.9], axis=0)
                frames.append(pd.DataFrame(dict(workout_id=str(wid), segment_id=s.segment_id, time_s=s.time,
                    target_w=s.target, real_w=s.target+s.residual, input_w=input_delta(s.target),
                    response_w=response, final_residual_w=e, innovation_w=innovation,
                    ar_mean_w=ar_mean, ar_sample_w=simulated[0], ar_low_w=low, ar_high_w=high)))
        if not frames:
            raise ValueError('No valid continuous segments')
        return pd.concat(frames, ignore_index=True)


def compose(table, *, dynamic=True, ar=True, mode='mean'):
    if mode not in ('mean','simulation'):
        raise ValueError('Mode must be mean or simulation')
    predicted = table.target_w.to_numpy().copy()
    if dynamic:
        predicted += table.response_w.to_numpy()
    if ar:
        predicted += table['ar_mean_w' if mode == 'mean' else 'ar_sample_w'].to_numpy()
    return predicted, table.real_w.to_numpy()-predicted


def error_metrics(error):
    error = np.asarray(error, float)
    if not len(error):
        return dict(n=0, rmse_w=None, mae_w=None, bias_w=None, sd_w=None)
    if not np.isfinite(error).all():
        raise ValueError('Nonfinite prediction error')
    return dict(n=len(error), rmse_w=float(np.sqrt(np.mean(error**2))),
                mae_w=float(np.mean(np.abs(error))), bias_w=float(np.mean(error)), sd_w=float(np.std(error)))


def configuration_metrics(table, *, dynamic=True, ar=True, mode='mean', start=None, end=None):
    selected = table
    if start is not None:
        selected = selected[selected.time_s >= start]
    if end is not None:
        selected = selected[selected.time_s <= end]
    _, error = compose(selected, dynamic=dynamic, ar=ar, mode=mode)
    return error_metrics(error)


def all_metrics(table):
    rows = []
    for wid, part in table.groupby('workout_id', sort=False):
        for mode in ('mean','simulation'):
            for dynamic in (False,True):
                for ar in (False,True):
                    rows.append(dict(workout_id=wid, mode=mode, dynamic=dynamic, ar=ar,
                                     **configuration_metrics(part, dynamic=dynamic, ar=ar, mode=mode)))
    return rows


def select_order(rows, seed=42):
    """Preserve the approved paired-SE rule; selection sees validation only."""
    pivot = pd.DataFrame(rows).pivot(index='workout_id', columns='order', values='rmse').sort_index(axis=1)
    if pivot.empty or pivot.isna().any().any():
        raise ValueError('Selection requires common workout support')
    best = int(pivot.mean().idxmin())
    indices = np.random.default_rng(seed).integers(0,len(pivot),size=(2000,len(pivot)))
    comparisons, eligible = [], []
    for order in pivot:
        difference = (pivot[order]-pivot[best]).to_numpy()
        se = float(np.std(difference,ddof=1)/np.sqrt(len(difference))) if len(difference)>1 else 0.
        delta = float(difference.mean())
        accepted = delta <= se+1e-10
        if accepted:
            eligible.append(int(order))
        comparisons.append(dict(order=int(order),mean_rmse_w=float(pivot[order].mean()),delta_from_best_w=delta,
            paired_se_w=se, paired_bootstrap_ci95_w=np.quantile(difference[indices].mean(axis=1),[.025,.975]).tolist(),
            within_one_paired_se=accepted))
    return min(eligible), dict(best_order=best, comparisons=comparisons,
        rule='smallest converged order within one paired SE of best validation mean workout RMSE')
