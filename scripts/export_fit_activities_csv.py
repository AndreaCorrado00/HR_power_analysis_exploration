"""Export complete FIT activities as a model-identification CSV ZIP.

Run from the repository root with .venv/Scripts/python.
An optional prior import can reuse conversions after checking source/blob hashes.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webapp.model_identification_app.backend.datasets import unpack
from webapp.model_identification_app.backend.fit_import import convert_fit
from webapp.model_identification_app.backend.storage import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cached-dataset', type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if args.output.exists():
        raise ValueError('Output already exists; choose a new filename')
    source_data = source.read_bytes()
    records, _, _ = unpack([(source.name, source_data)], ROOT/'dataset', {source.name: source})
    if any(not name.lower().endswith('.fit') for name, _, _ in records):
        raise ValueError('This exporter requires FIT activities only')
    cache = {}
    if args.cached_dataset:
        cached = json.loads(args.cached_dataset.read_text(encoding='utf-8'))
        if not any(s['sha256'] == sha(source_data) for s in cached['sources']):
            raise ValueError('Cached import source hash differs')
        cache = {s['source_metadata']['fit_sha256']: s for s in cached['segments']}
    entries, contents = [], []
    for index, (name, fit, source_meta) in enumerate(records, 1):
        digest = sha(fit)
        prior = cache.get(digest)
        if prior:
            blobs = args.cached_dataset.parent.parent/'blobs'
            if sha((blobs/digest).read_bytes()) != digest:
                raise ValueError('Cached FIT integrity check failed')
            data = (blobs/prior['sha256']).read_bytes()
            if sha(data) != prior['sha256']:
                raise ValueError('Cached CSV integrity check failed')
            meta = prior['source_metadata']
        else:
            data, meta = convert_fit(fit, name)
        csv_name = f'activities/{index:03d}_{Path(name.split("::")[-1]).stem}.csv'
        contents.append((csv_name, data))
        entries.append({**source_meta, **meta, 'csv_file': csv_name,
                        'csv_sha256': sha(data), 'duration_group': 'unknown',
                        'empirical_label': 'unknown', 'first_lap': None, 'last_lap': None,
                        'selection': 'all FIT record messages; no lap selection'})
        print(f'{index}/{len(records)} {csv_name}', flush=True)
    manifest = {
        'format_version': 1, 'dataset_kind': 'complete_activities',
        'source_archive': str(source), 'source_archive_sha256': sha(source_data),
        'converter_sha256': sha((ROOT/'webapp/model_identification_app/backend/fit_import.py').read_bytes()),
        'reproduce': f'.venv/Scripts/python scripts/export_fit_activities_csv.py "{args.source}" "{args.output}"',
        'columns': {'elapsed_seconds': {'unit': 's'}, 'power_w': {'unit': 'W'},
                    'heart_rate_bpm': {'unit': 'bpm'}, 'timestamp': {'unit': 'ISO 8601 UTC'},
                    'cadence_rpm': {'unit': 'rpm'}, 'speed_m_s': {'unit': 'm/s'},
                    'altitude_m': {'unit': 'm'}, 'temperature_c': {'unit': 'degC'}},
        'preprocessing': {'filtering': False, 'interpolation': False, 'resampling': False,
                          'missing_values': 'empty CSV cells; no sample removal',
                          'time_origin': 'first FIT record; full activity regardless of laps'},
        'warnings_by_activity': dict(Counter(w for e in entries for w in e['warnings'])),
        'segments': entries,
    }
    with zipfile.ZipFile(args.output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for filename, data in contents:
            archive.writestr(filename, data)
        archive.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f'Created {args.output}: {len(entries)} CSV files')


if __name__ == '__main__':
    main()
