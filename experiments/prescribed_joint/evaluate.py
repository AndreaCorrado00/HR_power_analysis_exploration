"""Frozen validation/test evaluation with explicit train-only HR references."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtri
from power_response_estimation.ar import simulate_residual, stationary_state
from power_response_estimation.model import DecompositionModel, clipped_normal_mean
from power_response_estimation.data import sha256
from power_response_estimation.cli import get_segments
from .data import HERE, OUTPUT, prepare, load_parts, save
from .simulation import stream, sample_parameters, hr_trajectories, metrics


def predict_part(part, power_model, hr_bundle, draws=1000):
    if not np.all(np.diff(part['time'])==1): raise ValueError('Monte Carlo requires explicit 1-s support')
    target=part['target']; n=len(target)
    response=power_model.dynamics.response(target)
    am,ac=stationary_state(power_model.ar); sd=np.sqrt(ac[0,0])
    mu=target+response+am[0]
    pmean=clipped_normal_mean(mu,sd)
    plow,phigh=np.maximum(0.,mu+ndtri(np.array([.025,.975]))[:,None]*sd)
    simulated=simulate_residual(power_model.ar,n,draws,stream(part['id'],'power'))
    latent=simulated+target+response
    clipping_fraction=float((latent<0).mean())
    simulated=np.maximum(0.,latent)
    del latent
    theta,acceptance=sample_parameters(hr_bundle,part['id'],draws)
    analysis=hr_bundle['analysis'];a=analysis['B_reference']['A'];h0=analysis['HR0_reference']['mean']
    hr_paths=hr_trajectories(simulated,theta,a,h0)
    chain=hr_paths.mean(axis=0)
    low,high=np.quantile(hr_paths,[.025,.975],axis=0)
    # Monte Carlo standard error of the plotted mean, not physiological uncertainty.
    mcse=float(np.max(hr_paths.std(axis=0,ddof=1)/np.sqrt(draws)))
    del hr_paths,simulated
    mean=np.asarray(analysis['model']['mean'])[None,:]
    oracle=hr_trajectories(part['power'][None,:],mean,a,h0)[0]
    direct=hr_trajectories(target[None,:],mean,a,h0)[0]
    beta=hr_bundle['static']['beta']
    series=dict(time=part['time'],elapsed=part['elapsed'],target=target,power=part['power'],
        power_mean=pmean,power_low=plow,power_high=phigh,hr=part['hr'],hr_chain=chain,
        hr_low=low,hr_high=high,hr_real_power=oracle,hr_target=direct,
        hr_static=beta[0]+beta[1]*pmean,hr_static_real=beta[0]+beta[1]*part['power'])
    return dict(id=part['id'],workout_id=part['workout_id'],status='predicted',series=series,
        draws=draws,parameter_acceptance=acceptance,clipped_fraction=clipping_fraction,
        max_mean_mcse_bpm=mcse)


MODELS={'chain':'hr_chain','real_power':'hr_real_power','target_direct':'hr_target',
        'static_chain':'hr_static','static_real_power':'hr_static_real'}


def score(parts, workout_id):
    series={k:np.concatenate([p['series'][k] for p in parts]) for k in parts[0]['series']}
    t=series['time']; rows=[]
    for window,mask in [('all',np.ones(len(t),bool)),('initial',t<180),('tail',t>=180)]:
        for name,key in MODELS.items():
            low=series['hr_low'][mask] if name=='chain' else None
            high=series['hr_high'][mask] if name=='chain' else None
            rows.append(dict(workout_id=workout_id,window=window,model=name,
                **metrics(series['hr'][mask],series[key][mask],low,high)))
    for name,key in [('power_common','power_mean'),('power_target_common','target')]:
        rows.append(dict(workout_id=workout_id,window='all',model=name,
            **metrics(series['power'],series[key],series['power_low'] if name=='power_common' else None,
                      series['power_high'] if name=='power_common' else None)))
    return rows


def aggregate(rows):
    result=[]
    for window,model in sorted({(r['window'],r['model']) for r in rows}):
        group=[r for r in rows if r['window']==window and r['model']==model and r['N']>0]
        if not group: continue
        item=dict(window=window,model=model,workouts=len(group),N=sum(r['N'] for r in group))
        for key in ['MAE','RMSE','bias','residual_sd','coverage','width']:
            values=[r[key] for r in group if r.get(key) is not None]
            item[key]=float(np.mean(values)) if values else None
        result.append(item)
    return result


def serializable(part):
    return {**part,'series':{k:[float(x) if np.isfinite(x) else None for x in v]
                             for k,v in part['series'].items()}}


def verify_freeze(output, hashes):
    frozen=output/'frozen.json'; validation=output/'validation.json'
    if not frozen.exists() or not validation.exists():
        raise ValueError('Run validation and freeze before inspecting test')
    saved=json.loads(frozen.read_text(encoding='utf-8'))
    if saved['hashes']!=hashes or saved['validation_sha256']!=sha256(validation):
        raise ValueError('Models or validation changed after freeze')


def evaluate(split, output=OUTPUT):
    manifest=prepare(output)
    power_path=output/'power/model.json'; hr_path=output/'hr_model.json'
    power_bundle=json.loads(power_path.read_text(encoding='utf-8'))
    hr_bundle=json.loads(hr_path.read_text(encoding='utf-8'))
    if power_bundle['split']!=manifest['split']: raise ValueError('Power split mismatch')
    expected={s['id'] for s in manifest['segments'] if s['split']=='train'}
    for group in manifest['split']:
        expected={s['id'] for s in manifest['segments'] if s['split']==group}
        if set(hr_bundle['manifest']['split']['assignments'][group])!=expected:
            raise ValueError('HR split mismatch')
    source_paths=list(HERE.glob('*.py'))+list((HERE.parents[1]/'power_response_estimation').glob('*.py'))
    backend=HERE.parents[1]/'webapp/model_identification_app/backend'
    source_paths+=list((backend/'models').glob('*.py'))+[backend/'population.py',backend/'context.py']
    hashes=dict(power=sha256(power_path),hr=sha256(hr_path),manifest=sha256(output/'manifest.json'),
                code={str(p.relative_to(HERE.parents[1])):sha256(p) for p in source_paths})
    freeze_path=output/'frozen.json'
    if split=='test':
        verify_freeze(output,hashes)
    power_model=DecompositionModel.from_dict(power_bundle['decomposition'])
    predicted=[];failures=[];rows=[]
    for part in load_parts(manifest,split):
        try:
            prediction=predict_part(part,power_model,hr_bundle)
            predicted.append(prediction)
            print(f"{split} {part['id']}: {len(part['time'])} samples",flush=True)
        except ValueError as exc:
            failures.append(dict(id=part['id'],workout_id=part['workout_id'],error=str(exc)))
    for wid in manifest['split'][split]:
        group=[p for p in predicted if p['workout_id']==wid]
        if group: rows.extend(score(group,wid))
    # Power-only scores retain every valid power sample, including short segments.
    power_parts,coverage=get_segments(power_bundle,split)
    am,ac=stationary_state(power_model.ar);sd=np.sqrt(ac[0,0])
    for wid in manifest['split'][split]:
        parts=[p for p in power_parts if p.workout_id==wid]
        real=np.concatenate([p.target+p.residual for p in parts])
        target=np.concatenate([p.target for p in parts])
        mu=np.concatenate([p.target+power_model.dynamics.response(p.target)+am[0] for p in parts])
        low,high=np.maximum(0.,mu+ndtri(np.array([.025,.975]))[:,None]*sd)
        rows.append(dict(workout_id=wid,window='all',model='power_all',
                         **metrics(real,clipped_normal_mean(mu,sd),low,high)))
        rows.append(dict(workout_id=wid,window='all',model='power_target_all',**metrics(real,target)))
    result=dict(split=split,hashes=hashes,summary=aggregate(rows),metrics=rows,failures=failures,
        power_coverage=coverage,segments=[serializable(p) for p in predicted],
        requested_segments=sum(s['split']==split for s in manifest['segments']),
        provenance='Retrospective heldout activity split; reconstructed targets; partial variability bands')
    save(output/f'{split}.json',result)
    pd.DataFrame(rows).to_csv(output/f'{split}_metrics.csv',index=False)
    if split=='validation':
        save(freeze_path,dict(hashes=hashes,hr_mode='population_B_P0_mean_HR0',
            power_selected_order=power_bundle['selected_order'],decision='No HR retuning after validation; test descriptive',
            validation_sha256=sha256(output/'validation.json')))
    from .viewer import publish
    publish(output)
    print(f'{split}: {len(predicted)} predicted, {len(failures)} failed',flush=True)
