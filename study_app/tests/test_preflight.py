from study_app.backend.experiments import split_workouts
from study_app.backend.experiments import create_experiment,preflight
from study_app.backend.repository import Repository
from study_app.tests.helpers import synthetic_workout


def test_cutoff_uses_local_midnight_and_whole_workout():
    ws=[{'id':'a','start_time':'2026-10-17T21:59:59Z'}, {'id':'b','start_time':'2026-10-17T22:00:00Z'}]
    assert split_workouts(ws,'2026-10-18','Europe/Rome')=={'train':['a'],'validation':['b']}


def test_validation_missing_hr_blocks_scoring_not_prediction_segmentation(tmp_path):
    r=Repository(tmp_path);a=r.create_athlete(dict(first_name='A',last_name='B',age=30))
    train=[r.create('workouts',a['id'],synthetic_workout('2026-01-01T00:00:00Z',str(i)))['id'] for i in range(5)]
    w=synthetic_workout();w['series']['heart_rate_bpm']=[None]*601
    val=r.create('workouts',a['id'],w)
    r.create('datasets',a['id'],{'workout_ids':train+[val['id']]})
    e=create_experiment(r,a['id'],'2026-10-01')
    p=preflight(r,e['id'])
    assert p['counts']['validation']['hr_segments']==1
    assert not p['can_start']
    assert p['counts']['validation']['observed_hr_samples']==0
