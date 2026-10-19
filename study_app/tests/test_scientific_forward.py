import numpy as np
from study_app.scientific.adapters import simulate_hr, simulate_power, rules_for_ftp


def test_hr_uses_only_train_initial_references():
    p = np.full((2, 301), 100.)
    theta = np.array([[.2, 0, 50], [.2, 7.5, 50]])
    y = simulate_hr(p, theta, 80., 120.)
    expected = 100 + 20*np.exp(-np.arange(301)/50)
    np.testing.assert_allclose(y[0], expected)
    np.testing.assert_allclose(y[1], expected)


def test_power_is_autonomous_repeatable_and_nonnegative():
    model = {'dynamics': {'order':2,'a':[1.,0.,0.],'b':[0.,0.,0.],'mean':0},
             'ar':{'p':2,'intercept':0.,'coefficients':[.5,.1],'hold_back':2,'sigma2':400.},'seed':42,'paths':30}
    a = simulate_power(np.zeros(100), model, 30, 42, 'one')
    b = simulate_power(np.zeros(100), model, 30, 42, 'one')
    np.testing.assert_array_equal(a,b)
    assert a.min() == 0 and a.mean() > 0


def test_ftp_changes_zones_not_observed_target_rounding():
    rules = rules_for_ftp(260)
    assert rules['ftp_w'] == 260
    np.testing.assert_allclose(rules['zones'][-1]['high_w'], 390.4)
    assert rules['target_rounding_w'] == 5
    assert rules['patterns']['power_tolerance_fraction'] == .05
