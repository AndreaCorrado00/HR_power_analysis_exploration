"""Fit and test a single saved power decomposition, in one output folder."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil

import numpy as np
import pandas as pd
import scipy

from .ar import fit_ar
from .data import inventory, chronological_split, load_segments, verify_inputs, sha256
from .dynamics import fit_response
from .model import DecompositionModel, all_metrics, compose, error_metrics, select_order

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREFIX = 'window.POWER_RESPONSE_RESULTS = '
ASSETS = ['index.html','app.js','garch.html','garch_app.js','echarts.min.js','LICENSE-echarts']


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def encode(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()


def atomic_text(path, text):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(text,encoding='utf-8')
    os.replace(temporary,path)


def resolved_records(bundle):
    return [{**r,'path':str(ROOT/r['path'])} for r in bundle['records']]


def validate_split(split, ids):
    if set(split) != {'train','validation','test'} or any(not values for values in split.values()):
        raise ValueError('Need nonempty train, validation and test')
    flat = sum(split.values(),[])
    if len(set(flat)) != len(flat):
        raise ValueError('Split overlap')
    if set(flat) != set(ids):
        raise ValueError('Split does not match dataset')


def get_segments(bundle, split):
    records = resolved_records(bundle)
    parts, coverage = load_segments(records,bundle['split'][split],split_at_prescription=False)
    if set(s.workout_id for s in parts) != set(bundle['split'][split]):
        raise ValueError(f'Workout without valid samples in {split}')
    return parts,coverage.to_dict(orient='records')


def read_results(output):
    text = (Path(output)/'results.js').read_text(encoding='utf-8')
    if not text.startswith(PREFIX) or not text.endswith(';\n'):
        raise ValueError('Invalid results.js')
    return json.loads(text[len(PREFIX):-2])


def pack(table, coverage):
    fields = dict(t='time_s',segment='segment_id',target='target_w',real='real_w',u='input_w',
                  r='response_w',arSample='ar_sample_w',low='ar_low_w',high='ar_high_w',innovation='innovation_w')
    workouts = {}
    for wid, part in table.groupby('workout_id',sort=False):
        data = {key:part[col].astype(object).where(part[col].notna(),None).tolist() for key,col in fields.items()}
        data['arMean'] = float(part.ar_mean_w.iloc[0])
        workouts[str(wid)] = data
    return dict(workouts=workouts,metrics=all_metrics(table),coverage=coverage)


def report(bundle, results):
    n = bundle['selected_order']
    lines = ['# Power response estimation', '',
        f'Modello condiviso: risposta dinamica di ordine **{n}** + AR(2). LS predefinito, Huber opzionale. Target ricostruiti: risultati condizionati al dataset.', '',
        '## Selezione sul validation', '', '| Ordine | RMSE medio W | Delta dal migliore W |', '| --- | ---: | ---: |']
    for row in bundle['selection']['comparisons']:
        lines.append(f"| {row['order']} | {row['mean_rmse_w']:.3f} | {row['delta_from_best_w']:.3f} |")
    lines += ['', 'La selezione usa target + r + media accessoria del fit. Nelle ablazioni la media del residuo appartiene invece all’AR: disattivarlo rimuove anche quella media. Non avviene alcun rifit.', '',
        '## Valutazione delle quattro combinazioni', '',
        'RMSE medio per workout della **previsione media**, senza feedback osservato. Gli errori della prima traiettoria casuale sono separati in `metrics.csv` e nella pagina.', '',
        '| Split | Dinamica | AR | RMSE medio W | MAE medio W | Bias medio W |', '| --- | --- | --- | ---: | ---: | ---: |']
    for split, result in results['splits'].items():
        frame = pd.DataFrame(result['metrics'])
        for (dynamic,ar), group in frame[frame['mode']=='mean'].groupby(['dynamic','ar']):
            lines.append(f'| {split} | {dynamic} | {ar} | {group.rmse_w.mean():.3f} | {group.mae_w.mean():.3f} | {group.bias_w.mean():.3f} |')
    stat = bundle['candidates'][str(n)]['statistics']
    lines += ['', '## Interpretazione e controlli', '',
        f"Parametri: rango Jacobiano {stat['jacobian_rank']}/{stat['parameter_count']}; raggio spettrale {stat['spectral_radius']:.6f}. Stime, IC locali per cluster workout, poli/zeri e tentativi multistart sono in `model.json` e nella pagina.",
        'Confrontare transitori e plateau: un buon RMSE non rende il residuo automaticamente indipendente dal target. Gli intervalli sono locali, non prova di ripetibilità fisiologica.',
        'Nel modo simulazione il residuo visualizzato è reale − traiettoria simulata: non coincide con l’innovazione AR. Le innovazioni osservate sono salvate nei dati della pagina come diagnostica separata.',
        'Il vecchio test è già stato esaminato: il confronto è descrittivo. Coefficienti sempre stimati sul training, senza refit su train+validation.', '',
        '## Uso della pagina', '',
        'Aprire `index.html`. Rotella per zoom, trascinamento per scorrere, barra inferiore per selezionare/spostare l’intervallo. I quattro pannelli condividono il tempo. Interruttori dinamica/AR e modalità media/simulazione aggiornano curve, residui, RMSE, MAE e bias. Scegliere metriche dell’intero workout o della finestra visibile.',
        'La stessa realizzazione AR rimane fissa cambiando contributi e zoom. Nessuna linea attraversa gap reali. Le bande P10–P90 sono puntuali, senza incertezza parametrica; nessun clipping della potenza negativa.', '',
        'Codice, modello, pagina, risultati e questo report stanno nella stessa cartella. Comandi e convenzioni in `README.md`.']
    return '\n'.join(lines)+'\n'


def prediction_table(results):
    """Export the exact viewer samples, with explicit mean/simulation errors."""
    fields = dict(time_s='t', segment_id='segment', target_w='target', real_w='real',
                  input_w='u', response_w='r', ar_sample_w='arSample',
                  ar_low_w='low', ar_high_w='high', innovation_w='innovation')
    frames = []
    for split, result in results['splits'].items():
        for wid, data in result['workouts'].items():
            frame = pd.DataFrame({col:data[key] for col,key in fields.items()})
            frame.insert(0,'workout_id',wid)
            frame.insert(0,'split',split)
            frame['ar_mean_w'] = data['arMean']
            frame['final_residual_w'] = frame.real_w-frame.target_w-frame.response_w
            for mode in ('mean','simulation'):
                frame['predicted_'+mode+'_w'], frame['residual_'+mode+'_w'] = compose(frame,mode=mode)
            frames.append(frame)
    return pd.concat(frames,ignore_index=True)


def publish(output, bundle, results, *, write_model=False):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    for asset in ASSETS:
        if (HERE/asset).resolve() != (output/asset).resolve():
            shutil.copyfile(HERE/asset,output/asset)
    results['model_hash'] = digest(bundle)
    results['model'] = dict(selected_order=bundle['selected_order'],decomposition=bundle['decomposition'],
        selection=bundle['selection'],statistics=bundle['candidates'][str(bundle['selected_order'])]['statistics'],
        training_workouts=len(bundle['split']['train']),loss=bundle['config']['loss'])
    if write_model:
        atomic_text(output/'model.json',encode(bundle)+'\n')
    atomic_text(output/'results.js',PREFIX+encode(results).replace('<','\\u003c')+';\n')
    frames = [pd.DataFrame(v['metrics']).assign(split=k) for k,v in results['splits'].items()]
    atomic_text(output/'metrics.csv',pd.concat(frames,ignore_index=True).to_csv(index=False))
    atomic_text(output/'predictions.csv',prediction_table(results).to_csv(index=False))
    atomic_text(output/'report.md',report(bundle,results))


def fit(args):
    output = args.output
    if (output/'model.json').exists() and not args.overwrite:
        raise FileExistsError('Model already exists; use --overwrite to explicitly replace the fit and invalidate old evaluations')
    orders = sorted(set(args.orders))
    if any(n not in (2,3,4) for n in orders) or not orders or args.paths<1 or args.seed<0:
        raise ValueError('Invalid orders, paths or seed')
    records = inventory(args.input)
    split = read_json(args.split_file) if args.split_file else chronological_split(records,args.train_count,args.validation_count)
    validate_split(split,[r['workout_id'] for r in records])
    portable = []
    for record in records:
        path = Path(record['path'])
        portable.append({**record,'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)})
    bundle = dict(format_version=1,records=portable,split=split,
        config=dict(loss=args.loss,starts=args.starts,max_nfev=args.max_nfev,seed=args.seed,paths=args.paths,
            dynamics_weighting='equal workout',ar_weighting='equal sample',initialization='zero at real boundaries'),
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__),
        code_hashes={p.name:sha256(p) for p in HERE.glob('*.py')},candidates={},test_status='previously examined; descriptive only')
    train,_ = get_segments(bundle,'train'); validation,coverage = get_segments(bundle,'validation')
    verify_inputs(records)
    y = np.concatenate([s.residual for s in train])
    scale = max(1.,float(np.median(np.abs(y-np.median(y)))*1.4826))
    bundle['config']['scale_w']=scale
    selection_rows=[]
    for n in orders:
        print(f'Fit n={n}: {len(y)} samples, {len(split["train"])} workouts',flush=True)
        dynamics,stats = fit_response(train,n,loss=args.loss,scale=scale,starts=args.starts,max_nfev=args.max_nfev,seed=args.seed)
        bundle['candidates'][str(n)] = dict(model=dynamics.to_dict(),statistics=stats)
        if stats['converged']:
            for wid in split['validation']:
                errors = np.concatenate([s.residual-dynamics.response(s.target)-dynamics.mean
                                          for s in validation if s.workout_id==wid])
                selection_rows.append(dict(order=n,workout_id=wid,rmse=error_metrics(errors)['rmse_w']))
    if not selection_rows:
        raise RuntimeError('No converged candidate; no saved model replaced')
    n,selection = select_order(selection_rows,args.seed)
    from .dynamics import ResponseModel
    dynamics = ResponseModel.from_dict(bundle['candidates'][str(n)]['model'])
    from .data import Segment
    residuals = [Segment(s.workout_id,s.segment_id,s.time,s.residual-dynamics.response(s.target),s.target) for s in train]
    ar = fit_ar(residuals,2,hold_back=2)
    model = DecompositionModel(dynamics,ar,args.seed,args.paths)
    table = model.decompose(validation)  # Includes stable AR validation before publishing.
    bundle.update(selected_order=n,selection=selection,decomposition=model.to_dict())
    result = dict(splits={'validation':pack(table,coverage)})
    verify_inputs(records)
    publish(output,bundle,result,write_model=True)
    print(f'Selected n={n}; AR(2); {output / "index.html"}',flush=True)


def test(args):
    bundle = read_json(args.output/'model.json')
    model = DecompositionModel.from_dict(bundle['decomposition'])
    records=resolved_records(bundle); verify_inputs(records)
    if (args.output/'results.js').exists():
        results = read_results(args.output)
        if results['model_hash'] != digest(bundle):
            raise ValueError('Evaluation/model mismatch; regenerate from the matching frozen model')
    else:
        results = dict(splits={})
    for split in (['validation','test'] if args.split=='both' else [args.split]):
        parts,coverage = get_segments(bundle,split)
        results['splits'][split] = pack(model.decompose(parts),coverage)
    verify_inputs(records)
    publish(args.output,bundle,results)
    print(f'Evaluated {args.split}; model unchanged; {args.output / "index.html"}',flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('fit',help='Fit dynamics, select order on validation, then fit AR(2)')
    p.add_argument('--input',type=Path,default=ROOT/'data/processed/prescribed_workouts_final')
    p.add_argument('--output',type=Path,default=HERE)
    p.add_argument('--split-file',type=Path)
    p.add_argument('--train-count',type=int,default=36)
    p.add_argument('--validation-count',type=int,default=12)
    p.add_argument('--orders',type=int,nargs='+',default=[2,3,4])
    p.add_argument('--loss',choices=['linear','huber'],default='linear')
    p.add_argument('--starts',type=int,default=6)
    p.add_argument('--max-nfev',type=int,default=250)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--paths',type=int,default=100)
    p.add_argument('--overwrite',action='store_true')
    p=subs.add_parser('test',help='Frozen free prediction on validation, test or both')
    p.add_argument('--output',type=Path,default=HERE)
    p.add_argument('--split',choices=['validation','test','both'],default='test')
    p=subs.add_parser('fit-garch',help='Fit GARCH(1,1) variance on frozen training innovations; evaluate validation/test')
    p.add_argument('--output',type=Path,default=HERE)
    p.add_argument('--overwrite',action='store_true')
    p=subs.add_parser('test-garch',help='Evaluate frozen GARCH without refitting the mean or variance')
    p.add_argument('--output',type=Path,default=HERE)
    p.add_argument('--split',choices=['validation','test','both'],default='both')
    args=parser.parse_args(argv)
    if args.command in ('fit-garch','test-garch'):
        from .garch_run import run
        run(args)
        return 0
    (fit if args.command=='fit' else test)(args)
    return 0
