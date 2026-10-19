from concurrent.futures import ProcessPoolExecutor
from .repository import Repository
from .experiments import preflight
from .identification import fit_models


def _worker(root,job_id):
    service=JobService(Repository(root),execute=False,recover=False)
    service.run(job_id)


class JobService:
    def __init__(self,repo,execute=True,recover=True):
        self.repo=repo;self.pool=ProcessPoolExecutor(max_workers=1) if execute else None
        if recover:
            for job in repo.list('jobs'):
                if job['status'] in ('queued','running'):repo.mutate(job['id'],{'status':'interrupted','error':'Servizio interrotto: nessuna ripresa automatica'})

    def start(self,experiment_id,expected_hash,key):
        with self.repo.lock:
            exp=self.repo.get(experiment_id)
            for job in self.repo.list('jobs',exp['athlete_id']):
                if job['experiment_id']==experiment_id and (job.get('idempotency_key')==key or job['status'] in ('queued','running')): return job
            check=preflight(self.repo,experiment_id)
            if check['hash']!=expected_hash: raise ValueError('Preflight obsoleto: ricaricare il riepilogo')
            if not check['can_start']:raise ValueError('; '.join(check['blocking_reasons']))
            job=self.repo.create('jobs',exp['athlete_id'],{'experiment_id':experiment_id,'status':'queued','idempotency_key':key,'log':[]})
            if self.pool:self.pool.submit(_worker,str(self.repo.root),job['id'])
            return job

    def run(self,job_id,fitter=fit_models):
        job=self.repo.get(job_id);exp=self.repo.get(job['experiment_id'])
        def progress(message):
            state=self.repo.get(job_id)
            self.repo.mutate(job_id,{'status':'running','message':message,'log':state.get('log',[])+[message]})
        try:
            progress('Identificazione avviata esplicitamente')
            result=fitter(self.repo,exp,progress)
            model=self.repo.create('models',exp['athlete_id'],result)
            self.repo.mutate(job_id,{'status':'succeeded','model_id':model['id'],'message':'Completato'})
        except Exception as exc:
            diagnostic=None
            if hasattr(exc,'diagnostic'):
                diagnostic=self.repo.create('diagnostics',exp['athlete_id'],exc.diagnostic)['id']
            self.repo.mutate(job_id,{'status':'failed','error':str(exc),'diagnostic_id':diagnostic})

    def close(self):
        if self.pool:self.pool.shutdown(wait=True,cancel_futures=True)
