"""Import existing CSV records without preprocessing or modifying the originals."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import PurePosixPath
import uuid
import zipfile

import numpy as np

from .storage import sha

MAX_BYTES = 256 * 1024**2
SIGNALS = {'raw': ('power_w','heart_rate_bpm'), 'ma': ('power_ma_w','heart_rate_ma_bpm')}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    columns = reader.fieldnames or []
    if len(set(columns)) != len(columns): raise ValueError('Colonne CSV duplicate')
    if 'elapsed_seconds' not in columns: raise ValueError('Colonna elapsed_seconds mancante')
    rows = list(reader)
    if not rows: raise ValueError('CSV vuoto')
    return columns, rows


def series(data, signal):
    if signal not in SIGNALS: raise ValueError('Segnali sconosciuti')
    columns, rows = read_csv(data)
    p, h = SIGNALS[signal]
    if p not in columns or h not in columns: raise ValueError(f'Colonne {p}/{h} mancanti')
    def number(value):
        try: return float(value)
        except (TypeError, ValueError): return float('nan')
    return tuple(np.array([number(row.get(c)) for row in rows]) for c in ('elapsed_seconds',p,h))


def statistics(segments):
    durations = [s['duration_seconds'] for s in segments]
    return {'count': len(segments), 'duration_mean': float(np.mean(durations)) if durations else None,
            'duration_sd': float(np.std(durations, ddof=1)) if len(durations)>1 else None}


def unpack(files):
    records, manifests, sources = [], [], []
    if sum(len(data) for _,data in files) > MAX_BYTES: raise ValueError('Import oltre 256 MiB')
    for filename, data in files:
        sources.append({'name': filename, 'sha256': sha(data)})
        if filename.lower().endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                names = [x.filename for x in infos]
                if len(names) != len(set(names)): raise ValueError('Voci ZIP duplicate')
                if len(infos)>10000 or sum(x.file_size for x in infos)>512*1024**2:
                    raise ValueError('ZIP oltre i limiti di import')
                for name in names:
                    path = PurePosixPath(name)
                    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                        raise ValueError('Percorso ZIP non sicuro')
                meta = json.loads(z.read('manifest.json')) if 'manifest.json' in names else {}
                manifests.append({'source': filename, 'manifest': meta})
                entries = meta.get('segments', [])
                by_file = {e['csv_file']: e for e in entries}
                if len(by_file) != len(entries): raise ValueError('Segmenti duplicati nel manifest')
                csv_names = [n for n in names if n.lower().endswith('.csv') and not n.startswith('metadata/')]
                if entries and set(by_file) != set(csv_names): raise ValueError('CSV e manifest non corrispondono')
                for name in csv_names: records.append((filename+'::'+name, z.read(name), by_file.get(name,{})))
        elif filename.lower().endswith('.csv'):
            records.append((filename, data, {}))
        elif filename.lower().endswith('.json'):
            manifests.append({'source': filename, 'manifest': json.loads(data)})
        else: raise ValueError('Importare CSV, ZIP o manifest JSON')
    # Optional loose manifest maps basenames or relative CSV names.
    for i, (name, data, meta) in enumerate(records):
        if '::' in name: continue
        matches = [e for m in manifests for e in m['manifest'].get('segments', [])
                   if e.get('csv_file') == name or PurePosixPath(e.get('csv_file','')).name == name]
        if len(matches)>1: raise ValueError('Manifest ambiguo per '+name)
        if matches: records[i] = (name,data,matches[0])
    if not records: raise ValueError('Nessun CSV di segmento trovato')
    if len({r[0] for r in records}) != len(records): raise ValueError('Nomi CSV duplicati')
    return records, manifests, sources


class DatasetService:
    def __init__(self, store): self.store = store

    def get(self, key): return self.store.read('datasets',key)

    def import_files(self, files, name):
        records, manifests, sources = unpack(files)
        segments = []
        for filename, data, meta in records:
            columns, rows = read_csv(data)
            try: t = np.array([float(r['elapsed_seconds']) for r in rows])
            except (ValueError, TypeError): raise ValueError(f'{filename}: tempi non validi')
            if not np.isfinite(t).all() or np.any(np.diff(t)<=0): raise ValueError(f'{filename}: tempi non crescenti/non finiti')
            activities = {r.get('activity_id') for r in rows if r.get('activity_id')}
            if len(activities)>1: raise ValueError('Un CSV deve contenere un solo segmento di una attività')
            activity = next(iter(activities), meta.get('activity_id'))
            if activities and meta.get('activity_id') and activity != meta['activity_id']:
                raise ValueError('activity_id differente tra CSV e manifest')
            pathparts = filename.replace('::','/').split('/')
            group, label = str(meta.get('duration_group','unknown')), meta.get('empirical_label','unknown')
            for part in pathparts:
                for g in ('1','2','3','4'):
                    if part in [f'{l}_G{g}' for l in ('UtD','DtU','Ambigui')]:
                        group, label = g, part.split('_')[0]
            if label == 'Ambiguo': label = 'Ambigui'
            warnings = []
            if not activity: warnings.append('activity_missing')
            start, end = rows[0].get('timestamp'), rows[-1].get('timestamp')
            if start and end:
                try:
                    start = datetime.fromisoformat(start.replace('Z','+00:00')).isoformat()
                    end = datetime.fromisoformat(end.replace('Z','+00:00')).isoformat()
                except ValueError: raise ValueError('Timestamp CSV non valido')
            else:
                start = end = None
                warnings.append('absolute_timestamps_missing')
            available = [key for key,(p,h) in SIGNALS.items() if p in columns and h in columns]
            if not available: raise ValueError(f'{filename}: nessuna coppia potenza/HR in W e bpm')
            digest = self.store.blob(data)
            segments.append({'id': sha((filename+digest).encode())[:24], 'filename': filename,
                             'sha256': digest, 'activity_id': activity, 'group': group, 'label': label,
                             'duration_seconds': float(t[-1]-t[0]), 'samples': len(t),
                             'start_timestamp': start, 'end_timestamp': end,
                             'first_lap': meta.get('first_lap', rows[0].get('first_lap')),
                             'last_lap': meta.get('last_lap', rows[0].get('last_lap')),
                             'signals': available, 'warnings': warnings, 'source_metadata': meta})
        ds = {'id': uuid.uuid4().hex, 'name': self._name(name), 'created_at': utc_now(),
              'sources': sources, 'source_manifests': manifests, 'segments': segments,
              'stats': statistics(segments), 'filters': None, 'split': None}
        self.store.write('datasets', ds['id'], ds)
        return ds

    @staticmethod
    def _name(name):
        if not name.strip() or len(name)>120: raise ValueError('Nome richiesto, massimo 120 caratteri')
        return name.strip()

    def rename(self, key, name):
        with self.store.lock:
            ds = self.get(key); ds['name'] = self._name(name)
            self.store.write('datasets', key, ds)
        return ds

    def subset(self, key, name, groups, labels):
        ds = self.get(key)
        selected = [s for s in ds['segments'] if s['group'] in groups and s['label'] in labels]
        if not selected: raise ValueError('Nessun segmento per questi filtri')
        ds.update(id=uuid.uuid4().hex, name=self._name(name), created_at=utc_now(),
                  segments=selected, stats=statistics(selected), split=None,
                  filters={'parent_dataset_id': key, 'groups': groups, 'labels': labels})
        self.store.write('datasets',ds['id'],ds)
        return ds

    def split(self, key, percentages, seed, unit):
        if len(percentages)!=3 or not np.isfinite(percentages).all() or min(percentages)<0 or abs(sum(percentages)-100)>1e-8 or percentages[0]<=0:
            raise ValueError('Percentuali non negative, train positivo e somma 100')
        if unit not in ('segment','activity') or not 0<=seed<2**32: raise ValueError('Unità o seed non validi')
        with self.store.lock:
            ds = self.get(key)
            segments = ds['segments']
            if any(not s['activity_id'] for s in segments):
                raise ValueError('activity_id necessario per verificare le sovrapposizioni prima dello split; importare anche il manifest originale')
            if unit == 'segment':
                by_activity = {}
                for s in segments:
                    if s['activity_id']: by_activity.setdefault(s['activity_id'],[]).append(s)
                for items in by_activity.values():
                    if len(items)<2: continue
                    if any(not s['start_timestamp'] for s in items):
                        raise ValueError('Sovrapposizioni non verificabili: usare split per attività')
                    spans = sorted((datetime.fromisoformat(s['start_timestamp']),datetime.fromisoformat(s['end_timestamp'])) for s in items)
                    latest = spans[0][1]
                    for start, end in spans[1:]:
                        if start <= latest: raise ValueError('Segmenti sovrapposti: usare split per attività')
                        latest = max(latest,end)
            groups = {}
            for s in segments: groups.setdefault(s['id'] if unit=='segment' else s['activity_id'], []).append(s['id'])
            ordered = sorted(groups)
            np.random.default_rng(seed).shuffle(ordered)
            raw = np.array(percentages)*len(ordered)/100
            counts = np.floor(raw).astype(int)
            for i in np.argsort(-(raw-counts), kind='stable')[:len(ordered)-sum(counts)]: counts[i]+=1
            assignments, offset = {}, 0
            for part, n in zip(('train','val','test'),counts):
                assignments[part] = [sid for group in ordered[offset:offset+n] for sid in groups[group]]
                offset += n
            if not assignments['train']: raise ValueError('Split senza train: aumentare la quota train')
            split = {'id': uuid.uuid4().hex, 'unit': unit, 'seed': seed, 'percentages': percentages,
                     'algorithm': 'sorted groups; numpy PCG64 shuffle; largest remainder on group counts v1',
                     'assignments': assignments, 'group_counts': counts.tolist(),
                     'actual_percentages': [100*len(assignments[k])/len(segments) for k in ('train','val','test')],
                     'warnings': ['empty_'+k for k in ('val','test') if not assignments[k]]}
            ds['split'] = split
            self.store.write('datasets',key,ds)
            return split
