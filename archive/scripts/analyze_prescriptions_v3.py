"""Compare prescriptions and hypothetical gap policies without modifying data."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from power_hr_eda.prescriptions import classify, recognize_blocks
from power_hr_eda.prescription_gaps import power_gaps, dominant_window


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_dataset(path):
    manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['output_sha256'].items():
        if sha(path/name)!=digest: raise ValueError(f'Hash mismatch: {path/name}')
    return manifest,[json.loads(s) for s in (path/'workouts.jsonl').read_text(encoding='utf-8').splitlines()]


def deviations(laps):
    values=np.array([r['power_target_w']-r['mean_power_w'] for r in laps
                     if r['prescription_kind']=='power'])
    return dict(numeric_laps=len(values),median_absolute_w=float(np.median(abs(values))),
                median_signed_w=float(np.median(values)),over_50w=int((abs(values)>50).sum()),
                maximum_absolute_w=float(max(abs(values))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'data/processed/prescribed_workouts_v3_verified')
    parser.add_argument('--previous',type=Path,default=ROOT/'data/processed/prescribed_workouts_v2')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/prescribed_workouts_v3_analysis')
    args=parser.parse_args()
    current,workouts=checked_dataset(args.input)
    previous,old=checked_dataset(args.previous)
    prior={w['workout_id']:w for w in old}
    assert set(prior)=={w['workout_id'] for w in workouts}
    gaps_all=[]; windows=[]; sample_count=0; missing_count=0; zeros=0; unassigned_samples=0
    valid_count=0; timestamp_gaps=0; sensitivity={}
    measured=['record_index','timestamp','elapsed_seconds','lap_index','power_w','heart_rate_bpm',
              'cadence_rpm','speed_m_s','altitude_m','temperature_c']
    for workout in workouts:
        wid=workout['workout_id']
        assert workout['source_sha256']==prior[wid]['source_sha256']
        frame=pd.read_csv(args.input/workout['sample_file'])
        oldframe=pd.read_csv(args.previous/prior[wid]['sample_file'])
        pd.testing.assert_frame_equal(frame[measured],oldframe[measured])
        sample_count+=len(frame)
        valid=np.isfinite(frame.power_w)&(frame.power_w>=0)
        missing_count+=int((~valid).sum()); zeros+=int((frame.power_w==0).sum())
        valid_count+=int((valid&frame.prescription_kind.isin(['power','maximal'])).sum())
        unassigned_samples+=int((frame.lap_index==0).sum())
        timestamp_gaps+=int((frame.elapsed_seconds.diff()>2).sum())
        gaps=power_gaps(frame)
        for gap in gaps:
            gap['zero_at_both_ends']=bool(gap['bounded'] and
                frame.power_w.iloc[gap['left_index']]==0 and frame.power_w.iloc[gap['right_index']]==0)
        gaps_all.extend(dict(workout_id=wid,**gap) for gap in gaps)
        for threshold in [2,60,120]:
            window=dominant_window(frame,gaps,threshold)
            windows.append(dict(workout_id=wid,split_threshold_s=threshold,**window))
    for tolerance in [.05,.10]:
        rules=deepcopy(current['rules']); rules['patterns']['power_tolerance_fraction']=tolerance
        laps=[]; protocols=Counter()
        for workout in workouts:
            rows=[]
            for step in workout['steps']:
                row={k:step[k] for k in ['lap_index','start_elapsed_s','end_elapsed_s','duration_s','mean_power_w']}
                row.update(classify(row['mean_power_w'],row['duration_s'],rules))
                row.update(block_id=None,family_id=None,phase_index=None,phase_role=None,ideal_duration_s=None)
                rows.append(row)
            blocks=recognize_blocks(rows,rules)
            protocols.update(b['protocol'] for b in blocks)
            for row in rows:
                if row['block_id'] and row['prescription_kind']=='power':
                    assert abs(row['mean_power_w']-row['power_target_w'])<=tolerance*row['power_target_w']+1e-9
            if tolerance==.05:
                assert [(r['power_target_w'],r['block_id']) for r in rows]==[
                    (r['power_target_w'],r['block_id']) for r in workout['steps']]
            laps.extend(rows)
        sensitivity[str(tolerance)]=dict(blocks=sum(protocols.values()),protocols=dict(protocols),
                                       shared_laps=sum(r['block_id'] is not None for r in laps),**deviations(laps))
    bounded=[g for g in gaps_all if g['bounded']]
    buckets={label:sum(lo<g['missing_duration_s']<=hi for g in bounded)
             for label,lo,hi in [('1-5s',0,5),('6-30s',5,30),('31-60s',30,60),
                                ('61-120s',60,120),('over120s',120,float('inf'))]}
    policies={}
    for threshold in [2,60,120]:
        subset=[w for w in windows if w['split_threshold_s']==threshold]
        candidates=[g for g in bounded if g['same_numeric_lap'] and g['missing_duration_s']<threshold]
        policies[str(threshold)]=dict(retained_complete_laps=sum(w['complete_laps'] for w in subset),
            retained_valid_prescribed_samples=sum(w['valid_prescribed_samples'] for w in subset),
            same_numeric_lap_short_gaps=len(candidates),
            candidate_missing_seconds=sum(g['missing_duration_s'] for g in candidates),
            candidate_gaps_zero_at_both_ends=sum(g['zero_at_both_ends'] for g in candidates),
            candidate_endpoint_delta_median_w=float(np.median([g['endpoint_delta_w'] for g in candidates])) if candidates else None,
            candidate_endpoint_delta_max_w=max((g['endpoint_delta_w'] for g in candidates),default=None))
    result=dict(workouts=len(workouts),measured_samples=sample_count,missing_or_invalid_power=missing_count,
        zero_power_samples=zeros,samples_outside_laps=unassigned_samples,valid_prescribed_samples=valid_count,
        measured_columns_identical_to_v2=True,timestamp_gaps_over_2s=timestamp_gaps,
        bounded_power_gaps=len(bounded),unbounded_power_gaps=len(gaps_all)-len(bounded),
        bounded_missing_seconds=sum(g['missing_duration_s'] for g in bounded),gap_buckets=buckets,
        workouts_with_power_gaps=len({g['workout_id'] for g in gaps_all}),
        previous_deviations=deviations([r for w in old for r in w['steps']]),
        tolerance_sensitivity=sensitivity,hypothetical_gap_policies=policies)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    pd.DataFrame(gaps_all).to_csv(args.output/'power_gaps.csv',index=False)
    pd.DataFrame(windows).to_csv(args.output/'candidate_windows.csv',index=False)
    manifest=dict(input_manifest_sha256=sha(args.input/'manifest.json'),
                  previous_manifest_sha256=sha(args.previous/'manifest.json'),
                  code_sha256={str(p.relative_to(ROOT)):sha(p) for p in
                               [Path(__file__),ROOT/'src/power_hr_eda/prescription_gaps.py',
                                ROOT/'src/power_hr_eda/prescriptions.py']},
                  policy='diagnostic only; no cutting, interpolation, or concatenation',
                  expected_sampling_step_s=1,
                  window_score=['complete observed laps','valid prescribed samples','earliest start'],
                  output_sha256={p.name:sha(p) for p in args.output.iterdir()})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
