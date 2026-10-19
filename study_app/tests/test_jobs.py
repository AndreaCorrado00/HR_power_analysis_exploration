import pytest
from study_app.backend.jobs import JobService
from study_app.backend.repository import Repository
from study_app.backend.experiments import create_experiment,preflight
from study_app.tests.helpers import synthetic_workout,synthetic_model


def test_job_failure_is_persisted_without_publishing_model(tmp_path):
    repo=Repository(tmp_path);a=repo.create_athlete(dict(first_name='A',last_name='B',age=30))
    exp=repo.create('experiments',a['id'],{'split':{'train':[],'validation':[]}})
    service=JobService(repo,execute=False)
    job=repo.create('jobs',a['id'],{'experiment_id':exp['id'],'status':'queued'})
    def fail(*args,**kwargs): raise ValueError('population insufficient')
    service.run(job['id'],fitter=fail)
    assert repo.get(job['id'])['status']=='failed'
    assert repo.list('models')==[]
    assert 'population insufficient' in repo.get(job['id'])['error']


def test_attempt_keys_allow_explicit_retry_but_not_double_start(tmp_path):
    repo=Repository(tmp_path);a=repo.create_athlete(dict(first_name='A',last_name='B',age=30))
    ids=[repo.create('workouts',a['id'],synthetic_workout('2026-01-01T00:00:00Z',str(i)))['id'] for i in range(5)]
    ids.append(repo.create('workouts',a['id'],synthetic_workout())['id'])
    repo.create('datasets',a['id'],{'workout_ids':ids})
    exp=create_experiment(repo,a['id'],'2026-10-01')
    check=preflight(repo,exp['id']);assert check['can_start']
    service=JobService(repo,execute=False)
    job=service.start(exp['id'],check['hash'],'attempt-one')
    assert service.start(exp['id'],check['hash'],'attempt-one')['id']==job['id']
    assert service.start(exp['id'],check['hash'],'other-click')['id']==job['id']
    def fail(*args):raise ValueError('Explicit retry required')
    service.run(job['id'],fitter=fail)
    second=service.start(exp['id'],check['hash'],'attempt-two')
    assert second['id']!=job['id']
    service.run(second['id'],fitter=lambda r,e,p:synthetic_model(e))
    assert repo.get(second['id'])['status']=='succeeded'
    assert len(repo.list('models',a['id']))==1
    assert repo.get(job['id'])['status']=='failed'


def test_restart_does_not_resume_pending_job(tmp_path):
    repo=Repository(tmp_path);a=repo.create_athlete(dict(first_name='A',last_name='B',age=30))
    job=repo.create('jobs',a['id'],{'status':'running','experiment_id':'not-executed'})
    service=JobService(repo,execute=False)
    assert repo.get(job['id'])['status']=='interrupted'
    assert repo.list('models')==[]
