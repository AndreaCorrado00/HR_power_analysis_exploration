"""Package the approved G1/G2 selection without changing segment CSV bytes."""
import argparse
from collections import Counter
import copy
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('dataset/dataset_segments.zip'))
    parser.add_argument('--report', type=Path, default=Path('reports/segment_groups'))
    parser.add_argument('--output', type=Path, default=Path('dataset/dataset_segments_G1_G2.zip'))
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    summary = json.loads((args.report / 'summary.json').read_text(encoding='utf-8'))
    if digest(source_bytes) != summary['input_sha256']:
        raise ValueError('Source archive differs from the classified archive')
    classification_bytes = (args.report / 'classificazioni.csv').read_bytes()
    rows = list(csv.DictReader(io.StringIO(classification_bytes.decode('utf-8-sig'))))
    labels = {'UtD': 'UtD', 'DtU': 'DtU', 'Ambiguo': 'Ambigui'}
    folders = [f'{label}_G{group}/' for group in (1, 2) for label in labels.values()]
    counts = Counter({folder: 0 for folder in folders})
    selected, excluded, payloads = [], [], {}
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as source:
        if len(source.namelist()) != len(set(source.namelist())):
            raise ValueError('Duplicate source archive entries')
        original_manifest = json.loads(source.read('manifest.json'))
        entries = {entry['csv_file']: entry for entry in original_manifest['segments']}
        names = [row['id'] + '.csv' for row in rows]
        if (len(names) != len(set(names)) or set(names) != set(entries)
                or len(entries) != len(original_manifest['segments'])
                or set(names) != {n for n in source.namelist() if n.endswith('.csv')}):
            raise ValueError('Classification, manifest and source CSV inventory disagree')
        manifest = copy.deepcopy(original_manifest)
        manifest['segments'] = []
        for row, name in zip(rows, names):
            if row['label'] not in labels or row['group'] not in ('1', '2', '3', '4'):
                raise ValueError(f'Unexpected classification: {row}')
            record = dict(row, original_csv_file=name)
            if row['group'] not in ('1', '2'):
                record['exclusion_reason'] = 'G3/G4 provisionally excluded by user: duration and representation uncertain'
                excluded.append(record)
                continue
            folder = f"{labels[row['label']]}_G{row['group']}/"
            target = folder + name
            if PurePosixPath(name).name != name:
                raise ValueError('Expected flat source filenames')
            payloads[target] = source.read(name)
            counts[folder] += 1
            record.update(csv_file=target, sha256=digest(payloads[target]))
            selected.append(record)
            entry = copy.deepcopy(entries[name])
            entry.update(csv_file=target, empirical_label=row['label'], duration_group=int(row['group']))
            manifest['segments'].append(entry)
    selection = dict(source_archive=args.source.name, source_sha256=digest(source_bytes),
                     classifications_sha256=digest(classification_bytes),
                     duration_thresholds_seconds=summary['thresholds_seconds'],
                     counts=dict(counts), included=selected, excluded=excluded)
    manifest['selection_metadata'] = 'metadata/selection.json'
    manifest['grouping_note'] = 'Empirical labels, not independently validated certainty; G1/G2 only'
    readme = '''# Archivio G1/G2

CSV originali invariati, suddivisi secondo le classificazioni già prodotte.
UtD_G1, DtU_G1, Ambigui_G1; UtD_G2, DtU_G2, Ambigui_G2.
DtU_G2 è presente anche se vuota. G3/G4 sono esclusi provvisoriamente,
non eliminati dalla fonte: durata e presenza nel dataset considerate ambigue.
"Certi" significa non ambigui secondo le regole empiriche attuali,
non validati indipendentemente. Nessun nuovo fitting o preprocessing.

Il manifest conserva i metadati originari e aggiorna i percorsi dei CSV.
metadata/selection.json registra assegnazioni, esclusioni e hash.
metadata/grouping_criteria.md conserva i criteri del report originale;
i link alle immagini in quel documento si riferiscono al report nel repository.

Riproduzione dalla radice del repository:
`.venv/Scripts/python scripts/package_segment_groups.py --output dataset/nuovo_archivio.zip`
L'output deve essere un file nuovo: lo script non sovrascrive archivi esistenti.
'''
    payloads.update({
        'manifest.json': json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'),
        'metadata/selection.json': json.dumps(selection, ensure_ascii=False, indent=2).encode('utf-8'),
        'metadata/grouping_criteria.md': (args.report / 'README.md').read_bytes(),
        'README.md': readme.encode('utf-8'),
    })
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in [(f, b'') for f in folders] + sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    with zipfile.ZipFile(args.output) as output:
        assert output.testzip() is None
        assert all(output.read(name) == data for name, data in payloads.items())
        assert all(folder in output.namelist() for folder in folders)
        assert len([n for n in output.namelist() if n.endswith('.csv')]) == len(selected)
    assert args.source.read_bytes() == source_bytes
    print(json.dumps(dict(output=str(args.output), included=len(selected), excluded=len(excluded),
                          folders=dict(counts), verified=True), indent=2))


if __name__ == '__main__':
    main()
