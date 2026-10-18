import numpy as np
import pandas as pd
from experiments.prescribed_joint.data import hr_parts


def frame():
    n = 905
    return pd.DataFrame(dict(elapsed_seconds=np.arange(n), power_w=np.full(n, 150.),
        power_target_w=np.full(n, 160.), heart_rate_bpm=np.full(n, 120.),
        timer_paused=False, power_segment_id=1, lap_index=1))


def test_hr_missing_only_changes_training_support():
    f = frame()
    f.loc[450, 'heart_rate_bpm'] = np.nan
    train = hr_parts(f, 'a', training=True)
    evaluation = hr_parts(f, 'a', training=False)
    assert [len(p['time']) for p in train] == [450, 454]
    assert len(evaluation) == 1 and len(evaluation[0]['time']) == 905


def test_no_reset_at_lap_but_reset_at_gap():
    f = frame()
    f.loc[100:, 'lap_index'] = 2
    f.loc[100:, 'power_target_w'] = 200
    assert len(hr_parts(f, 'a', training=True)) == 1
    f.loc[450:, 'elapsed_seconds'] += 2
    assert [len(p['time']) for p in hr_parts(f, 'a', training=True)] == [450, 455]


def test_no_interpolation_or_short_segment_fallback():
    assert hr_parts(frame().iloc[:300], 'a', training=True) == []


def test_vectorized_hr_matches_existing_simulator():
    from experiments.prescribed_joint.simulation import hr_trajectories
    from webapp.model_identification_app.backend.models.p1d import simulate
    rng = np.random.default_rng(3)
    power = rng.uniform(0,400,(4,500))
    theta = np.array([[.3,0.,40],[.2,3.7,120],[.4,30,1.5],[.1,5.1,1800]])
    actual = hr_trajectories(power,theta,80.,110.)
    for i in range(4):
        expected = simulate(np.arange(500),power[i],110.,[*theta[i],80.+theta[i,0]*power[i,0]],
                            power[i,0],'p1d_full','estimated_equilibrium')
        np.testing.assert_allclose(actual[i],expected,rtol=1e-12,atol=1e-10)


def test_hr_simulation_is_causal_and_has_no_observed_hr_input():
    from experiments.prescribed_joint.simulation import hr_trajectories
    theta=np.array([[.3,4.5,40.]])
    power=np.full((1,500),150.)
    base=hr_trajectories(power,theta,80.,110.)
    power[:,250:]=300.
    changed=hr_trajectories(power,theta,80.,110.)
    np.testing.assert_array_equal(changed[:,:255],base[:,:255])
    assert changed[0,-1]>base[0,-1]


def test_metrics_exclude_missing_and_use_observed_minus_predicted():
    from experiments.prescribed_joint.simulation import metrics
    m=metrics(np.array([1.,3.,np.nan]),np.array([0.,1.,100.]),np.zeros(3),np.full(3,2.))
    assert m['N']==2 and m['bias']==1.5 and m['coverage']==.5
    assert m['RMSE']==np.sqrt(2.5)


def test_joint_prediction_never_uses_heldout_power_or_hr():
    from experiments.prescribed_joint.evaluate import predict_part
    from power_response_estimation.model import DecompositionModel
    from power_response_estimation.dynamics import ResponseModel
    from power_response_estimation.ar import ARModel
    part=hr_parts(frame().iloc[:350], 'a', training=False)[0]
    hr=dict(analysis=dict(status='estimated',model=dict(keys=['K','L','tau'],mean=[.3,4.,40.],
        covariance=np.diag([.001,.01,2.]).tolist()),B_reference=dict(A=80.),HR0_reference=dict(mean=110.)),
        manifest=dict(parameter_bounds=dict(keys=['K','L','tau','B'],lower=[1e-6,0,.01,60],upper=[5,30,1800,200])),
        static=dict(beta=[80.,.3]))
    power=DecompositionModel(ResponseModel(2,[1.,-.2,.01],[0.,0.,0.],0.),
        ARModel(2,0.,[.5,.1],2,sigma2=100.))
    first=predict_part(part,power,hr,draws=50)
    part['hr'][:]=np.nan
    part['power'][:]=999.
    second=predict_part(part,power,hr,draws=50)
    for key in ['hr_chain','hr_low','hr_high','power_mean','power_low','power_high']:
        np.testing.assert_array_equal(first['series'][key],second['series'][key])


def test_summary_gives_workouts_equal_weight():
    from experiments.prescribed_joint.evaluate import aggregate
    rows=[dict(workout_id='a',window='all',model='chain',N=1000,RMSE=2.,MAE=1.,bias=0.,residual_sd=2.,coverage=.9,width=4.),
          dict(workout_id='b',window='all',model='chain',N=10,RMSE=8.,MAE=7.,bias=0.,residual_sd=8.,coverage=.5,width=10.)]
    summary=aggregate(rows)[0]
    assert summary['RMSE']==5. and summary['workouts']==2 and summary['N']==1010


def test_test_requires_unchanged_validation_and_models(tmp_path):
    from experiments.prescribed_joint.evaluate import verify_freeze
    from experiments.prescribed_joint.data import save
    from power_response_estimation.data import sha256
    import pytest
    hashes={'power':'p','hr':'h','manifest':'m'}
    with pytest.raises(ValueError): verify_freeze(tmp_path,hashes)
    save(tmp_path/'validation.json',{'result':1})
    save(tmp_path/'frozen.json',dict(hashes=hashes,validation_sha256=sha256(tmp_path/'validation.json')))
    verify_freeze(tmp_path,hashes)
    with pytest.raises(ValueError): verify_freeze(tmp_path,{**hashes,'hr':'changed'})
    save(tmp_path/'validation.json',{'result':2})
    with pytest.raises(ValueError): verify_freeze(tmp_path,hashes)
