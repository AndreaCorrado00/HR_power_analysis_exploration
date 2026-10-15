"""Offline masking experiment; never fills or changes the prescribed dataset."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from power_hr_eda.fit_reader import read_fit_activity
from power_hr_eda.prescription_gaps import power_gaps

SEED=3252026
GRID=[1,2,5,10,15,30,60,120]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pauses(events,origin):
    result=[]; stopped=None
    for event in sorted((e for e in events if e.get('event')=='timer' and e.get('timestamp') is not None),
                        key=lambda e:e['timestamp']):
        time=(pd.Timestamp(event['timestamp'])-origin).total_seconds()
        kind=str(event.get('event_type',''))
        if kind.startswith('stop') and stopped is None:
            stopped=time
        elif kind=='start' and stopped is not None:
            if time>stopped: result.append((stopped,time))
            stopped=None
    return result


def context(frame,left,right):
    # Only observations outside the hidden interval enter these descriptors.
    p=frame.power_w.to_numpy(); t=frame.elapsed_seconds.to_numpy()
    a=frame.iloc[left]; b=frame.iloc[right]
    same=bool(a.lap_index>0 and a.lap_index==b.lap_index and
              a.prescription_kind==b.prescription_kind=='power')
    available=left>=4 and right+4<len(frame)
    stable=False; span=None
    if available:
        flank=np.r_[p[left-4:left+1],p[right:right+5]]
        available=bool(np.isfinite(flank).all() and (flank>=0).all() and
                       (np.diff(t[left-4:left+1])==1).all() and
                       (np.diff(t[right:right+5])==1).all())
        if available:
            span=float(np.ptp(flank)); stable=span<=20
    return dict(same_numeric_lap=same,zero_endpoints=bool(p[left]==p[right]==0),
                flank_available=available,flank_range_w=span,stable_flanks_20w=stable)


def errors(truth,left,right):
    n=len(truth); linear=np.linspace(left,right,n+2)[1:-1]
    hold=np.full(n,left)
    variation=float(np.abs(np.diff(np.r_[left,truth,right])).sum())
    return dict(linear_mae_w=float(np.abs(linear-truth).mean()),
                hold_mae_w=float(np.abs(hold-truth).mean()),
                linear_mse_w=float(np.square(linear-truth).mean()),
                linear_bias_w=float((linear-truth).mean()),
                linear_max_error_w=float(np.abs(linear-truth).max()),
                observed_variation_w=variation,reconstructed_variation_w=float(abs(right-left)),
                hidden_peak_loss_w=float(max(truth)-max(np.r_[left,linear,right])),
                hidden_mean_w=float(np.mean(truth)))


def aggregate(group):
    # Equal session weight avoids treating overlapping durations as independent.
    per=group.groupby('workout_id').agg(mae=('linear_mae_w','mean'),hold=('hold_mae_w','mean'),
        mse=('linear_mse_w','mean'),bias=('linear_bias_w','mean'))
    rng=np.random.default_rng(SEED)
    values=per.mae.to_numpy()
    boot=rng.choice(values,size=(1000,len(values)),replace=True).mean(axis=1)
    observed=group.observed_variation_w.sum()
    return dict(windows=len(group),workouts=len(per),linear_mae_w=float(per.mae.mean()),
                linear_mae_ci_low_w=float(np.quantile(boot,.025)),
                linear_mae_ci_high_w=float(np.quantile(boot,.975)),
                hold_mae_w=float(per.hold.mean()),linear_rmse_w=float(np.sqrt(per.mse.mean())),
                linear_bias_w=float(per.bias.mean()),window_mae_p90_w=float(group.linear_mae_w.quantile(.9)),
                windows_mae_over_20w_fraction=float((group.linear_mae_w>20).mean()),
                variation_retained_fraction=float(group.reconstructed_variation_w.sum()/observed) if observed else None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'data/processed/prescribed_workouts_final')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/power_gap_interpolation_benchmark')
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Output must be new')
    manifest=json.loads((args.input/'manifest.json').read_text())
    for name,digest in manifest['output_sha256'].items():
        assert sha(args.input/name)==digest,name
    workouts=sorted([json.loads(s) for s in (args.input/'workouts.jsonl').read_text().splitlines()],
                    key=lambda w:w['steps'][0]['start_timestamp'])
    frames={}; real=[]; event_rows=[]
    for index,w in enumerate(workouts):
        wid=w['workout_id']; frame=pd.read_csv(args.input/w['sample_file']); frames[wid]=frame
        assert sha(w['source_file'])==w['source_sha256']
        activity=read_fit_activity(Path(w['source_file']))
        if activity.parse_error: raise ValueError(activity.parse_error)
        origin=pd.Timestamp(frame.timestamp.iloc[0])-pd.Timedelta(seconds=frame.elapsed_seconds.iloc[0])
        stopped=pauses(activity.messages.get('event',[]),origin)
        event_rows.extend(dict(workout_id=wid,start_elapsed_s=a,end_elapsed_s=b) for a,b in stopped)
        for gap in power_gaps(frame):
            row=dict(workout_id=wid,**gap)
            if gap['bounded']:
                left=gap['left_index'];right=gap['right_index']
                a=frame.elapsed_seconds.iloc[left];b=frame.elapsed_seconds.iloc[right]
                # Interior missing 1 Hz sample instants, not the bounding observations.
                missing_times=np.arange(a+1,b,1)
                paused=np.zeros(len(missing_times),dtype=bool)
                for lo,hi in stopped: paused|=(missing_times>=lo)&(missing_times<hi)
                row.update(context(frame,left,right),timer_paused_seconds=int(paused.sum()),
                           timer_pause_fraction=float(paused.mean()) if len(paused) else 0)
            real.append(row)
        print(f'FIT events {index+1}/{len(workouts)} {wid}',flush=True)
    durations=sorted(set(GRID)|{int(r['missing_duration_s']) for r in real
                              if r['bounded'] and 0<r['missing_duration_s']<=120})
    records=[]
    for wi,w in enumerate(workouts):
        wid=w['workout_id'];frame=frames[wid];p=frame.power_w.to_numpy();t=frame.elapsed_seconds.to_numpy()
        bad=(~np.isfinite(p))|(p<0)
        prefix=np.r_[0,np.cumsum(bad)]
        breaks=np.r_[0,np.cumsum(np.diff(t)!=1)]
        rng=np.random.default_rng(SEED+wi)
        for duration in durations:
            starts=np.arange(4,len(p)-duration-5)
            ends=starts+duration+1
            good=(prefix[ends+5]-prefix[starts-4]==0)&(breaks[ends+4]-breaks[starts-4]==0)
            candidates=starts[good]; rng.shuffle(candidates)
            occupied=np.zeros(len(p),dtype=bool);count=0
            for left in candidates:
                right=left+duration+1
                if occupied[left:right+1].any(): continue
                occupied[left:right+1]=True
                records.append(dict(workout_id=wid,split='development' if wi<40 else 'holdout',
                    missing_seconds=duration,left_index=int(left),right_index=int(right),
                    **context(frame,left,right),**errors(p[left+1:right],p[left],p[right])))
                count+=1
                if count>=(80 if duration in GRID else 25): break
        print(f'Masking {wi+1}/{len(workouts)} {wid}',flush=True)
    data=pd.DataFrame(records); actual=pd.DataFrame(real)
    summaries=[]
    for split in ['all','development','holdout']:
        part=data if split=='all' else data[data.split==split]
        for name,selected in [('all',part),('same_numeric_lap',part[part.same_numeric_lap]),
                              ('stable_same_numeric',part[part.same_numeric_lap&part.stable_flanks_20w]),
                              ('zero_endpoints',part[part.zero_endpoints]),
                              ('other_lap_or_maximal',part[~part.same_numeric_lap])]:
            for duration,group in selected[selected.missing_seconds.isin(GRID)].groupby('missing_seconds'):
                summaries.append(dict(split=split,context=name,missing_seconds=int(duration),**aggregate(group)))
    # Match each true gap to exact duration + endpoint/lap context, never hidden values.
    matches=[]
    for index,gap in actual[actual.bounded & (actual.missing_duration_s<=120)].iterrows():
        selected=data[(data.missing_seconds==gap.missing_duration_s)&
                      (data.same_numeric_lap==gap.same_numeric_lap)&
                      (data.zero_endpoints==gap.zero_endpoints)&
                      (data.stable_flanks_20w==gap.stable_flanks_20w)]
        matches.append(dict(gap_row=int(index),workout_id=gap.workout_id,
            missing_seconds=gap.missing_duration_s,timer_pause_fraction=gap.timer_pause_fraction,
            matching_windows=len(selected),matching_workouts=selected.workout_id.nunique(),
            mean_window_mae_w=float(selected.linear_mae_w.mean()) if len(selected) else None,
            p90_window_mae_w=float(selected.linear_mae_w.quantile(.9)) if len(selected) else None))
    args.output.mkdir(parents=True)
    data.to_csv(args.output/'masked_windows.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    actual.to_csv(args.output/'real_gaps_with_timer.csv',index=False)
    pd.DataFrame(event_rows).to_csv(args.output/'timer_pauses.csv',index=False)
    pd.DataFrame(summaries).to_csv(args.output/'error_summary.csv',index=False)
    pd.DataFrame(matches).to_csv(args.output/'matched_real_gaps.csv',index=False)
    metadata=dict(seed=SEED,grid_seconds=GRID,all_durations_seconds=durations,
        split='first 40 sessions chronologically: development; last 20: holdout',
        synthetic_windows=len(data),workouts=len(workouts),
        sampling='nonoverlapping endpoint-inclusive windows within each workout/duration; 80 grid, 25 other duration maximum',
        stability='range of 5 observed samples on each flank combined <=20 W; excludes hidden samples',
        confidence_intervals='1000 session bootstrap resamples of session mean MAE',
        limitations='Missing-not-at-random not identifiable: observed stretches may differ from actual gaps. Matched errors are analogues, not errors measured inside true gaps.',
        input_manifest_sha256=sha(args.input/'manifest.json'),code_sha256=sha(__file__),
        dependency_sha256={name:sha(ROOT/name) for name in ['src/power_hr_eda/fit_reader.py','src/power_hr_eda/prescription_gaps.py']},
        output_sha256={p.name:sha(p) for p in args.output.iterdir()})
    (args.output/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':
    main()
