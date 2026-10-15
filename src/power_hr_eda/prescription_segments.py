"""Observed continuous segments; missing data and timer pauses are never filled."""
import numpy as np
import pandas as pd


def timer_intervals(events,origin):
    intervals=[];stop=None
    for event in sorted((e for e in events if e.get('event')=='timer' and e.get('timestamp') is not None),
                        key=lambda e:e['timestamp']):
        time=(pd.Timestamp(event['timestamp'])-origin).total_seconds()
        kind=str(event.get('event_type',''))
        if kind.startswith('stop') and stop is None: stop=time
        elif kind=='start' and stop is not None:
            if time>stop: intervals.append((stop,time))
            stop=None
    return intervals


def annotate_segments(frame,pauses):
    out=frame.copy();time=out.elapsed_seconds.to_numpy(float)
    if not np.isfinite(time).all() or np.any(np.diff(time)<=0):
        raise ValueError('Expected finite increasing timestamps')
    boundary=np.r_[True,np.diff(time)!=1]
    paused=np.zeros(len(out),dtype=bool)
    for start,end in pauses:
        paused|=(time>=start)&(time<end)
        boundary[1:]|=((start>time[:-1])&(start<=time[1:]))|((end>time[:-1])&(end<=time[1:]))
    power=out.power_w.to_numpy(float);hr=out.heart_rate_bpm.to_numpy(float)
    out['power_observed']=np.isfinite(power)&(power>=0)
    out['hr_observed']=np.isfinite(hr)&(hr>0)
    out['timer_paused']=paused
    out['power_target_valid']=out.power_observed&out.prescription_kind.isin(['power','maximal'])
    out['dynamics_target_valid']=out.power_target_valid&out.hr_observed
    for name,valid in [('power',out.power_observed.to_numpy()),('hr',out.hr_observed.to_numpy()),
                       ('dynamics',(out.power_observed&out.hr_observed).to_numpy())]:
        starts=valid&(boundary|np.r_[True,~valid[:-1]])
        out[name+'_segment_id']=np.where(valid,np.cumsum(starts),0)
    return out


def segment_tables(workout_id,frame):
    segments=[];fragments=[]
    totals=frame[frame.lap_index>0].groupby('lap_index').size()
    for signal in ['power','hr','dynamics']:
        for segment_id,part in frame[frame[signal+'_segment_id']>0].groupby(signal+'_segment_id'):
            segments.append(dict(workout_id=workout_id,signal=signal,segment_id=int(segment_id),
                start_elapsed_s=float(part.elapsed_seconds.iloc[0]),end_elapsed_s=float(part.elapsed_seconds.iloc[-1]),
                sample_count=len(part),valid_prescribed_samples=int(part.power_target_valid.sum()),
                first_record_index=int(part.record_index.iloc[0]),last_record_index=int(part.record_index.iloc[-1])))
            for lap,fragment in part[part.lap_index>0].groupby('lap_index'):
                fragments.append(dict(workout_id=workout_id,signal=signal,segment_id=int(segment_id),lap_index=int(lap),
                    start_elapsed_s=float(fragment.elapsed_seconds.iloc[0]),end_elapsed_s=float(fragment.elapsed_seconds.iloc[-1]),
                    sample_count=len(fragment),all_exported_lap_samples_present=bool(len(fragment)==totals[lap])))
    return segments,fragments
