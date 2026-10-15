"""Whole-workout free simulations: continuity, stochastic dynamics and no feedback."""
import importlib
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
import pytest

from power_hr_eda.power_residual_ar.data import segment_frame, Segment
from power_hr_eda.power_residual_ar.fit import ARModel


def simulation():
    try:
        return importlib.import_module('power_hr_eda.power_residual_ar.simulation')
    except ModuleNotFoundError:
        pytest.fail('Free simulation module not yet implemented')


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


def test_simulation_summary_uses_all_valid_samples_and_records_negative_power():
    sim = simulation()
    part = Segment('w', 1, np.arange(4.), np.array([-1.,1.,-1.,1.]), np.zeros(4))
    paths = [np.array([[-2.,2.,-2.,2.],[-3.,3.,-3.,3.]])]
    table, summary = sim.summarize_workout([part], paths, residual_mean=0.)
    assert len(table) == 4
    assert summary['n_samples'] == 4
    assert summary['observed_residual_sd_w'] == 1.
    assert summary['simulated_negative_power_fraction'] == .5
    assert summary['mean_prediction_rmse_w'] == 1.
    assert summary['baseline_rmse_w'] == 1.
