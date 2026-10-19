import numpy as np
import pytest
from webapp.model_identification_app.backend.models import p1d


def test_nonequilibrium_exact_initial_decay_and_delayed_forcing():
    t = np.array([0., .4, 1., 2., 3.5, 7., 20.])
    power = np.full(len(t), 300.)
    expected = 120+40*np.exp(-t/10)+.2*200*(-np.expm1(-np.maximum(t-2.3, 0)/10))
    actual = p1d.simulate(t, power, 160., [.2, 2.3, 10., 120.], 100., initialization_mode='estimated_equilibrium')
    np.testing.assert_allclose(actual, expected, atol=1e-12)
    assert actual[0] == 160
    assert actual[1] < actual[0]


def test_recovers_equilibrium_and_initial_state_without_fitting_context():
    t = np.arange(181.)
    power = np.select([t<40, t<80, t<120], [300., 100., 250.], 50.)
    tau, delay, gain, equilibrium, initial = 15., 3.4, .2, 125., 160.
    hr = equilibrium+(initial-equilibrium)*np.exp(-t/tau)
    for at, delta in [(0,200), (40,-200), (80,150), (120,-200)]:
        hr += gain*delta*(-np.expm1(-np.maximum(t-at-delay,0)/tau))
    result = p1d.fit(np.r_[np.arange(-10.,0),t], np.r_[np.full(10,100.),power],
                     np.r_[np.linspace(175,165,10),hr],
                     dict(use_pre_window=True, initialization_mode='estimated_equilibrium',
                          equilibrium_bounds=[0.,250.], n_starts=2))
    np.testing.assert_allclose([p['estimate'] for p in result['parameters'].values()],
                               [gain,delay,tau,equilibrium], atol=1e-4)
    assert result['uncertainty']['p'] == 4
    assert result['uncertainty']['N'] == len(t)
    assert result['uncertainty']['rank'] == 4
    assert result['parameters']['B']['se'] is not None
    assert result['initial_conditions']['HR0'] == initial
    assert result['initial_conditions']['x0'] == pytest.approx(initial-equilibrium, abs=1e-4)
    assert result['initial_conditions']['HR0_method'] == 'first_segment_sample'
    assert 'K_B' in result['identifiability']['correlations']
    assert len(result['effective_bounds']['lower']) == 4
    assert result['series']['predicted'][0] == initial


def test_nonequilibrium_needs_positive_residual_degrees_of_freedom():
    with pytest.raises(ValueError, match='insufficient_residual_degrees_of_freedom'):
        p1d.fit(np.arange(4.), np.ones(4), np.ones(4)*120,
                 dict(initialization_mode='estimated_equilibrium', equilibrium_bounds=[0.,250.]))


@pytest.mark.parametrize('extra', [dict(model_structure='short_transient'), dict(initialization_protocol='legacy_v1'),
                                  dict(equilibrium_bounds=[100.,100.]), dict(equilibrium_bounds=[None,250.])])
def test_rejects_incompatible_initialization_settings(extra):
    with pytest.raises(ValueError):
        p1d.validate_config(dict({'initialization_mode':'estimated_equilibrium','equilibrium_bounds':[0.,250.]}, **extra))


def test_unused_prewindow_hr_does_not_invalidate_estimated_equilibrium():
    t = np.arange(-10.,30.)
    power = np.where(t<0,100.,300.)
    hr = np.where(t<0,np.nan,140.)
    config = dict(use_pre_window=True,initialization_mode='estimated_equilibrium',equilibrium_bounds=[0.,250.],n_starts=2)
    r = p1d.fit(t,power,hr,config)
    assert r['identification_valid']
    assert r['initial_conditions']['P0'] == 100
    assert r['pre_window']['observed'] == [None]*10
    assert not r['pre_window']['signals_finite']
    power[0] = np.nan
    with pytest.raises(ValueError, match='pre_window_nonfinite'):
        p1d.fit(t,power,hr,config)


def test_accepted_numeric_bounds_are_normalized_before_fitting():
    config = p1d.validate_config(dict(initialization_mode='estimated_equilibrium',equilibrium_bounds=['0','250'],n_starts=2))
    assert config['equilibrium_bounds'] == [0.,250.]
    r = p1d.fit(np.arange(20.),np.ones(20)*100,np.ones(20)*120,config)
    assert r['identification_valid']
