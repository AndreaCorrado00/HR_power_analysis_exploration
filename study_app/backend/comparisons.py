from datetime import datetime
import json
from pathlib import Path
import numpy as np
from study_app.scientific.adapters import simulate_hr
from study_app.scientific.frozen.joint.simulation import metrics
from .repository import clean


def dt(value):return datetime.fromisoformat(value.replace('Z','+00:00'))


def is_prospective(prediction,model,workout):
    known=Path(__file__).parents[1]/'scientific/historical_source_hashes.json'
    historical=json.loads(known.read_text()) if known.exists() else []
    return (dt(prediction['created_at'])<dt(workout['start_time']) and dt(model['created_at'])<dt(workout['start_time'])
        and workout['raw_sha256'] not in model.get('raw_hashes',{}).values() and workout['raw_sha256'] not in historical)


def align_series(workout,scenario):
    raw=workout['series'];offset=(dt(workout['start_time'])-dt(workout.get('timer_start') or workout['start_time'])).total_seconds()
    actual=np.asarray(raw['elapsed_seconds'],float)+offset
    timeline=np.union1d(actual,np.arange(len(scenario['target']),dtype=float))
    out={'elapsed':timeline.tolist()}
    grid=np.arange(len(scenario['target']))
    signals=[('power',raw['power_w'],actual),('hr',raw['heart_rate_bpm'],actual),('target',scenario['target'],grid)]
    for group in ('power','hr'):
        for field,key in [('mean','chain' if group=='hr' else 'mean'),('lower','low'),('upper','high')]:
            signals.append((f'{group}_{key}',scenario[group][field],grid))
    for name,values,times in signals:
        series=np.full(len(timeline),np.nan);series[np.searchsorted(timeline,times)]=np.asarray(values,float);out[name]=series.tolist()
    return out


def compare(repo,prediction_id,workout_id,scenario_name):
    prediction=repo.get(prediction_id);workout=repo.get(workout_id,prediction['athlete_id']);model=repo.get(prediction['model_id'],prediction['athlete_id'])
    if workout['kind']!='workouts':raise ValueError('Attività richiesta')
    scenario=next((s for s in prediction['scenarios'] if s['name']==scenario_name),None)
    if scenario is None:raise ValueError('Scenario non trovato')
    series=align_series(workout,scenario);t=np.asarray(series['elapsed']);diag=np.full(len(t),np.nan)
    raw=workout['series'];rt=np.asarray(raw['elapsed_seconds'],float);rp=np.asarray(raw['power_w'],float)
    offset=(dt(workout['start_time'])-dt(workout.get('timer_start') or workout['start_time'])).total_seconds()
    valid=np.isfinite(rp)&(rp>=0)&~np.asarray(raw['timer_paused'],bool)
    link=valid[:-1]&valid[1:]&(np.diff(rt)==1)
    edges=np.r_[0,np.flatnonzero(~link)+1,len(rt)];resets=[];a=model['hr']['analysis']
    for start,end in zip(edges[:-1],edges[1:]):
        if not valid[start] or end-start<2:continue
        response=simulate_hr(rp[None,start:end],np.asarray(a['model']['mean'])[None,:],a['B_reference']['A'],a['HR0_reference']['mean'])[0]
        diag[np.searchsorted(t,rt[start:end]+offset)]=response
        resets.append(float(rt[start]+offset))
    series['hr_real_power']=diag.tolist()
    actual=np.asarray(series['power'],float);target=np.asarray(series['target'],float);hr=np.asarray(series['hr'],float)
    predicted=np.asarray(series['hr_chain'],float);pmean=np.asarray(series['power_mean'],float)
    common=np.isfinite(actual)&np.isfinite(target)
    # Energy: explicit ZOH only over observed consecutive 1-s intervals, never gaps.
    continuous=common[:-1]&common[1:]&(np.diff(t)==1)
    adherence={'metrics':metrics(actual,target),'observed_work_kj_common':float(actual[:-1][continuous].sum()/1000),
        'prescribed_work_kj_common':float(target[:-1][continuous].sum()/1000),'energy_support_seconds':int(continuous.sum()),
        'registered_duration_s':workout['duration_s'],'prescribed_duration_s':scenario['duration_s'],
        'paired_samples':int(common.sum()),'planned_samples':len(scenario['target']),
        'sample_coverage':float(common.sum()/len(scenario['target'])),'blocks':[]}
    for b in scenario['blocks']:
        mask=(t>=b['start_s'])&(t<b['end_s'])
        adherence['blocks'].append({**b,**metrics(actual[mask],target[mask])})
    context={}
    for field in ('temperature_c','altitude_m','cadence_rpm'):
        values=np.asarray(raw.get(field,[]),float);values=values[np.isfinite(values)]
        context[field]={'n':len(values),'min':float(values.min()),'max':float(values.max()),'mean':float(values.mean())} if len(values) else None
    at_origin=np.flatnonzero(rt+offset==0)
    hr_initial={'predicted_from_train_bpm':a['HR0_reference']['mean'],
        'observed_at_origin_bpm':raw['heart_rate_bpm'][int(at_origin[0])] if len(at_origin) else None,
        'calibration_used':False}
    return repo.create('comparisons',prediction['athlete_id'],{'prediction_id':prediction_id,'workout_id':workout_id,
        'model_id':model['id'],'scenario':scenario_name,'prospective':is_prospective(prediction,model,workout),
        'policy':prediction['policy'],'workout_sha256':workout['sha256'],'prediction_sha256':prediction['sha256'],
        'series':clean(series),'diagnostic_resets_s':resets,'quality':workout['quality'],'adherence':adherence,
        'observed_context':context,'hr_initial':hr_initial,
        'metrics':{'execution':metrics(actual,pmean,np.asarray(series['power_low']),np.asarray(series['power_high'])),
            'prior':metrics(hr,predicted,np.asarray(series['hr_low']),np.asarray(series['hr_high'])),
            'diagnostic':metrics(hr,diag)}})


def evaluation_history(repo,aid):
    return [{'id':c['id'],'model_id':c['model_id'],'workout_id':c['workout_id'],'created_at':c['created_at'],
        'prospective':c['prospective'],'metrics':c['metrics'],'adherence':c['adherence']} for c in repo.list('comparisons',aid)]
