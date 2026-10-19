from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
from urllib.parse import urlparse
from fastapi import FastAPI,UploadFile,File,Request
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from .repository import Repository,digest
from .imports import import_files,MAX_UPLOAD
from .preprocessing import prepare_workout
from .experiments import create_experiment,preflight
from .jobs import JobService
from .prescriptions import parse_prescription,resolve_targets
from .predictions import predict
from .comparisons import compare,evaluation_history


def brief(obj):
    return {k:v for k,v in obj.items() if k not in ('series','laps','fits','power_statistics','code_sha256','scenarios','validation')}


def create_app(storage=None,execute_jobs=True):
    repo=Repository(storage or Path(__file__).parents[2]/'storage')
    jobs=JobService(repo,execute=execute_jobs)
    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.close()
    app=FastAPI(title='Studio HR · Power',lifespan=lifespan)
    app.state.repo=repo;app.state.jobs=jobs
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

    @app.middleware('http')
    async def local_origin(request,call_next):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'message':'Origine non consentita'},status_code=403)
        length=request.headers.get('content-length')
        if length and int(length)>MAX_UPLOAD+1024*1024:return JSONResponse({'message':'Upload oltre 2 GiB'},status_code=413)
        response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.exception_handler(ValueError)
    def invalid(request,exc):return JSONResponse({'code':'invalid_input','message':str(exc),'details':None},status_code=422)
    @app.exception_handler(FileNotFoundError)
    def missing(request,exc):return JSONResponse({'code':'not_found','message':str(exc),'details':None},status_code=404)
    @app.get('/api/health')
    def health():return {'status':'ok','fitting':'explicit_user_action_only'}
    @app.get('/api/athletes')
    def athletes():return repo.list('athletes')
    @app.post('/api/athletes')
    def add_athlete(body:dict):return repo.create_athlete(body)
    @app.patch('/api/athletes/{aid}')
    def edit_athlete(aid:str,body:dict):return repo.update_athlete(aid,body)
    @app.post('/api/athletes/{aid}/imports')
    async def upload(aid:str,files:list[UploadFile]=File(...)):
        repo.get(aid);contents=[];total=0
        for f in files:
            content=await f.read(MAX_UPLOAD+1);total+=len(content)
            if total>MAX_UPLOAD:raise ValueError('Import oltre 2 GiB')
            contents.append((f.filename or 'upload',content))
        return await run_in_threadpool(import_files,repo,aid,contents)
    @app.post('/api/athletes/{aid}/prepare')
    def reprepare(aid:str):
        athlete=repo.get(aid)
        if not athlete.get('ftp_w'):raise ValueError('Inserire FTP prima della preparazione')
        revisions=repo.list('datasets',aid)
        if not revisions:raise ValueError('Importare attività')
        ids=[]
        for wid in revisions[0]['workout_ids']:
            old=repo.get(wid,aid)
            if hashlib.sha256((repo.root/old['raw_path']).read_bytes()).hexdigest()!=old['raw_sha256']:
                raise ValueError('FIT originale alterato: preparazione interrotta')
            prepared=prepare_workout(repo.root/old['raw_path'],athlete['ftp_w'])
            w=repo.create('workouts',aid,{**prepared,'raw_path':old['raw_path'],'raw_sha256':old['raw_sha256'],
                'source_name':old['source_name'],'previous_revision_id':wid})
            ids.append(w['id'])
        return repo.create('datasets',aid,{'workout_ids':ids,'ftp_w':athlete['ftp_w']})
    @app.get('/api/athletes/{aid}/workouts')
    def workouts(aid:str):
        revisions=repo.list('datasets',aid)
        return [brief(repo.get(w,aid)) for w in revisions[0]['workout_ids']] if revisions else []
    @app.get('/api/workouts/{wid}/series')
    def workout_series(wid:str):return repo.get(wid)
    @app.get('/api/athletes/{aid}/jobs')
    def list_jobs(aid:str):return repo.list('jobs',aid)
    @app.get('/api/jobs/{jid}')
    def job(jid:str):return repo.get(jid)
    @app.get('/api/diagnostics/{did}')
    def diagnostic(did:str):return repo.get(did)
    @app.get('/api/imports/{iid}')
    def import_report(iid:str):return repo.get(iid)
    @app.get('/api/athletes/{aid}/experiments')
    def experiments(aid:str):return repo.list('experiments',aid)
    @app.post('/api/athletes/{aid}/experiments')
    def experiment(aid:str,body:dict):return create_experiment(repo,aid,body.get('cutoff',''),body.get('timezone','Europe/Rome'))
    @app.get('/api/experiments/{eid}/preflight')
    def check(eid:str):return preflight(repo,eid)
    @app.post('/api/experiments/{eid}/start')
    def start(eid:str,body:dict):
        if not body.get('idempotency_key'):raise ValueError('Chiave idempotenza richiesta')
        return jobs.start(eid,body.get('preflight_hash'),body['idempotency_key'])
    @app.get('/api/experiments/{eid}/results')
    def result(eid:str):
        exp=repo.get(eid)
        found=[m for m in repo.list('models',exp['athlete_id']) if m['experiment_id']==eid]
        if not found:raise FileNotFoundError('Risultati non ancora disponibili')
        return found[0]
    @app.get('/api/athletes/{aid}/models')
    def models(aid:str):return [brief(m) for m in repo.list('models',aid)]
    @app.get('/api/models/{mid}')
    def model(mid:str):return repo.get(mid)
    @app.get('/api/athletes/{aid}/prescriptions')
    def prescriptions(aid:str):return repo.list('prescriptions',aid)
    @app.post('/api/athletes/{aid}/prescriptions')
    def prescription(aid:str,body:dict):
        draft=parse_prescription(body['content'],body['format']) if 'content' in body else body.get('draft',{})
        choices=body.get('choices',{})
        resolve_targets(draft,choices)
        return repo.create('prescriptions',aid,{'draft':draft,'choices':choices})
    @app.post('/api/prescriptions/{pid}/predictions')
    def prediction(pid:str,body:dict):
        p=repo.get(pid)
        return predict(repo,pid,body.get('model_id'),body.get('choices',p['choices']),body.get('paths',1000),body.get('seed',42))
    @app.get('/api/athletes/{aid}/predictions')
    def predictions(aid:str):return [brief(p) for p in repo.list('predictions',aid)]
    @app.get('/api/predictions/{pid}')
    def get_prediction(pid:str):return repo.get(pid)
    @app.post('/api/predictions/{pid}/comparisons')
    def comparison(pid:str,body:dict):return compare(repo,pid,body.get('workout_id'),body.get('scenario','centrale'))
    @app.get('/api/comparisons/{cid}')
    def get_comparison(cid:str):return repo.get(cid)
    @app.get('/api/athletes/{aid}/evaluation')
    def evaluation(aid:str):return evaluation_history(repo,aid)
    @app.get('/api/model-comparison')
    def model_comparison(left:str,right:str):
        a=repo.get(left);b=repo.get(right)
        if a['kind']!='models' or b['kind']!='models' or a['athlete_id']==b['athlete_id']:raise ValueError('Selezionare versioni di due atleti diversi')
        return {'left':brief(a),'right':brief(b),'compatible':digest(a['config'])==digest(b['config']),
            'guide':{'K':'Sensibilità matematica HR/potenza (bpm/W)','L':'Ritardo (s), non compensato a posteriori','tau':'Tempo caratteristico (s)',
                'sd':'Variabilità tra tratti; non incertezza della media','interpretation':'Parametri matematici, non biomarcatori o ranking di forma'}}
    @app.get('/api/examples/{name}')
    def example(name:str):
        if name not in ('prescription.json','prescription.csv','prescription-range.json'):raise FileNotFoundError('Esempio non disponibile')
        return FileResponse(Path(__file__).parents[1]/'examples'/name,filename=name)
    dist=Path(__file__).parents[1]/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
