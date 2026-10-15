"""Scientific contracts: boundaries, common support and causal forecasting."""
import importlib
import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def api(name):
    try:
        return importlib.import_module('power_hr_eda.power_residual_ar.' + name)
    except ModuleNotFoundError as exc:
        pytest.fail(f'AR module is not implemented: {exc}')


def frame():
    return pd.DataFrame(dict(
        elapsed_seconds=[0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        power_w=[100, 0, np.nan, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        power_target_w=[100]*7 + [120]*5,
        power_segment_id=[1, 1, 0, 2, 2, 2, 2, 2, 2, 2, 3, 3],
        timer_paused=[False]*4 + [True] + [False]*7,
        lap_index=[1]*9 + [2]*3))


def test_segmentation_preserves_zero_and_breaks_every_boundary():
    data = api('data')
    f = frame()
    before = f.copy(deep=True)
    segments, coverage = data.segment_frame(f, 'w')
    assert [s.time.tolist() for s in segments] == [[0, 1], [4], [6, 7], [8, 9], [10], [11, 12]]
    assert segments[0].residual.tolist() == [0, -100]
    assert coverage['valid_samples'] == 10
    pd.testing.assert_frame_equal(f, before)


def segment(y, wid='w', sid=1):
    data = api('data')
    y = np.asarray(y, float)
    return data.Segment(wid, sid, np.arange(len(y), dtype=float), y, np.full(len(y), 200.))


def test_lags_stay_in_segments_and_orders_have_identical_support():
    fit = api('fit')
    segments = [segment([0, 1, 2, 3, 4]), segment([100, 101, 102, 103, 104], sid=2)]
    x1, y1 = fit.design_matrix(segments, p=1, hold_back=2)
    x2, y2 = fit.design_matrix(segments, p=2, hold_back=2)
    assert y1.tolist() == [2, 3, 4, 102, 103, 104]
    np.testing.assert_array_equal(y1, y2)
    assert x2.tolist() == [[1, 1, 0], [1, 2, 1], [1, 3, 2], [1, 101, 100], [1, 102, 101], [1, 103, 102]]
    np.testing.assert_array_equal(x1[:, 1], x2[:, 1])
    with pytest.raises(ValueError):
        fit.design_matrix(segments, p=3, hold_back=2)


def test_ar_fit_recovers_known_process_and_information_criteria():
    fit = api('fit')
    rng = np.random.default_rng(841)
    y = np.zeros(20000)
    for i in range(1, len(y)):
        y[i] = 2 + .7*y[i-1] + rng.normal()
    model = fit.fit_ar([segment(y)], p=1, hold_back=3)
    assert model.intercept == pytest.approx(2, abs=.09)
    assert model.coefficients[0] == pytest.approx(.7, abs=.02)
    assert model.stable
    assert model.nobs == len(y)-3
    assert model.bic-model.aic == pytest.approx(3*(np.log(model.nobs)-2))


def test_recursive_prediction_cannot_see_future_observations():
    fit, validation = api('fit'), api('validation')
    model = fit.ARModel(p=1, intercept=1., coefficients=[.5], hold_back=1)
    s = segment([2, 4, 1000, -1000, 9, 10])
    pred = validation.forecast_segment(model, s, horizon=3, hold_back=1)
    assert pred['index'].tolist() == [3, 4, 5]
    assert pred['predicted_residual'][0] == 2.
    changed = segment([2, 9999, 3333, 77, 9, 10])
    other = validation.forecast_segment(model, changed, horizon=3, hold_back=1)
    assert other['predicted_residual'][0] == 2.
    one = validation.forecast_segment(model, s, horizon=1, hold_back=1)
    assert one['predicted_residual'].tolist() == [2, 3, 501, -499, 5.5]


def test_metrics_are_in_watts_and_macro_average_weights_workouts_equally():
    validation = api('validation')
    metrics = validation.error_metrics(np.array([3., -4.]))
    assert metrics['rmse_w'] == pytest.approx(np.sqrt(12.5))
    assert metrics['mae_w'] == 3.5
    rows = pd.DataFrame([dict(workout_id='a', horizon_s=1, model='ar', n=1000, rmse_w=2., mae_w=1.),
                         dict(workout_id='b', horizon_s=1, model='ar', n=1, rmse_w=10., mae_w=9.)])
    result = validation.macro_metrics(rows)
    assert result.iloc[0].rmse_w == 6.
    assert result.iloc[0].mae_w == 5.


def test_acf_pacf_use_each_segment_and_handle_constant_short_series():
    diag = api('diagnostics')
    acf, pacf = diag.acf_pacf(np.array([1., 2., 3., 4.]), 1)
    assert acf.tolist() == pytest.approx([1, .25])
    assert pacf.tolist() == pytest.approx([1, .25])
    acf, pacf = diag.acf_pacf(np.ones(20), 5)
    assert np.isnan(acf[1:]).all()
    assert np.isnan(pacf[1:]).all()


def test_chronological_split_is_disjoint_and_needs_a_test_workout():
    data = api('data')
    records = [dict(workout_id=str(i), start_time=f'2025-01-{i+1:02d}T00:00:00+00:00') for i in reversed(range(6))]
    split = data.chronological_split(records, 3, 2)
    assert split == dict(train=['0', '1', '2'], validation=['3', '4'], test=['5'])
    with pytest.raises(ValueError):
        data.chronological_split(records, 4, 2)


def write_dataset(root):
    samples = root/'samples'
    samples.mkdir(parents=True)
    rng = np.random.default_rng(7)
    for k in range(6):
        n = 160
        y = np.zeros(n)
        for i in range(1, n):
            y[i] = .8*y[i-1] + rng.normal()
        pd.DataFrame(dict(timestamp=pd.date_range(f'2025-01-{k+1:02d}', periods=n, freq='s', tz='UTC'),
                          elapsed_seconds=np.arange(n), power_w=200+y, power_target_w=200.,
                          lap_index=1, power_segment_id=1, timer_paused=False)).to_csv(samples/f'w{k}.csv.gz', index=False)


def test_cli_freezes_train_diagnostics_and_keeps_test_out_of_selection():
    api('cli')
    from power_hr_eda.power_residual_ar.cli import main
    # Python 3.14 / Windows sandbox: pytest's mode=0o700 temporary paths
    # are not readable by this process. Ordinary workspace directories are.
    tmp_path = Path(__file__).parent/'_generated'/('ar_' + uuid.uuid4().hex)
    source, output = tmp_path/'dataset', tmp_path/'results'
    write_dataset(source)
    assert main(['diagnose', '--input', str(source), '--output', str(output), '--train-count', '3',
                 '--validation-count', '2', '--max-lag', '12']) == 0
    diagnostics = pd.read_csv(output/'diagnostics'/'segments.csv')
    assert set(diagnostics.workout_id) == {'w0', 'w1', 'w2'}
    assert main(['fit', '--output', str(output), '--p', '1', '2', '--analyze']) == 0
    selection = json.loads((output/'selection.json').read_text())
    assert selection['criterion'] == 'validation_macro_rmse_h1'
    metrics = pd.read_csv(output/'comparison.csv')
    assert set(metrics.split) == {'train', 'validation'}
    assert not (output/'test').exists()
    premature = tmp_path/'premature_simulation'
    assert main(['simulate', '--from-run', str(output), '--output', str(premature), '--paths', '2']) != 0
    assert not premature.exists()
    assert main(['test', '--output', str(output), '--analyze']) == 0
    metrics = pd.read_csv(output/'test'/'metrics_by_workout.csv')
    assert set(metrics.workout_id) == {'w5'}
    assert main(['fit', '--output', str(output), '--p', '1']) != 0
    frozen_selection = (output/'selection.json').read_bytes()
    simulations = tmp_path/'simulations'
    assert main(['simulate', '--from-run', str(output), '--output', str(simulations),
                 '--paths', '5', '--seed', '12', '--analyze']) == 0
    assert (output/'selection.json').read_bytes() == frozen_selection
    m = pd.read_csv(simulations/'test_descriptive'/'metrics_by_workout.csv')
    assert set(m.workout_id) == {'w5'}
    assert m.n_samples.iloc[0] == 160  # includes initialized first samples
    trace = pd.read_csv(simulations/'test_descriptive'/'w5.csv.gz')
    assert len(trace) == 160
    np.testing.assert_allclose(trace.simulated_power_w-trace.prescribed_power_w, trace.simulated_residual_w)
    assert (simulations/'test_descriptive'/'w5.png').exists()


def test_optional_analysis_handles_too_short_innovation_segments():
    fit, validation, plots = api('fit'), api('validation'), api('plots')
    rng = np.random.default_rng(63)
    segments = [segment(rng.normal(size=21), wid=str(i), sid=i) for i in range(40)]
    model = fit.fit_ar(segments, p=1, hold_back=20)
    assert model.nobs == 40
    output = Path(__file__).parent/'_generated'/('ar_short_' + uuid.uuid4().hex)
    plots.fit_analysis(model, segments, segments, validation.evaluate(model, segments), output)
    assert json.loads((output/'innovation_status.json').read_text())['available'] is False
    assert (output/'performance.png').exists()
