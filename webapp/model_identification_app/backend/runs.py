"""Persistent experiment lifecycle. Only IDs in the frozen train split are fitted."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.metadata
import platform
from pathlib import Path
import shutil
import uuid

from .datasets import series, SIGNALS, utc_now
from .models import get_model
from .storage import sha, slug


class RunService:
    def __init__(self, store, datasets):
        self.store, self.datasets = store, datasets
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='p1d-fit')
        for manifest in self.store.list('runs'):
            if manifest['status'] in ('running','queued'):
                manifest.update(status='interrupted', finished_at=utc_now(),
                                error='Servizio riavviato prima del completamento; risultati parziali conservati')
                self.save(manifest)

    def save(self, manifest):
        self.store.write_path(self.store.root/'runs'/manifest['manifest_filename'], manifest)

    def get(self, key, archived=False):
        for manifest in self.store.list('archived_manifests' if archived else 'runs'):
            if manifest['id']==key: return manifest
        raise FileNotFoundError('Run non trovata')

    def provenance(self):
        root = Path(__file__).resolve().parents[1]
        files = [*root.glob('backend/**/*.py'), *root.glob('src/**/*.ts'), *root.glob('src/**/*.vue')]
        files += [p for p in [root/'package-lock.json',root/'requirements.txt'] if p.exists()]
        sources = {str(p.relative_to(root)).replace('\\','/'): self.store.blob(p.read_bytes()) for p in sorted(files)}
        return {'python': platform.python_version(), 'platform': platform.platform(),
                'packages': dict(sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions() if d.metadata['Name'])),
                'code_blobs': sources, 'code_sha256': sha(str(sorted(sources.items())).encode())}

    def start(self, dataset_id, model_id, signal, config, original=None):
        model = get_model(model_id)
        config = model.validate_config(config)
        ds = self.datasets.get(dataset_id) if original is None else original['dataset']
        split = ds['split'] if original is None else original['split']
        if not split or not split['assignments']['train']: raise ValueError('Creare prima uno split con train non vuoto')
        if signal not in SIGNALS: raise ValueError('Segnali non validi')
        selected = [s for s in ds['segments'] if s['id'] in split['assignments']['train']]
        if any(signal not in s['signals'] for s in selected): raise ValueError('Colonne selezionate mancanti in almeno un segmento train')
        for segment in selected: self.store.read_blob(segment['sha256'])
        key = uuid.uuid4().hex
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        split_name = '-'.join(f'{v:g}' for v in split['percentages'])
        name = f"{stamp}__{slug(ds['name'])}__{model_id}__{signal}__{split_name}__s{split['seed']}__n{config['n_starts']}-f{config['seed']}__{key[:8]}.json"
        manifest = {'schema_version': 1, 'id': key, 'manifest_filename': name,
                    'created_at': utc_now(), 'status': 'queued', 'dataset': ds, 'split': split,
                    'model': model.METADATA, 'signal': signal, 'columns': list(SIGNALS[signal]),
                    'config': config, 'environment': self.provenance(), 'scope': 'train-only in-sample',
                    'progress': {'done': 0, 'total': len(selected), 'failed': 0},
                    'replay_of': original['id'] if original else None}
        if original:
            manifest['code_changed_since_original'] = original['environment']['code_sha256'] != manifest['environment']['code_sha256']
        with self.store.lock:
            (self.store.root/'runs'/key).mkdir()
            self.save(manifest)  # Must exist on disk before scheduling any fitting.
            self.executor.submit(self.execute, key)
        return manifest

    def execute(self, key):
        manifest = self.get(key)
        try:
            manifest.update(status='running', started_at=utc_now())
            self.save(manifest)
            model = get_model(manifest['model']['id'])
            by_id = {s['id']: s for s in manifest['dataset']['segments']}
            for sid in manifest['split']['assignments']['train']:
                segment = by_id[sid]
                result = {'segment_id': sid, 'filename': segment['filename'], 'status': 'failed'}
                try:
                    data = self.store.read_blob(segment['sha256'])
                    result.update(model.fit(*series(data, manifest['signal']), manifest['config']))
                    result['status'] = 'fitted'
                except (ValueError, ArithmeticError) as exc:
                    result['error'] = str(exc)
                    manifest['progress']['failed'] += 1
                self.store.write_path(self.store.root/'runs'/key/(sid+'.json'), result)
                manifest['progress']['done'] += 1
                self.save(manifest)
            manifest.update(status='completed' if not manifest['progress']['failed'] else 'completed_with_errors', finished_at=utc_now())
        except Exception as exc:
            manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}', finished_at=utc_now())
        self.save(manifest)

    def results(self, key, detail=False):
        self.get(key)
        folder = self.store.root/'runs'/key
        import json
        output = []
        for path in sorted(folder.glob('*.json')):
            result = json.loads(path.read_text(encoding='utf-8'))
            if not detail:
                result.pop('series',None)
                result.pop('starts',None)
            output.append(result)
        return output

    def archive(self, key):
        with self.store.lock:
            manifest = self.get(key)
            if manifest['status'] in ('queued','running'): raise ValueError('Attendere la fine della run prima di eliminarla')
            manifest['archived_at'] = utc_now()
            target = self.store.root/'archived_manifests'/manifest['manifest_filename']
            self.store.write_path(target,manifest)
            folder = (self.store.root/'runs'/key).resolve()
            if folder.parent != (self.store.root/'runs').resolve(): raise ValueError('Percorso run non valido')
            if folder.exists(): shutil.rmtree(folder)
            (self.store.root/'runs'/manifest['manifest_filename']).unlink()
        return {'archived_manifest': target.name}

    def replay(self, key, archived=False):
        original = self.get(key,archived)
        return self.start(original['dataset']['id'], original['model']['id'], original['signal'], original['config'], original)

    def close(self):
        self.executor.shutdown(wait=True)
