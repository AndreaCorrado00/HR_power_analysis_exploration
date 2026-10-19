"""CLI: prepare, hr, evaluate. Each stage persists reproducible artifacts."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import platform
import numpy as np
import scipy
from .data import HERE, OUTPUT, prepare, load_parts, save
from webapp.model_identification_app.backend.models import p1d
from webapp.model_identification_app.backend import population


def configuration():
    c = p1d.default_config(new_run=True)
    c['equilibrium_bounds'] = [60., 200.]
    return c


def fit_part(part, config):
    try:
        result = p1d.fit(part['time'], part['power'], part['hr'], config)
        result.pop('series', None)
        result['status'] = 'fitted' if result['identification_valid'] else 'failed'
    except (ValueError, np.linalg.LinAlgError) as exc:
        result = dict(status='failed', error=str(exc))
    return dict(result, segment_id=part['id'], activity_id=part['workout_id'])


def fit_hr(output=OUTPUT, workers=3):
    manifest = prepare(output)
    parts = load_parts(manifest, 'train')
    config = configuration()
    # Resumption requires identical source/config/model code, never old experiments.
    from power_response_estimation.data import sha256
    sources = [HERE/'run.py', HERE/'data.py'] + list((HERE.parents[1]/'webapp/model_identification_app/backend/models').glob('*.py'))
    signature = hashlib.sha256(json.dumps(dict(manifest=manifest,config=config,
        code={str(p.relative_to(HERE.parents[1])):sha256(p) for p in sources}),sort_keys=True).encode()).hexdigest()
    fits = output/'hr_fits'
    fits.mkdir(parents=True, exist_ok=True)
    pending = []
    results = []
    for part in parts:
        path = fits/(part['id']+'.json')
        if path.exists():
            result = json.loads(path.read_text(encoding='utf-8'))
            if result['signature'] != signature:
                raise ValueError('Cached HR fit has different inputs/config/code')
            results.append(result)
        else:
            pending.append(part)
    print(f'HR: {len(parts)} train segments; {len(results)} cached; {workers} workers',flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(fit_part,p,config):p for p in pending}
        for future in as_completed(jobs):
            result = future.result()
            result['signature'] = signature
            save(fits/(result['segment_id']+'.json'),result)
            results.append(result)
            print(f"HR {len(results)}/{len(parts)} {result['segment_id']} {result['status']}",flush=True)
    order = {p['id']:i for i,p in enumerate(parts)}
    results.sort(key=lambda r:order[r['segment_id']])
    hr_manifest = dict(id=manifest['id'], config=config, model=p1d.metadata(config),
        model_structure='p1d_full', dataset=dict(segments=manifest['segments']),
        parameter_bounds=dict(keys=['K','L','tau','B'],lower=config['lower']+[60.],upper=config['upper']+[200.]),
        split=dict(unit='activity',assignments={k:[s['id'] for s in manifest['segments'] if s['split']==k]
                                               for k in manifest['split']}))
    analysis = population.analyze(hr_manifest,results,
        dict(prediction_mode=population.MEAN_HR0_MODE,draws=1000,seed=42),
        train_initial_hr={p['id']:float(p['hr'][0]) for p in parts})
    x = np.concatenate([p['power'] for p in parts]); y = np.concatenate([p['hr'] for p in parts])
    design = np.column_stack([np.ones(len(x)),x])
    beta,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
    if rank != 2: raise ValueError('Static baseline unidentifiable')
    bundle = dict(manifest=hr_manifest, analysis=analysis, static=dict(beta=beta.tolist(),samples=len(y)),
                  signature=signature, versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    save(output/'hr_model.json', bundle)
    print(f"HR population: {analysis['status']}, retained {analysis['retained_vectors']}/{len(parts)}",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','hr','evaluate'])
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--split',choices=['validation','test'],default='validation')
    args=parser.parse_args()
    if args.stage=='prepare':
        m=prepare(); print({k:len(v) for k,v in m['split'].items()})
    elif args.stage=='hr': fit_hr(workers=args.workers)
    else:
        from .evaluate import evaluate
        evaluate(args.split)


if __name__=='__main__': main()
