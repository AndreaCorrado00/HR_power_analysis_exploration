"""Create/verify an immutable experiment snapshot; prune only verified members."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MODULE=ROOT/'power_response_estimation'
ZIP=HERE/'variance_experiments.zip'
MANIFEST=HERE/'variance_experiments_manifest.json'
ACTIVE={'__init__.py','__main__.py','ar.py','cli.py','data.py','dynamics.py','model.py',
        'index.html','app.js','echarts.min.js','LICENSE-echarts','model.json','results.js',
        'metrics.csv','predictions.csv','report.md','README.md','legacy.zip'}
EXPERIMENT_TESTS=['test_power_response_garch.py','test_power_response_diagnostics.py',
    'test_variance_comparison.py','test_scaled_ar.py','test_lap_random_ar.py',
    'garch_browser_check.py','variance_browser_check.py','lap_ar_browser_check.py']


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if digest(ZIP)!=manifest['archive_sha256']:raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:raise ValueError('Archive CRC failed')
        for entry in manifest['files']:
            if hashlib.sha256(archive.read(entry['path'])).hexdigest()!=entry['sha256']:
                raise ValueError('Member mismatch: '+entry['path'])
    return manifest


def create():
    if ZIP.exists() or MANIFEST.exists():raise FileExistsError('Snapshot already exists; verify instead')
    paths=[p for p in MODULE.iterdir() if p.is_file() and p.name!='legacy.zip']
    paths+=list((MODULE/'diagnostics').rglob('*')) if (MODULE/'diagnostics').exists() else []
    paths=[p for p in paths if p.is_file()]
    paths+=[ROOT/'tests'/name for name in EXPERIMENT_TESTS+['test_power_response_estimation.py','test_power_response_estimation_core.py']]
    paths+=[ROOT/'requirements.txt',ROOT/'AGENTS.md']
    entries=[]
    for p in sorted(set(paths)):
        if not p.is_file():continue
        relative=p.relative_to(ROOT).as_posix()
        remove=(p.parent==MODULE and p.name not in ACTIVE) or (MODULE/'diagnostics') in p.parents or (p.parent==ROOT/'tests' and p.name in EXPERIMENT_TESTS)
        entries.append(dict(path=relative,sha256=digest(p),bytes=p.stat().st_size,remove_from_active=remove))
    manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        created_utc=datetime.now(timezone.utc).isoformat(),files=entries,
        protected={f:digest(MODULE/f) for f in ['model.json','results.js','predictions.csv','metrics.csv','report.md','legacy.zip']})
    temporary=ZIP.with_suffix('.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for entry in entries:archive.write(ROOT/entry['path'],entry['path'])
        archive.writestr('EXPERIMENT_SNAPSHOT.json',json.dumps(manifest,indent=2))
    temporary.replace(ZIP);manifest['archive_sha256']=digest(ZIP)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    verify()
    print(f'Verified {len(entries)} members; {sum(e["remove_from_active"] for e in entries)} archived-only files; {ZIP.stat().st_size} archive bytes')


def prune():
    manifest=verify();targets=[]
    for entry in manifest['files']:
        if not entry['remove_from_active']:continue
        p=(ROOT/entry['path']).resolve()
        if not (p.is_relative_to(MODULE.resolve()) or p.parent==(ROOT/'tests').resolve()):
            raise ValueError('Path outside authorized workspace components')
        if p.exists():
            if not p.is_file() or digest(p)!=entry['sha256']:raise ValueError('Source changed after archive: '+str(p))
            targets.append(p)
    # All paths and contents checked before any removal. No recursive deletion.
    for p in targets:p.unlink()
    diagnostic=MODULE/'diagnostics'
    if diagnostic.exists():
        for directory in sorted([p for p in diagnostic.rglob('*') if p.is_dir()],key=lambda p:len(p.parts),reverse=True):
            if not any(directory.iterdir()):directory.rmdir()
        if not any(diagnostic.iterdir()):diagnostic.rmdir()
    for name,expected in manifest['protected'].items():
        if digest(MODULE/name)!=expected:raise ValueError('Frozen artifact changed: '+name)
    print(f'Removed {len(targets)} verified archive members from active paths; frozen artifacts unchanged')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['create','verify','prune']);args=parser.parse_args()
    if args.action=='create':create()
    elif args.action=='prune':prune()
    else:print(f'Archive verified: {len(verify()["files"])} members')
