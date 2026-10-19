import io
import json
import zipfile

import pytest

from webapp.model_identification_app.backend.datasets import DatasetService
from webapp.model_identification_app.backend.storage import Store


def archive():
    b = io.BytesIO()
    entries = []
    with zipfile.ZipFile(b, 'w') as z:
        for i in range(10):
            name = f'UtD_G{1+i%2}/s{i}.csv'
            entries.append({'csv_file': name, 'activity_id': f'a{i//2}.fit',
                            'duration_group': 1+i%2, 'empirical_label': 'UtD'})
            z.writestr(name, 'activity_id,elapsed_seconds,timestamp,power_w,heart_rate_bpm\n' +
                       ''.join(f'a{i//2}.fit,{t},2026-01-01T00:{i:02}:{t:02}Z,{100+t*10},{120+t}\n' for t in range(10)))
        z.writestr('manifest.json', json.dumps({'segments': entries}))
    return b.getvalue()


def test_subset_split_and_rename_survive_reload(tmp_path):
    service = DatasetService(Store(tmp_path))
    ds = service.import_files([('input.zip', archive())], 'Originale')
    assert ds['stats']['count'] == 10
    assert ds['stats']['duration_mean'] == 9
    sub = service.subset(ds['id'], 'G1 UtD', ['1'], ['UtD'])
    assert len(sub['segments']) == 5
    split = service.split(ds['id'], [70,10,20], 42, 'activity')
    again = service.split(ds['id'], [70,10,20], 42, 'activity')
    assert split['assignments'] == again['assignments']
    partitions = [{s['activity_id'] for s in ds['segments'] if s['id'] in split['assignments'][key]} for key in ['train','val','test']]
    assert not partitions[0] & partitions[1]
    assert not partitions[0] & partitions[2]
    service.rename(ds['id'], 'Nuovo')
    assert DatasetService(Store(tmp_path)).get(ds['id'])['name'] == 'Nuovo'
    assert len(service.store.read('datasets', ds['id'])['source_manifests']) == 1


def test_split_rejects_invalid_percentages_and_empty_filters(tmp_path):
    s = DatasetService(Store(tmp_path))
    ds = s.import_files([('in.zip', archive())], 'D')
    with pytest.raises(ValueError): s.split(ds['id'], [70,20,20], 42, 'segment')
    with pytest.raises(ValueError): s.subset(ds['id'], 'empty', ['9'], ['UtD'])


def test_zip_traversal_and_duplicate_names_rejected(tmp_path):
    b = io.BytesIO()
    with zipfile.ZipFile(b,'w') as z: z.writestr('../unsafe.csv','x')
    with pytest.raises(ValueError): DatasetService(Store(tmp_path)).import_files([('bad.zip',b.getvalue())], 'bad')


def test_overlapping_segments_cannot_cross_random_segment_split(tmp_path):
    text = b'activity_id,elapsed_seconds,timestamp,power_w,heart_rate_bpm\na,0,2026-01-01T00:00:00Z,100,120\na,1,2026-01-01T00:00:01Z,110,121\n'
    s = DatasetService(Store(tmp_path))
    ds = s.import_files([('a.csv',text),('b.csv',text)],'overlap')
    with pytest.raises(ValueError, match='sovrapposti'): s.split(ds['id'], [70,10,20], 42, 'segment')


def test_missing_activity_metadata_cannot_bypass_overlap_checks(tmp_path):
    text = b'elapsed_seconds,timestamp,power_w,heart_rate_bpm\n0,2026-01-01T00:00:00Z,100,120\n1,2026-01-01T00:00:01Z,110,121\n'
    s = DatasetService(Store(tmp_path))
    ds = s.import_files([(f'{i}.csv',text) for i in range(10)],'duplicates')
    with pytest.raises(ValueError, match='activity_id'):
        s.split(ds['id'], [70,10,20],42,'segment')
