from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from .preprocessing import parts_for
from .repository import digest
from study_app.scientific.adapters import load_frozen_config


def split_workouts(workouts,cutoff,timezone):
    boundary=datetime.strptime(cutoff,'%Y-%m-%d').replace(tzinfo=ZoneInfo(timezone))
    result={'train':[],'validation':[]}
    for w in sorted(workouts,key=lambda x:(x['start_time'],x['id'])):
        dt=datetime.fromisoformat(w['start_time'].replace('Z','+00:00'))
        if dt.tzinfo is None: raise ValueError('Timestamp attività senza fuso')
        result['train' if dt<boundary else 'validation'].append(w['id'])
    return result


def create_experiment(repo,aid,cutoff,timezone='Europe/Rome'):
    datasets=repo.list('datasets',aid)
    if not datasets: raise ValueError('Importare un dataset')
    revision=datasets[0];workouts=[repo.get(i,aid) for i in revision['workout_ids']]
    return repo.create('experiments',aid,{'dataset_revision_id':revision['id'],'split':split_workouts(workouts,cutoff,timezone),
        'cutoff':cutoff,'timezone':timezone,'config':load_frozen_config(),'workout_hashes':{w['id']:w['sha256'] for w in workouts}})


def preflight(repo,experiment_id):
    exp=repo.get(experiment_id);counts={};reasons=[]
    for group,ids in exp['split'].items():
        ps=hs=pn=hn=observed=0;included=[]
        for wid in ids:
            w=repo.get(wid,exp['athlete_id'])
            if w['sha256']!=exp['workout_hashes'][wid]: raise ValueError('Revisione dati alterata')
            power,hr=parts_for(w,training=group=='train')
            ps+=len(power);hs+=len(hr);pn+=sum(len(p.time) for p in power);hn+=sum(len(p['time']) for p in hr)
            observed+=sum(int(np.isfinite(p['hr']).sum()) for p in hr)
            included.append({'id':wid,'source_name':w['source_name'],'power_segments':len(power),'hr_segments':len(hr),'reasons':w['reasons']})
        counts[group]={'activities':len(ids),'power_segments':ps,'hr_segments':hs,'power_samples':pn,'hr_samples':hn,'observed_hr_samples':observed,'workouts':included}
        if not ps or not hs: reasons.append(f'{group}: supporto potenza/HR insufficiente')
        if not observed: reasons.append(f'{group}: nessun campione HR osservato sul supporto valutabile')
    if counts['train']['hr_segments']<5: reasons.append('Train: meno di 5 tratti HR; popolazione non stimabile')
    result={'counts':counts,'blocking_reasons':reasons,'can_start':not reasons,'config':exp['config'],
        'assumptions':['B=A+K·P0; A e HR0 esclusivamente dal train','Nessuna calibrazione HR validation','Ordine potenza 2 fisso + AR(2)','Target ricostruito: validation retrospettiva','Fasce 95% di variabilità parziale; nessun rumore residuo HR']}
    result['hash']=digest({'experiment':exp['sha256'],'preflight':result})
    return result
