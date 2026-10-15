"""Rebuild the selected 60 FITs and annotate observed segments without interpolation."""
import argparse
import gzip
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from power_hr_eda.fit_reader import read_fit_activity
from power_hr_eda.prescription_cli import export_dataset,sha256
from power_hr_eda.prescription_gaps import power_gaps
from power_hr_eda.prescription_segments import annotate_segments,segment_tables,timer_intervals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/prescribed_workouts_final')
    parser.add_argument('--input',type=Path,default=ROOT/'.worktrees/dataset-exploration-webapp/dataset/cleaned/only_road_activities')
    args=parser.parse_args()
    selection=ROOT/'references/prescribed_workouts_selection.json'
    rules=json.loads((ROOT/'references/prescription_rules_v3.json').read_text())
    events={}
    def reader(path):
        activity=read_fit_activity(path)
        events[Path(path).resolve()]=activity.messages.get('event',[])
        return activity
    manifest=export_dataset(args.input,args.output,rules,reader=reader,selection_manifest=selection)
    output=args.output.resolve()
    workouts=[json.loads(s) for s in (output/'workouts.jsonl').read_text().splitlines()]
    expected={a['workout_id']:a for a in json.loads(selection.read_text())['activities']}
    if set(expected)!={w['workout_id'] for w in workouts}:raise ValueError('Selection mismatch')
    all_segments=[];all_fragments=[];all_gaps=[];all_pauses=[]
    valid_power=valid_dynamics=0
    for w in workouts:
        if w['source_sha256']!=expected[w['workout_id']]['source_sha256']:raise ValueError('Source FIT changed')
        path=output/w['sample_file'];frame=pd.read_csv(path)
        origin=pd.Timestamp(frame.timestamp.iloc[0])-pd.Timedelta(seconds=frame.elapsed_seconds.iloc[0])
        pauses=timer_intervals(events[Path(w['source_file']).resolve()],origin)
        annotated=annotate_segments(frame,pauses)
        pd.testing.assert_frame_equal(annotated[frame.columns],frame)
        segments,fragments=segment_tables(w['workout_id'],annotated)
        all_segments.extend(segments);all_fragments.extend(fragments)
        all_pauses.extend(dict(workout_id=w['workout_id'],start_elapsed_s=start,end_elapsed_s=end) for start,end in pauses)
        for gap in power_gaps(frame):
            overlap=False
            if gap['bounded']:
                start=frame.elapsed_seconds.iloc[gap['left_index']];end=frame.elapsed_seconds.iloc[gap['right_index']]
                overlap=any(lo<end and hi>start for lo,hi in pauses)
            all_gaps.append(dict(workout_id=w['workout_id'],overlaps_timer_pause=overlap,**gap))
        valid_power+=int(annotated.power_target_valid.sum());valid_dynamics+=int(annotated.dynamics_target_valid.sum())
        path.write_bytes(gzip.compress(annotated.to_csv(index=False,lineterminator='\n').encode(),mtime=0))
        w['segment_counts']={signal:sum(s['signal']==signal for s in segments) for signal in ['power','hr','dynamics']}
    for name,rows in [('segments',all_segments),('lap_fragments',all_fragments),('power_gaps',all_gaps),('timer_pauses',all_pauses)]:
        pd.DataFrame(rows).to_csv(output/(name+'.csv'),index=False)
    (output/'workouts.jsonl').write_text(''.join(json.dumps(w,ensure_ascii=False,allow_nan=False)+'\n' for w in workouts),encoding='utf-8')
    manifest['format_version']=2
    manifest['summary'].update(valid_power_prescription_samples=valid_power,valid_power_hr_prescription_samples=valid_dynamics,
        segment_counts={signal:sum(s['signal']==signal for s in all_segments) for signal in ['power','hr','dynamics']})
    manifest['segmentation']=dict(expected_step_s=1,no_minimum_segment_length=True,interpolation=False,
        invalid_segment_id=0,ids_scoped_to='workout and signal',
        boundaries='missing/invalid signal, timestamp step !=1 s, recorded timer stop/restart',
        power_valid='finite and >=0',hr_valid='finite and >0',dynamics_valid='power and HR valid',
        raw_samples_preserved=True,lap_fragments_preserve_original_timing=True)
    for path in [Path(__file__),ROOT/'src/power_hr_eda/prescription_segments.py',ROOT/'src/power_hr_eda/prescription_gaps.py']:
        manifest['code_sha256'][str(path.relative_to(ROOT))]=sha256(path)
    with (output/'report.md').open('a',encoding='utf-8') as f:
        f.write('\n## Dataset definitivo segmentato\n\nTutti i campioni originali conservati. Nessuna interpolazione, nessun filtro o taglio per durata minima.\n\n')
        f.write(json.dumps(manifest['summary']['segment_counts'])+'\n\n')
        f.write('Gli ID di segmento sono locali al workout e al segnale; 0 indica dato non osservato/valido. '
                'power_target_valid indica potenza misurata valida con prescrizione; dynamics_target_valid richiede anche HR valida. '
                'Queste maschere non sono garanzie di assenza di artefatti. '
                'I frammenti mantengono il lap originale: non diventano nuove ripetute. '
                'Le pause non sono potenza zero imputata. Split futuri per sessione/tempo.\n')
    manifest['output_sha256']={p.relative_to(output).as_posix():sha256(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(manifest['summary'],indent=2))


if __name__=='__main__':main()
