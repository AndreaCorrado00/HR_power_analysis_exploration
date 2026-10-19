import numpy as np
from study_app.scientific.frozen.joint.simulation import metrics
from study_app.scientific.adapters import simulate_chain,simulate_hr
from .preprocessing import parts_for
from .repository import clean


def score_series(series):
    t=np.asarray(series['time'],float); observed=np.asarray(series['hr'],float)
    result=[]
    for window,mask in [('all',np.ones(len(t),bool)),('initial',t<180),('tail',t>=180)]:
        for name,key in [('chain','hr_chain'),('real_power','hr_real_power'),('target','hr_target'),('static','hr_static')]:
            if key not in series: continue
            lo=np.asarray(series['hr_low'],float)[mask] if name=='chain' else None
            hi=np.asarray(series['hr_high'],float)[mask] if name=='chain' else None
            result.append({'window':window,'model':name,**metrics(observed[mask],np.asarray(series[key],float)[mask],lo,hi)})
    return result


def evaluate_workout(workout,model):
    _,parts=parts_for(workout,False);results=[]; failures=[]
    a=model['hr']['analysis'];theta=np.asarray(a['model']['mean'])[None,:]
    for part in parts:
        try:
            pred=simulate_chain(part['target'],model,key=part['id'])
            oracle=simulate_hr(part['power'][None,:],theta,a['B_reference']['A'],a['HR0_reference']['mean'])[0]
            direct=simulate_hr(part['target'][None,:],theta,a['B_reference']['A'],a['HR0_reference']['mean'])[0]
            beta=model['hr']['static']['beta']
            s=dict(time=part['time'],elapsed=part['elapsed'],target=part['target'],power=part['power'],hr=part['hr'],
                power_mean=pred['power']['mean'],power_low=pred['power']['lower'],power_high=pred['power']['upper'],
                hr_chain=pred['hr']['mean'],hr_low=pred['hr']['lower'],hr_high=pred['hr']['upper'],
                hr_real_power=oracle,hr_target=direct,hr_static=beta[0]+beta[1]*np.asarray(pred['power']['mean']))
            results.append({'id':part['id'],'series':clean(s),'metrics':score_series(s)})
        except ValueError as exc: failures.append({'segment_id':part['id'],'reason':str(exc)})
    combined={k:np.concatenate([np.asarray(p['series'][k],float) for p in results]) for k in results[0]['series']} if results else {}
    return {'workout_id':workout['id'],'source_name':workout['source_name'],'parts':results,'failures':failures,
        'metrics':score_series(combined) if combined else [],'status':'predicted' if results else 'failed'}


def aggregate(workouts):
    rows=[]
    for window in ('all','initial','tail'):
        for model in ('chain','real_power','target','static'):
            selected=[m for w in workouts for m in w['metrics'] if m['window']==window and m['model']==model and m['N']>0]
            if not selected: continue
            row={'window':window,'model':model,'workouts':len(selected),'N':sum(m['N'] for m in selected)}
            for key in ('MAE','RMSE','bias','residual_sd','coverage','width'):
                vals=[m[key] for m in selected if m[key] is not None]
                row[key]=float(np.mean(vals)) if vals else None
            rows.append(row)
    return rows
