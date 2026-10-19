import numpy as np
import pandas as pd
from study_app.scientific.adapters import rules_for_ftp
from study_app.scientific.frozen.data.fit_reader import read_fit_activity
from study_app.scientific.frozen.data.prescriptions import extract_laps,recognize_blocks,is_assigned
from study_app.scientific.frozen.data.prescription_cli import _samples
from study_app.scientific.frozen.data.prescription_segments import annotate_segments,timer_intervals
from study_app.scientific.frozen.power.data import segment_frame
from .repository import clean


def prepare_workout(path,ftp):
    activity=read_fit_activity(path)
    if activity.parse_error or activity.records.empty: raise ValueError(activity.parse_error or 'FIT senza campioni')
    rules=rules_for_ftp(ftp) if ftp else rules_for_ftp(325)
    laps,assignment=extract_laps(activity,rules)
    # The historical recognizer mutates/returns its annotated lap collection.
    recognize_blocks(laps,rules)  # annotates laps in place; return value is blocks
    frame=_samples(activity,assignment,laps)
    if not ftp:
        frame['power_target_w']=np.nan; frame['prescription_kind']='unassigned'
    origin=pd.Timestamp(frame.timestamp.iloc[0])
    frame=annotate_segments(frame,timer_intervals(activity.messages.get('event',[]),origin))
    dt=np.diff(frame.elapsed_seconds.to_numpy(float))
    starts=[pd.Timestamp(e['timestamp']).isoformat() for e in activity.messages.get('event',[]) if e.get('event')=='timer' and e.get('event_type')=='start' and e.get('timestamp')]
    reasons=[]
    if not ftp: reasons.append('FTP mancante: regole da configurare')
    if not laps: reasons.append('Lap mancanti: target non ricostruibile')
    if not all(is_assigned(lap) for lap in laps): reasons.append('Non tutti i lap sono assegnati')
    parts,coverage=segment_frame(frame,'preview',split_at_prescription=False)
    result=clean(dict(start_time=origin.isoformat(),timer_start=min(starts) if starts else None,
        duration_s=float(frame.elapsed_seconds.iloc[-1]),series=frame.to_dict(orient='list'),laps=laps,
        rules=rules if ftp else None,reasons=reasons,eligible_power=not reasons and bool(parts),
        eligible_hr=not reasons and any(len(p.time)>=301 for p in parts),
        quality={**coverage,'missing_hr':int(frame.heart_rate_bpm.isna().sum()),
            'non_1s_steps':int((dt!=1).sum()),'hr_jumps_over_10':int(((abs(np.diff(frame.heart_rate_bpm))>10)&(dt==1)).sum()),
            'hr_outside_30_240':int(((frame.heart_rate_bpm<30)|(frame.heart_rate_bpm>240)).sum())}))
    _,hr=parts_for({**result,'id':'preview'},training=True)
    result['eligible_hr']=bool(hr)
    result['hr_reasons']=[] if hr else ['Nessun tratto HR train valido di almeno 301 campioni consecutivi (300 s)']
    result['quality']['usable_hr_train_samples']=sum(len(p['time']) for p in hr)
    result['quality']['usable_hr_train_segments']=len(hr)
    return result


def parts_for(workout,training=False):
    if not workout.get('eligible_power'): return [],[]
    frame=pd.DataFrame(workout['series'])
    power,_=segment_frame(frame,workout['id'],split_at_prescription=False)
    indexed=frame.set_index('elapsed_seconds'); hr_parts=[]
    for part in power:
        hr=indexed.loc[part.time,'heart_rate_bpm'].to_numpy(float)
        valid=np.isfinite(hr) if training else np.ones(len(hr),bool)
        edges=np.r_[0,np.flatnonzero(valid[1:]!=valid[:-1])+1,len(hr)]
        for a,b in zip(edges[:-1],edges[1:]):
            if not valid[a] or b-a<301: continue
            hr_parts.append(dict(id=f'{workout["id"]}_{part.segment_id}_{a}',workout_id=workout['id'],
                time=part.time[a:b]-part.time[a],elapsed=part.time[a:b],
                power=(part.target+part.residual)[a:b],target=part.target[a:b],hr=hr[a:b]))
    return power,hr_parts
