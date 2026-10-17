"""Unified decomposition: ablations, frozen CLI and reproducible artifacts."""
import importlib
import json
from pathlib import Path
import sys
import uuid

import numpy as np
import pandas as pd
import pytest
from scipy.signal import lfilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def mod(name):
    return importlib.import_module('power_response_estimation.'+name)


def sample_model():
    dynamic = mod('dynamics').ResponseModel(2, [1., -1.2, .32], [-.75,.25,.1], 9.)
    ar = mod('ar').ARModel(2, 2., [.5,0.], 2, sigma2=3.)
    return mod('model').DecompositionModel(dynamic, ar, seed=42, paths=5)


def test_clipping_is_output_only_and_mean_is_expectation_after_clipping():
    model = sample_model()
    model.ar.intercept = 0.
    s = mod('data').Segment('zero', 1, np.arange(200), np.zeros(200), np.zeros(200))
    table = model.decompose([s])
    latent = mod('ar').simulate_workout(model.ar, [s], seed=model.seed, paths=model.paths)[0][0]
    np.testing.assert_array_equal(table.ar_sample_w, latent)
    assert np.any(latent < 0)
    simulated, _ = mod('model').compose(table, mode='simulation')
    np.testing.assert_array_equal(simulated, np.maximum(latent, 0))
    mean, _ = mod('model').compose(table)
    sd = np.sqrt(mod('ar').stationary_state(model.ar)[1][0, 0])
    np.testing.assert_allclose(mean, sd/np.sqrt(2*np.pi))
    np.testing.assert_array_equal(mod('model').compose(table, ar=False)[0], 0)


def test_all_four_component_combinations_and_residuals():
    target = np.array([100.,100.,200.,200.,200.,100.])
    segment = mod('data').Segment('w',1,np.arange(6),np.arange(6.),target)
    model = sample_model()
    table = model.decompose([segment])
    r = np.array([0.,0.,-75.,-65.,-44.,43.])
    for dynamic in [False,True]:
        for ar in [False,True]:
            p, error = mod('model').compose(table, dynamic=dynamic, ar=ar, mode='mean')
            expected = target+(r if dynamic else 0)+(4. if ar else 0)
            np.testing.assert_allclose(p, expected)
            np.testing.assert_allclose(error, target+np.arange(6.)-expected)
    # The accessory dynamic fitting mean (9 W) is not added again.
    assert table.ar_mean_w.iloc[0] == 4.
    np.testing.assert_allclose(table.real_w, table.target_w+table.response_w+table.final_residual_w)


def test_ablations_reuse_same_ar_path_without_refitting_or_observed_feedback():
    model = sample_model()
    s = mod('data').Segment('w',1,np.arange(100),np.zeros(100),np.r_[np.full(50,100.),np.full(50,200.)])
    a = model.decompose([s])
    s.residual[:] = 10000
    b = model.decompose([s])
    np.testing.assert_array_equal(a.ar_sample_w,b.ar_sample_w)
    p, _ = mod('model').compose(a,dynamic=True,ar=True,mode='simulation')
    without, _ = mod('model').compose(a,dynamic=False,ar=True,mode='simulation')
    np.testing.assert_allclose(p-without,a.response_w)
    np.testing.assert_allclose(a.innovation_w.iloc[:2], [np.nan,np.nan], equal_nan=True)


def test_gap_reset_and_metrics_window_support():
    model = sample_model()
    S = mod('data').Segment
    table = model.decompose([S('w',1,np.array([0,1,2]),np.array([1.,2.,3.]),np.array([100.,100.,200.])),
                             S('w',2,np.array([10,11]),np.array([4.,5.]),np.array([300.,300.]))])
    assert table.input_w.tolist() == [0.,0.,100.,0.,0.]
    assert table.response_w.iloc[3] == 0.
    stats=mod('model').configuration_metrics(table,dynamic=False,ar=False,mode='mean',start=1,end=10)
    assert stats['n'] == 3
    assert stats['rmse_w'] == pytest.approx(np.sqrt(29/3))
    empty=mod('model').configuration_metrics(table,dynamic=False,ar=False,mode='mean',start=4,end=8)
    assert empty['n'] == 0 and empty['rmse_w'] is None


def make_dataset(folder):
    source=folder/'data'; (source/'samples').mkdir(parents=True)
    rng=np.random.default_rng(12)
    for i in range(6):
        target=np.repeat(rng.choice([100.,200.,300.],15),20)
        r=lfilter([-.75,.25,.1],[1.,-1.2,.32],np.r_[0.,np.diff(target)])
        residual=r+2.+lfilter([1.],[1.,-.5],rng.normal(0,.3,len(target)))
        pd.DataFrame(dict(timestamp=f'2025-01-0{i+1}T00:00:00Z',elapsed_seconds=np.arange(len(target)),
            power_w=target+residual,power_target_w=target,timer_paused=False,power_segment_id=1,lap_index=1)).to_csv(source/'samples'/f'{i}.csv.gz',index=False)
    split=folder/'split.json'
    split.write_text(json.dumps(dict(train=['0','1','2'],validation=['3','4'],test=['5'])))
    return source,split


def test_fit_test_share_single_bundle_and_output_directory():
    folder=ROOT/'tests/_generated'/('unified_'+uuid.uuid4().hex); folder.mkdir(parents=True)
    source,split=make_dataset(folder); output=folder/'power_response_estimation'
    cli=mod('cli')
    cli.main(['fit','--input',str(source),'--split-file',str(split),'--output',str(output),'--orders','2','--starts','2','--max-nfev','120','--paths','5'])
    bundle=json.loads((output/'model.json').read_text())
    assert bundle['selected_order'] == 2
    assert bundle['split']['train'] == ['0','1','2']
    before=(output/'model.json').read_bytes()
    assert set(pd.read_csv(output/'predictions.csv')['split']) == {'validation'}
    cli.main(['test','--output',str(output),'--split','test'])
    assert (output/'model.json').read_bytes() == before
    result=cli.read_results(output)
    assert set(result['splits']) == {'validation','test'}
    assert set(result['splits']['test']['workouts']) == {'5'}
    predictions = pd.read_csv(output/'predictions.csv', dtype={'workout_id':str})
    assert len(predictions) == 900
    assert set(predictions['split']) == {'validation','test'}
    for split_name, split_result in result['splits'].items():
        for wid, data in split_result['workouts'].items():
            rows = predictions[(predictions['split']==split_name) & (predictions.workout_id==wid)]
            np.testing.assert_allclose(rows.response_w, data['r'])
            np.testing.assert_allclose(rows.ar_sample_w, data['arSample'])
            np.testing.assert_allclose(rows.predicted_mean_w, np.array(data['target'])+data['r']+data['arMean'])
            np.testing.assert_allclose(rows.predicted_simulation_w, np.array(data['target'])+data['r']+data['arSample'])
            np.testing.assert_allclose(rows.residual_mean_w, rows.real_w-rows.predicted_mean_w)
            np.testing.assert_allclose(rows.residual_simulation_w, rows.real_w-rows.predicted_simulation_w)
            np.testing.assert_allclose(rows.final_residual_w, rows.real_w-rows.target_w-rows.response_w)
            assert rows.innovation_w.iloc[:2].isna().all()
    assert (output/'index.html').exists()
    assert not any(p.is_dir() for p in output.iterdir())
    with pytest.raises(FileExistsError):
        cli.main(['fit','--input',str(source),'--split-file',str(split),'--output',str(output),'--orders','2'])
    cli.main(['fit','--input',str(source),'--split-file',str(split),'--output',str(output),'--orders','2','--starts','1','--max-nfev','120','--paths','5','--overwrite'])
    assert set(cli.read_results(output)['splits']) == {'validation'}
    assert set(pd.read_csv(output/'predictions.csv')['split']) == {'validation'}
