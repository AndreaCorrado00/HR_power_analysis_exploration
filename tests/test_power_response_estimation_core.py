"""Scientific regression tests migrated from the two former pipelines."""
import importlib
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.signal import lfilter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from power_response_estimation.data import Segment,segment_frame
from power_response_estimation.ar import ARModel

def module(name):
    return importlib.import_module('power_response_estimation.'+{'model':'dynamics','evaluation':'model'}.get(name,name))
def api(name):
    return importlib.import_module('power_response_estimation.'+{'fit':'ar'}.get(name,name))
def simulation():
    return api('ar')

def synthetic(count=5, samples=600, noise=.15):
    rng = np.random.default_rng(8)
    segments = []
    for w in range(count):
        target = np.repeat(rng.choice([100., 200., 300.], samples // 20), 20)
        u = np.r_[0., np.diff(target)]
        r = lfilter([-.75, .25, .1], [1., -1.2, .32], u)
        e = 2.5 + lfilter([1.], [1., -.5], rng.normal(0, noise, samples))
        segments.append(Segment(str(w), 1, np.arange(samples), r+e, target))
    return segments

def test_free_response_has_direct_term_memory_and_no_artificial_first_jump():
    m = module('model').ResponseModel(2, [1., -1.2, .32], [-.75, .25, .1], 2.5)
    target = np.array([100., 100., 200., 200., 200., 100.])
    np.testing.assert_allclose(m.response(target), [0, 0, -75, -65, -44, 43], atol=1e-10)
    assert np.all(np.abs(np.roots(m.a)) < 1)
    restored = module('model').ResponseModel.from_dict(m.to_dict())
    np.testing.assert_allclose(restored.response(target), m.response(target))

def test_fit_recovers_impulse_with_colored_noise_and_reports_uncertainty():
    m, stats = module('model').fit_response(synthetic(), 2, starts=3, max_nfev=180)
    expected = lfilter([-.75, .25, .1], [1., -1.2, .32], np.r_[1., np.zeros(59)])
    np.testing.assert_allclose(lfilter(m.b, m.a, np.r_[1., np.zeros(59)]), expected, atol=.01)
    assert abs(m.mean - 2.5) < .1
    assert stats['converged']
    assert stats['jacobian_rank'] == 6
    assert len(stats['parameters']) == 6
    assert stats['clusters'] == 5

def test_segmentation_keeps_transitions_but_not_gaps():
    frame = pd.DataFrame(dict(elapsed_seconds=[0,1,2,4,5], power_w=[100,110,180,200,190],
        power_target_w=[100,100,200,200,200], timer_paused=False,
        power_segment_id=[1,1,1,2,2], lap_index=[1,1,2,2,2]))
    parts, _ = segment_frame(frame, 'x', split_at_prescription=False)
    assert [len(p.time) for p in parts] == [3,2]
    u = module('model').input_delta
    np.testing.assert_array_equal(u(parts[0].target), [0,0,100])
    np.testing.assert_array_equal(u(parts[1].target), [0,0])

def test_selection_prefers_smallest_within_paired_standard_error():
    rows = pd.DataFrame([dict(order=n, workout_id=str(i), rmse=v)
                        for n, values in [(2,[10.,12.,10.]), (3,[9.,12.,10.]), (4,[9.,12.,10.])]
                        for i,v in enumerate(values)])
    selected, _ = module('evaluation').select_order(rows, seed=42)
    assert selected == 2

def test_no_excitation_is_rejected():
    s = Segment('x', 1, np.arange(20), np.arange(20.), np.full(20, 100.))
    with pytest.raises(ValueError, match='transition'):
        module('model').fit_response([s], 2)

def test_huber_is_optional_and_retains_robust_scale_in_watts():
    parts = synthetic(3, samples=200)
    parts[0].residual[50] += 2000
    m, stats = module('model').fit_response(parts, 2, loss='huber', scale=2., starts=2, max_nfev=150)
    assert stats['loss'] == 'huber'
    assert stats['scale_w'] == 2.
    assert abs(m.mean-2.5) < .2
    assert stats['covariance'] is None

def test_parameter_diagnostics_expose_exact_pole_zero_cancellation():
    m = module('model').ResponseModel(2, [1., -1.2, .32], [1., -.8, 0.], 0.)
    parts = synthetic(3, samples=200)
    _, weights = module('model').prepare(parts)
    stats = module('model').parameter_statistics(m, parts, weights, np.zeros(600), 'linear')
    assert stats['minimum_pole_zero_distance'] < 1e-10

def frame():
    return pd.DataFrame(dict(
        elapsed_seconds=[0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        power_w=[100, 0, np.nan, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        power_target_w=[100]*7 + [120]*5,
        power_segment_id=[1, 1, 0, 2, 2, 2, 2, 2, 2, 2, 3, 3],
        timer_paused=[False]*4 + [True] + [False]*7,
        lap_index=[1]*9 + [2]*3))

def segment(y, wid='w', sid=1):
    data = api('data')
    y = np.asarray(y, float)
    return data.Segment(wid, sid, np.arange(len(y), dtype=float), y, np.full(len(y), 200.))

def test_segmentation_preserves_zero_and_breaks_every_boundary():
    data = api('data')
    f = frame()
    before = f.copy(deep=True)
    segments, coverage = data.segment_frame(f, 'w')
    assert [s.time.tolist() for s in segments] == [[0, 1], [4], [6, 7], [8, 9], [10], [11, 12]]
    assert segments[0].residual.tolist() == [0, -100]
    assert coverage['valid_samples'] == 10
    pd.testing.assert_frame_equal(f, before)

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

def test_chronological_split_is_disjoint_and_needs_a_test_workout():
    data = api('data')
    records = [dict(workout_id=str(i), start_time=f'2025-01-{i+1:02d}T00:00:00+00:00') for i in reversed(range(6))]
    split = data.chronological_split(records, 3, 2)
    assert split == dict(train=['0', '1', '2'], validation=['3', '4'], test=['5'])
    with pytest.raises(ValueError):
        data.chronological_split(records, 4, 2)

def test_continuous_fit_crosses_laps_and_targets_but_never_missing_or_pauses():
    f = pd.DataFrame(dict(elapsed_seconds=[0,1,2,3,4,5,7,8], power_w=[100,101,201,202,np.nan,100,100,100],
        power_target_w=[100,100,200,200,200,100,100,100], lap_index=[1,1,2,2,2,3,3,3],
        power_segment_id=[1,1,1,1,0,2,3,4], timer_paused=[False]*7+[True]))
    before = f.copy(deep=True)
    parts, _ = segment_frame(f, 'w', split_at_prescription=False)
    assert [s.time.tolist() for s in parts] == [[0,1,2,3], [5], [7]]
    assert parts[0].residual.tolist() == [0,1,1,2]
    pd.testing.assert_frame_equal(before, f)
    diagnostic_parts, _ = segment_frame(f, 'w')
    assert [s.time.tolist() for s in diagnostic_parts[:2]] == [[0,1],[2,3]]

def test_stationary_initialization_has_theoretical_ar1_moments():
    sim = simulation()
    model = ARModel(p=1, intercept=2., coefficients=[.5], hold_back=1, sigma2=3.)
    mean, covariance = sim.stationary_state(model)
    assert mean.tolist() == pytest.approx([4.])
    assert covariance[0,0] == pytest.approx(4.)
    paths = sim.simulate_residual(model, 40, 20000, np.random.default_rng(15))
    assert paths[:,0].mean() == pytest.approx(4., abs=.06)
    assert paths[:,0].var() == pytest.approx(4., abs=.12)
    assert paths[:,-1].var() == pytest.approx(4., abs=.12)
    assert np.corrcoef(paths[:,10], paths[:,11])[0,1] == pytest.approx(.5, abs=.025)
    with pytest.raises(ValueError):
        sim.stationary_state(ARModel(p=1, intercept=0., coefficients=[1.1], hold_back=1, sigma2=1.))

def test_whole_workout_simulation_does_not_read_observed_residual_and_is_repeatable():
    sim = simulation()
    model = ARModel(p=1, intercept=0., coefficients=[.8], hold_back=1, sigma2=4.)
    t = np.arange(300, dtype=float)
    target = np.r_[np.full(150,200.),np.full(150,300.)]
    a = Segment('w', 1, t, np.zeros(300), target)
    b = Segment('w', 1, t, np.full(300,10000.), target.copy())
    first = sim.simulate_workout(model, [a], seed=42, paths=5)
    second = sim.simulate_workout(model, [b], seed=42, paths=5)
    np.testing.assert_array_equal(first[0], second[0])
    assert first[0].shape == (5,300)
    # Prescribed jump shifts reconstructed power exactly; does not reset residual.
    flat = Segment('w', 1, t, a.residual, np.full(300,200.))
    np.testing.assert_array_equal(first[0], sim.simulate_workout(model,[flat],seed=42,paths=5)[0])
    assert not np.array_equal(first[0], sim.simulate_workout(model,[a],seed=43,paths=5)[0])
