"""Estimation boundary: called only by an explicitly started user job."""
import hashlib
import platform
from pathlib import Path
import numpy as np
import scipy
from study_app.scientific.frozen.power import dynamics,ar
from study_app.scientific.frozen.power.data import Segment
from study_app.scientific.frozen.hr.models import p1d
from study_app.scientific.frozen.hr import population
from .preprocessing import parts_for
from .results import evaluate_workout,aggregate
from .repository import clean


class IdentificationFailure(ValueError):
    def __init__(self,message,diagnostic):
        super().__init__(message)
        self.diagnostic=clean(diagnostic)


def fit_models(repo,experiment,progress):
    config=experiment['config']; aid=experiment['athlete_id']
    power=[];parts=[];workouts=[repo.get(i,aid) for i in experiment['split']['train']]
    for w in workouts:
        ps,hs=parts_for(w,True);power.extend(ps);parts.extend(hs)
    progress('Stima potenza ausiliaria: ordine 2 + AR(2)')
    dynamic,statistics=dynamics.fit_response(power,2,starts=6,max_nfev=250,seed=42)
    if not statistics['converged']:raise ValueError('Fit potenza non convergente: nessuna pubblicazione')
    residuals=[Segment(p.workout_id,p.segment_id,p.time,p.residual-dynamic.response(p.target),p.target) for p in power]
    noise=ar.fit_ar(residuals,2)
    if not noise.stable: raise ValueError('AR non stazionario: nessuna pubblicazione')
    power_bundle={'dynamics':dynamic.to_dict(),'ar':noise.to_dict(),'seed':42,'paths':1000}
    fits=[];c=config['hr']
    for i,part in enumerate(parts):
        progress(f'Fit HR {i+1}/{len(parts)}')
        try:
            fit=p1d.fit(part['time'],part['power'],part['hr'],c);fit.pop('series',None)
            fit['status']='fitted' if fit['identification_valid'] else 'failed'
        except (ValueError,np.linalg.LinAlgError) as exc: fit={'status':'failed','error':str(exc)}
        fits.append({**fit,'segment_id':part['id'],'activity_id':part['workout_id']})
    segments=[{'id':p['id'],'activity_id':p['workout_id'],'sha256':experiment['workout_hashes'][p['workout_id']]} for p in parts]
    manifest={'id':experiment['id'],'config':c,'model':p1d.metadata(c),'model_structure':'p1d_full',
        'dataset':{'segments':segments},'parameter_bounds':{'keys':['K','L','tau','B'],'lower':c['lower']+[60.],'upper':c['upper']+[200.]},
        'split':{'unit':'activity','assignments':{'train':[p['id'] for p in parts],'validation':[]}}}
    progress('Screening e popolazione HR: riferimenti esclusivamente train')
    analysis=population.analyze(manifest,fits,config['population'],train_initial_hr={p['id']:float(p['hr'][0]) for p in parts})
    if analysis['status']!='estimated':
        # Preserve every failed/screened fit, even when no model can be published.
        raise IdentificationFailure(analysis.get('reason','Popolazione HR non stimabile'),
            {'experiment_id':experiment['id'],'fits':fits,'analysis':analysis,'power':power_bundle,'power_statistics':statistics})
    x=np.concatenate([p['power'] for p in parts]);y=np.concatenate([p['hr'] for p in parts])
    beta,_,rank,_=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)
    if rank!=2: raise ValueError('Baseline statica non identificabile')
    hr={'manifest':manifest,'analysis':analysis,'static':{'beta':beta.tolist(),'samples':len(y)}}
    model={'experiment_id':experiment['id'],'config':config,'split':experiment['split'],'workout_hashes':experiment['workout_hashes'],
        'raw_hashes':{w['id']:w['raw_sha256'] for group in experiment['split'].values() for w in [repo.get(i,aid) for i in group]},
        'train_period':[min(w['start_time'] for w in workouts),max(w['start_time'] for w in workouts)],
        'domain':{'power_quantiles_w':np.quantile(x,[0,.25,.5,.75,1]).tolist(),'segment_durations_s':[float(p['time'][-1]) for p in parts],
            'workout_durations_s':[w['duration_s'] for w in workouts],'samples':len(x)},
        'power':power_bundle,'power_statistics':statistics,'hr':hr,'fits':fits,
        'software':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
        'code_sha256':{str(p.relative_to(Path(__file__).parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parents[1].rglob('*.py') if 'tests' not in p.parts}}
    validation=[]
    for wid in experiment['split']['validation']:
        progress(f'Validation {len(validation)+1}/{len(experiment["split"]["validation"])}')
        validation.append(evaluate_workout(repo.get(wid,aid),model))
    model['validation']={'workouts':validation,'aggregate':aggregate(validation)}
    return clean(model)
