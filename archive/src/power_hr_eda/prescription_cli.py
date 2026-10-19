"""Offline batch export, independent of the web application."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd

from .fit_reader import read_fit_activity
from .prescriptions import extract_laps, recognize_blocks, is_assigned


ROOT=Path(__file__).resolve().parents[2]


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def resolve_fit_source(path):
    """Resolve the text references used by the selected dataset, without rewriting them."""
    path=Path(path).resolve()
    with path.open('rb') as stream:
        header=stream.read(1024)
    if header[8:12]==b'.FIT':
        return path
    if path.stat().st_size>1024:
        raise ValueError('Missing FIT signature')
    try:
        text=header.decode('utf-8-sig').strip()
    except UnicodeDecodeError as exc:
        raise ValueError('Neither FIT binary nor UTF-8 file reference') from exc
    if not text or '\n' in text or '\r' in text or not text.lower().endswith('.fit'):
        raise ValueError('Invalid FIT text reference')
    source=Path(text)
    if not source.is_absolute(): source=path.parent/source
    source=source.resolve(strict=True)
    with source.open('rb') as stream:
        if stream.read(12)[8:12]!=b'.FIT':
            raise ValueError('Referenced file is not a FIT binary')
    return source


def _csv(path,rows,empty_columns=()):
    normalized=[{k:json.dumps(v,ensure_ascii=False,allow_nan=False) if isinstance(v,(list,dict)) else v
                 for k,v in row.items()} for row in rows]
    frame=pd.DataFrame(normalized) if rows else pd.DataFrame(columns=empty_columns)
    path.write_text(frame.to_csv(index=False,lineterminator='\n'),encoding='utf-8',newline='')


def _samples(activity,assignment,laps):
    original=activity.records
    times=pd.to_datetime(original.get('timestamp',pd.Series(index=original.index,dtype=object)),utc=True,errors='coerce')
    output=pd.DataFrame({'record_index':range(len(original)),'timestamp':times,
                         'elapsed_seconds':(times-times.min()).dt.total_seconds(),'lap_index':assignment})
    columns={'power_w':('power',),'heart_rate_bpm':('heart_rate',),'cadence_rpm':('cadence',),
             'speed_m_s':('enhanced_speed','speed'),'altitude_m':('enhanced_altitude','altitude'),
             'temperature_c':('temperature',)}
    for target,candidates in columns.items():
        value=pd.Series(float('nan'),index=original.index)
        for candidate in candidates:
            if candidate in original:
                value=value.fillna(pd.to_numeric(original[candidate],errors='coerce'))
        output[target]=value.to_numpy()
    lookup={lap['lap_index']:lap for lap in laps}
    for column in ('power_target_w','prescription_kind','block_id','family_id','phase_index'):
        output[column]=[lookup.get(int(i),{}).get(column) for i in assignment]
    return output


def export_dataset(source,output,rules,reader=read_fit_activity,selection_manifest=None):
    source=Path(source).resolve(strict=True); output=Path(output).resolve()
    if not source.is_dir(): raise ValueError('Input must be a directory')
    if output==source or output.is_relative_to(source):
        raise ValueError('Output must not be inside the input directory')
    if rules.get('ftp_w')!=325: raise ValueError('This mapping is defined for FTP 325 W only')
    if rules.get('z1_policy') not in ('unresolved','rounded_lap_mean'):
        raise ValueError('Unknown Z1 policy')
    if rules.get('z2_open_upper_policy') not in ('unresolved','cap_at_6h'):
        raise ValueError('Unknown Z2 policy')
    if rules.get('above_z6_policy') not in (None,'categorical_maximal'):
        raise ValueError('Unknown above-Z6 policy')
    if rules.get('workout_selection') not in (None,'all_laps_assigned'):
        raise ValueError('Unknown workout selection policy')
    if rules.get('power_model') not in (None,'rounded_observed_mean'):
        raise ValueError('Unknown power model')
    paths=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower()=='.fit')
    if selection_manifest is not None:
        selection_manifest=Path(selection_manifest).resolve(strict=True)
        selected=json.loads(selection_manifest.read_text(encoding='utf-8'))
        selected_ids={e['workout_id'] for e in selected['activities'] if e['status']=='exported'}
        paths=[p for p in paths if p.stem in selected_ids]
        if {p.stem for p in paths}!=selected_ids:
            raise ValueError('Previously selected workouts missing from input')
    if not paths: raise ValueError('No selected FIT files')
    output.mkdir(parents=True,exist_ok=False)
    (output/'samples').mkdir()
    all_laps=[]; activities=[]; workouts=[]; flags=Counter(); protocols=Counter()
    for index,selection in enumerate(paths,1):
        entry=dict(workout_id=selection.stem,selected_file=str(selection),selection_sha256=sha256(selection),
                   source_file=None,source_sha256=None,status=None,reason=None)
        try:
            fit=resolve_fit_source(selection)
            entry.update(source_file=str(fit),source_sha256=sha256(fit))
            activity=reader(fit)
            if activity.parse_error: raise ValueError(activity.parse_error)
        except (OSError,ValueError) as exc:
            entry.update(status='source_error',reason=str(exc)); activities.append(entry)
            continue
        if not activity.messages.get('lap'):
            entry.update(status='excluded_no_laps'); activities.append(entry)
            continue
        laps,assignment=extract_laps(activity,rules)
        for lap in laps:
            lap['workout_id']=selection.stem
            lap['observed_base_zone']=lap['base_zone']
        usable=sum(lap['valid_power_samples']>0 and lap['duration_s'] is not None
                   and lap['duration_s']>0 and 'invalid_lap_boundaries' not in lap['flags'] for lap in laps)
        if not usable:
            entry.update(status='excluded_no_usable_laps',lap_count=len(laps))
            activities.append(entry)
            continue
        blocks=recognize_blocks(laps,rules)
        unassigned=[lap for lap in laps if not is_assigned(lap)]
        if unassigned and rules.get('workout_selection')=='all_laps_assigned':
            entry.update(status='excluded_unassigned_laps',lap_count=len(laps),
                         unassigned_laps=len(unassigned),
                         unassigned_lap_indices=[lap['lap_index'] for lap in unassigned],
                         reason='Workout excluded because at least one lap is unassigned',
                         exclusion_details=[{'lap_index':lap['lap_index'],'flags':lap['flags']} for lap in unassigned])
            activities.append(entry)
            continue
        for lap in laps:
            target=lap['power_target_w']; mean=lap['mean_power_w']
            lap['target_minus_mean_w']=None if target is None or mean is None else round(target-mean,3)
            flags.update(lap['flags'])
        protocols.update(b['protocol'] for b in blocks)
        samples=_samples(activity,assignment,laps)
        sample_file=f'samples/{selection.stem}.csv.gz'
        data=samples.to_csv(index=False,lineterminator='\n').encode('utf-8')
        (output/sample_file).write_bytes(gzip.compress(data,mtime=0))
        assigned=sum(is_assigned(lap) for lap in laps)
        entry.update(status='exported',lap_count=len(laps),usable_laps=usable,assigned_laps=assigned,
                     unassigned_laps=len(laps)-assigned,block_count=len(blocks),sample_count=len(samples),
                     samples_outside_laps=int((assignment==0).sum()),
                     samples_with_target=int(samples.power_target_w.notna().sum()),sample_file=sample_file)
        entry['samples_with_prescription']=int(samples.prescription_kind.isin(['power','maximal']).sum())
        activities.append(entry)
        all_laps.extend(laps)
        workouts.append(dict(workout_id=selection.stem,source_file=str(fit),source_sha256=entry['source_sha256'],
                             sample_file=sample_file,lap_count=len(laps),blocks=blocks,steps=laps))
        print(f'{index}/{len(paths)} {selection.name}: {len(laps)} laps, {len(blocks)} blocks',flush=True)
    statuses=Counter(a['status'] for a in activities)
    summary=dict(input_files=len(paths),exported_workouts=statuses['exported'],
                 excluded_no_laps=statuses['excluded_no_laps'],source_errors=statuses['source_error'],
                 excluded_no_usable_laps=statuses['excluded_no_usable_laps'],
                 excluded_unassigned_laps=statuses['excluded_unassigned_laps'],
                 laps=len(all_laps),assigned_laps=sum(is_assigned(l) for l in all_laps),
                 numeric_target_laps=sum(l['power_target_w'] is not None for l in all_laps),
                 maximal_laps=sum(l['prescription_kind']=='maximal' for l in all_laps),
                 unassigned_laps=sum(not is_assigned(l) for l in all_laps),
                 blocks=sum(protocols.values()),protocol_counts=dict(protocols),lap_flags=dict(sorted(flags.items())),
                 measured_samples=sum(a.get('sample_count',0) for a in activities),
                 samples_with_target=sum(a.get('samples_with_target',0) for a in activities),
                 samples_with_prescription=sum(a.get('samples_with_prescription',0) for a in activities),
                 samples_outside_laps=sum(a.get('samples_outside_laps',0) for a in activities))
    _csv(output/'laps.csv',all_laps,('workout_id','lap_index','power_target_w'))
    _csv(output/'activities.csv',activities)
    (output/'workouts.jsonl').write_text(''.join(json.dumps(w,ensure_ascii=False,allow_nan=False)+'\n' for w in workouts),encoding='utf-8')
    report=['# Prescrizioni inferite dai lap','',
            'Dataset sintetico: non rappresenta piani originali verificati. Nessun training eseguito.','',
            '| Misura | Valore |','|---|---|']
    report.extend(f'| {k} | {v} |' for k,v in summary.items() if not isinstance(v,dict))
    report.extend(['','## Protocolli candidati','']+[f'- {k}: {v}' for k,v in protocols.items()])
    report.extend(['','## Indicatori per lap (non mutuamente esclusivi)','']+[f'- {k}: {v}' for k,v in sorted(flags.items())])
    report.extend(['','## Interpretazione','',
                   '- Media ricalcolata dai campioni del lap; avg_power FIT conservato per confronto.',
                   '- Zero incluso; valori mancanti/non finiti/negativi esclusi solo dalla media e conteggiati.',
                   '- Nessun campione filtrato, interpolato, riscalato o eliminato dal file samples.',
                   '- Estremi lap inclusivi; in caso di sovrapposizione il lap successivo possiede il campione.',
                   '- Fuori dai lap: lap_index=0 e target vuoto. Nessun riempimento dei gap.',
                   '- Durate effettive conservate; durata ideale inferita solo per sequenze ripetute.',
                   ('- Target numerici: media del lap arrotondata a 5 W; mediana delle medie per fasi condivise.'
                    if rules.get('power_model')=='rounded_observed_mean' else
                    f"- Policy Z1: {rules['z1_policy']}; Z2: {rules['z2_open_upper_policy']}."),
                   f"- Modello potenza: {rules.get('power_model','duration_curve')}; tolleranza ripetute: {rules['patterns']['power_tolerance_fraction']}.",
                   '- prescription_kind distingue power (watt), maximal (categorico) e unassigned.',
                   '- Un lap maximal e\' assegnato, anche se power_target_w resta vuoto: nessun watt massimale inventato.',
                   f"- Policy oltre Z6: {rules.get('above_z6_policy','unresolved')}; selezione: {rules.get('workout_selection','usable_laps')}.",
                   '- Massimale oltre 488 W e\' una convenzione del dataset, non prova di sforzo fisiologicamente massimale.',
                   '- Le tolleranze sono euristiche esplicite, non stime di accuratezza o confidenza.',
                   '- Split futuri per sessione/tempo; medie e diagnostica osservate non sono input prescritti.',
                   '- Un piano inferito dalla traccia target non costituisce validazione su prescrizioni prospettiche.',''])
    (output/'report.md').write_text('\n'.join(report),encoding='utf-8')
    config_json=json.dumps(rules,sort_keys=True,separators=(',',':'))
    manifest=dict(format_version=1,dataset_kind='inferred_prescriptions',input_directory=str(source),
                  rules=rules,rules_sha256=hashlib.sha256(config_json.encode()).hexdigest(),summary=summary,
                  units={'power':'W','duration':'s','heart_rate':'bpm','timestamp':'UTC'},
                  preprocessing={'mean':'arithmetic_valid_lap_samples_including_zero',
                                 'mean_duration':'FIT total_timer_time',
                                 'filtering':False,'interpolation':False,'resampling':False,
                                 'lap_boundaries':'inclusive; later lap wins overlap; no gap filling'},
                  code_sha256={str(p.relative_to(ROOT)):sha256(p) for p in
                               [Path(__file__),Path(__file__).with_name('prescriptions.py'),
                                Path(__file__).with_name('fit_reader.py')]},
                  activities=activities,
                  output_sha256={p.relative_to(output).as_posix():sha256(p) for p in sorted(output.rglob('*')) if p.is_file()})
    if selection_manifest is not None:
        manifest.update(selection_manifest=str(selection_manifest),selection_manifest_sha256=sha256(selection_manifest))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'.worktrees/dataset-exploration-webapp/dataset/cleaned/only_road_activities')
    parser.add_argument('--output',type=Path,required=True,help='New output directory; overwrite is never allowed')
    parser.add_argument('--rules',type=Path,default=ROOT/'references/prescription_rules.json')
    parser.add_argument('--selection-manifest',type=Path,help='Pin workouts exported by a previous manifest')
    args=parser.parse_args(argv)
    rules=json.loads(args.rules.read_text(encoding='utf-8'))
    manifest=export_dataset(args.input,args.output,rules,selection_manifest=args.selection_manifest)
    print(json.dumps(manifest['summary'],indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
