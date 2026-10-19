from fastapi.testclient import TestClient
from study_app.backend.app import create_app
from study_app.backend.repository import Repository
from study_app.backend.imports import import_files
from study_app.backend.jobs import JobService
from study_app.backend.predictions import predict
from study_app.backend.comparisons import compare
from study_app.tests.helpers import synthetic_model,synthetic_workout


def test_import_after_reprepare_does_not_restore_old_revisions(tmp_path):
    repo=Repository(tmp_path);a=repo.create_athlete(dict(first_name='A',last_name='B',age=30,ftp_w=260))
    old=repo.create('workouts',a['id'],synthetic_workout())
    revised=repo.create('workouts',a['id'],{**synthetic_workout(),'previous_revision_id':old['id']})
    repo.create('datasets',a['id'],{'workout_ids':[revised['id']]})
    result=import_files(repo,a['id'],[('unsupported.txt',b'text')])
    assert repo.get(result['dataset_revision_id'])['workout_ids']==[revised['id']]


def test_prediction_and_comparison_remain_immutable_without_fitting(tmp_path):
    repo=Repository(tmp_path);a=repo.create_athlete(dict(first_name='A',last_name='B',age=30))
    model=repo.create('models',a['id'],synthetic_model())
    p=repo.create('prescriptions',a['id'],{'draft':{'schema_version':1,'name':'Synthetic','blocks':[{'duration_s':300,'target':{'kind':'constant','watts':150}}]},'choices':{}})
    forecast=predict(repo,p['id'],model['id'],{},paths=20)
    before=repo.get(forecast['id'])
    workout=repo.create('workouts',a['id'],synthetic_workout())
    result=compare(repo,forecast['id'],workout['id'],'centrale')
    assert result['metrics']['prior']['N']==301
    assert result['metrics']['diagnostic']['N']==601
    assert result['adherence']['energy_support_seconds']==300
    assert repo.get(forecast['id'])==before
    # A newer identification does not rewrite the previous version's verification.
    repo.create('models',a['id'],{**synthetic_model(),'split':{'train':[workout['id']],'validation':[]}})
    assert repo.get(result['id'])==result
    b=repo.create_athlete(dict(first_name='Other',last_name='Athlete',age=30))
    foreign=repo.create('workouts',b['id'],synthetic_workout())
    import pytest
    with pytest.raises(ValueError):compare(repo,forecast['id'],foreign['id'],'centrale')
