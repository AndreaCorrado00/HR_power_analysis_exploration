"""Protect gap handling and the statistical diagnostic, independently of the fit."""
import importlib
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def api():
    return importlib.import_module('power_response_estimation.diagnostics_analysis')


def test_runs_break_at_gaps_and_missing_innovations():
    d = pd.DataFrame(dict(segment_id=[1]*7, time_s=[0,1,2,4,5,6,7],
                          innovation_w=[1,2,np.nan,3,4,5,6]))
    assert [len(x) for x in api().continuous_parts(d)] == [2,4]


def test_acf_does_not_create_pairs_across_parts():
    value, pairs = api().acf_parts([np.array([1.,3.]), np.array([10.,14.])], 1)
    assert value == pytest.approx(-.5)
    assert pairs == 2


def test_arch_matches_independent_reference_and_counts_rows():
    from scipy.stats import linregress, chi2
    # Independent simple-regression reference, no optional dependency.
    squares = np.array([1.,2.,3.,5.,4.,7.,2.,6.,8.,3.])
    x = np.sqrt(squares)
    result = api().arch_lm([x], 1)
    expected_lm = 9*linregress(squares[:-1],squares[1:]).rvalue**2
    assert result['lm'] == pytest.approx(expected_lm)
    assert result['p_value'] == pytest.approx(chi2.sf(expected_lm,1))
    assert api().arch_lm([x[:5], x[5:]], 1)['nobs'] == 8


def test_arch_detects_synthetic_volatility_clustering():
    rng = np.random.default_rng(7)
    e = np.zeros(6000)
    for i in range(1,len(e)):
        e[i] = rng.normal()*np.sqrt(1 + .8*e[i-1]**2)
    result = api().arch_lm([e], 5)
    assert result['p_value'] < 1e-10
    assert result['r_squared'] > .05


def test_degenerate_series_not_reported_as_evidence():
    assert np.isnan(api().arch_lm([np.ones(100)], 5)['p_value'])
    assert np.isnan(api().arch_lm([np.arange(4.)], 5)['p_value'])


def test_fdr_known_example():
    np.testing.assert_allclose(api().bh_adjust([.01,.04,.03]), [.03,.04,.04])


def intervals():
    return importlib.import_module('power_response_estimation.interval_diagnostics')


def test_interval_boundaries_preserve_target_age_at_lap_change():
    d = pd.DataFrame(dict(time_s=[0,1,2,3,4,6,7], segment_id=[1]*7,
        target_w=[100,100,100,200,200,200,200], lap_index=[1,1,2,2,2,2,2],
        innovation_w=[np.nan,1,2,3,4,5,6]))
    a = intervals().annotate_intervals(d)
    assert a.interval_id.tolist() == [1,1,2,3,3,4,4]
    assert a.target_age_s.tolist() == [0,1,2,0,1,0,1]


def test_fft_acf_matches_direct_estimator_with_short_parts():
    parts = [np.array([1.,3.,2.,8.]),np.array([5.,9.]),np.ones(8)]
    num,den,pairs = intervals().acf_components(parts,max_lag=5)
    for lag in range(1,6):
        expected,count = api().acf_parts(parts,lag)
        assert pairs[lag-1] == count
        if np.isnan(expected):
            assert den[0,lag-1] == pytest.approx(0)
        else:
            assert num[0,lag-1]/den[0,lag-1] == pytest.approx(expected)


def test_shuffle_preserves_every_interval_phase_distribution():
    x = np.arange(12.)
    cells = np.array([0]*3+[1]*3+[2]*6)
    shuffled = intervals().shuffle_cells(x,cells,np.random.default_rng(42),20)
    for cell in np.unique(cells):
        np.testing.assert_array_equal(np.sort(shuffled[:,cells==cell],axis=1),
            np.tile(x[cells==cell],(20,1)))
    assert not np.array_equal(shuffled[0],x)


def test_plateau_and_interval_acf_never_bridge_removed_samples():
    d = pd.DataFrame(dict(time_s=np.arange(12),segment_id=1,
        target_w=[100]*6+[200]*6,lap_index=[1]*6+[2]*6,
        innovation_w=np.arange(12.)+1))
    d = intervals().annotate_intervals(d)
    parts = intervals().mode_parts([d], 'plateau30', trim=3)
    assert [p.tolist() for p in parts] == [[4.,5.,6.],[10.,11.,12.]]
    assert intervals().acf_components([p*p for p in parts],max_lag=3)[2].tolist()==[4,2,0]


def test_context_null_retains_variance_regimes_but_not_internal_order():
    rng = np.random.default_rng(6)
    target = np.repeat([100,200]*5,100)
    d = pd.DataFrame(dict(time_s=np.arange(1000),segment_id=1,target_w=target,
        lap_index=np.repeat(np.arange(10),100),
        innovation_w=rng.normal(size=1000)*np.where(target==100,1,8)))
    d = intervals().annotate_intervals(d)
    comp = intervals().permutation_components([d],'synthetic',replicates=19)
    raw = intervals().ratio(comp['raw'][0],comp['raw'][1])
    within = intervals().ratio(comp['within'][0],comp['within'][1])
    assert np.median(raw[1:,0]) > .1
    assert abs(np.median(within[1:,0])) < .06
    # Fixed seed and identical input reproduce the actual reference distribution.
    again = intervals().permutation_components([d],'synthetic',replicates=19)
    np.testing.assert_array_equal(comp['raw'][0],again['raw'][0])
