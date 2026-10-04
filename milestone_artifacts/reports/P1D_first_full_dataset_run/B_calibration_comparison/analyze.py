"""Reproduce the exploratory B-window comparison; does not import or edit the app.

Run: python reports/P1D_first_full_dataset_run/B_calibration_comparison/analyze.py
Requires numpy. Outputs stay beside this script. No fitting of K, L or tau.
"""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "eca4153fddb94d419f02ed67a89450f1_population_review.json"
WINDOWS = (10, 30, 60, 120, 180)
EVALUATION_START = 180
# Inferred from the saved calibration.at_bound records, then checked by
# reproducing every original 10-second trajectory and evaluation metric.
B_BOUNDS = (60.0, 200.0)


def main():
    source_bytes = SOURCE.read_bytes()
    data = json.loads(source_bytes)
    assert data['config']['prediction_mode'] == 'local_B_10s'
    model = data['model']
    tau = model['mean'][model['keys'].index('tau')]
    predicted = [x for x in data['test'] if x['status'] == 'predicted']
    assert set(x['equilibrium_B'] for x in predicted
               if x['calibration']['at_bound']) == set(B_BOUNDS)
    rows = []
    max_baseline_difference = 0.0
    for segment in predicted:
        series = segment['series']
        t = np.asarray(series['time'], float)
        y = np.asarray(series['observed'], float)
        original = np.asarray(series['predicted'], float)
        assert t[0] == 0 and np.all(np.diff(t) > 0)
        assert np.isfinite(t).all() and np.isfinite(original).all()
        # Exact affine decomposition of the SAVED trajectory, preserving all
        # input handling and the original observed-HR initial condition.
        w = -np.expm1(-t / tau)
        a = original - w * segment['equilibrium_B']
        evaluation = (t >= EVALUATION_START) & np.isfinite(y)
        assert evaluation.any(), 'Segment has no common evaluation tail'
        for duration in WINDOWS:
            calibration = (t < duration) & np.isfinite(y)
            assert calibration.sum() >= 3
            assert not np.any(calibration & evaluation)
            wc = w[calibration]
            raw_b = float(wc @ (y[calibration] - a[calibration]) / (wc @ wc))
            b = float(np.clip(raw_b, *B_BOUNDS))
            prediction = a + w * b
            if duration == 10:
                difference = float(np.max(np.abs(prediction - original)))
                max_baseline_difference = max(max_baseline_difference, difference)
                assert difference < 1e-8
                old_e = y[(t >= 10) & np.isfinite(y)] - prediction[(t >= 10) & np.isfinite(y)]
                for key, value in [('RMSE', np.sqrt(np.mean(old_e**2))),
                                   ('MAE', np.mean(abs(old_e))), ('bias', old_e.mean())]:
                    assert np.isclose(value, segment['metrics'][key], atol=1e-8)
            e = y[evaluation] - prediction[evaluation]
            rows.append(dict(segment_id=segment['segment_id'], activity_id=segment['activity_id'],
                             filename=segment['filename'].split('/')[-1],
                             last_time_s=float(t[-1]), calibration_s=duration, B=b,
                             B_unconstrained=raw_b, at_bound=b in B_BOUNDS,
                             N=int(len(e)), MAE=float(np.mean(abs(e))),
                             RMSE=float(np.sqrt(np.mean(e**2))), bias=float(e.mean()),
                             residual_sd=float(e.std(ddof=1)), SSE=float(e @ e)))

    baseline = {r['segment_id']: r for r in rows if r['calibration_s'] == 10}
    aggregates = []
    for duration in WINDOWS:
        selected = [r for r in rows if r['calibration_s'] == duration]
        activities = defaultdict(list)
        for row in selected:
            activities[row['activity_id']].append(row)
        activity_rmse = [np.sqrt(sum(r['SSE'] for r in group) / sum(r['N'] for r in group))
                         for group in activities.values()]
        deltas = [r['RMSE'] - baseline[r['segment_id']]['RMSE'] for r in selected]
        aggregates.append(dict(calibration_s=duration, segments=len(selected),
            activities=len(activities), median_RMSE=float(np.median([r['RMSE'] for r in selected])),
            median_MAE=float(np.median([r['MAE'] for r in selected])),
            median_abs_bias=float(np.median([abs(r['bias']) for r in selected])),
            median_residual_sd=float(np.median([r['residual_sd'] for r in selected])),
            p90_RMSE=float(np.percentile([r['RMSE'] for r in selected], 90)),
            median_activity_RMSE=float(np.median(activity_rmse)),
            at_bound=sum(r['at_bound'] for r in selected),
            improved_vs_10s=sum(x < -1e-8 for x in deltas),
            worsened_vs_10s=sum(x > 1e-8 for x in deltas),
            unchanged_vs_10s=sum(abs(x) <= 1e-8 for x in deltas)))
    stability = []
    for earlier, later in zip(WINDOWS[:-1], WINDOWS[1:]):
        previous = {r['segment_id']: r['B'] for r in rows if r['calibration_s'] == earlier}
        differences = [abs(r['B'] - previous[r['segment_id']]) for r in rows
                       if r['calibration_s'] == later]
        stability.append(dict(earlier_s=earlier, later_s=later,
                              median_abs_B_change=float(np.median(differences)),
                              p90_abs_B_change=float(np.percentile(differences, 90))))
    output = dict(source=SOURCE.name, source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                  numpy_version=np.__version__, frozen_parameters=dict(zip(model['keys'], model['mean'])),
                  B_bounds=list(B_BOUNDS), bounds_provenance='inferred from saved at_bound records; 10s reproduction verified',
                  evaluation_start_s=EVALUATION_START, calibration_interval='0 <= t < T',
                  status='exploratory on previously inspected test; not independent validation',
                  failed_segments_excluded=len(data['test'])-len(predicted),
                  min_last_time_s=min(x['series']['time'][-1] for x in predicted),
                  max_original_trajectory_reproduction_error=max_baseline_difference,
                  summary=aggregates, B_stability=stability)
    (HERE / 'summary.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    with (HERE / 'per_segment.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
