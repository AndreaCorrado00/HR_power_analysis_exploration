import io
import stat
import struct
import zipfile

import numpy as np
import pytest
from fitdecode.utils import compute_crc

from webapp.model_identification_app.backend.datasets import DatasetService, series
from webapp.model_identification_app.backend.storage import Store, sha


def fit_bytes():
    records = bytes([0x40, 0, 0]) + struct.pack('<H', 20) + bytes([3, 253, 4, 0x86, 7, 2, 0x84, 3, 1, 2])
    for t, p, h in [(0, 200, 120), (1, 0, 121), (5, 65535, 255)]:
        records += bytes([0]) + struct.pack('<IHB', 1000000000+t, p, h)
    content = struct.pack('<BBHI4s', 12, 0x10, 100, len(records), b'.FIT') + records
    return content + struct.pack('<H', compute_crc(content))


def archive(name, data, link=False):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        item = zipfile.ZipInfo(name)
        if link:
            item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(item, data)
    return b.getvalue()


@pytest.mark.parametrize('zipped', [False, True])
def test_fit_preserves_samples_missing_values_and_provenance(tmp_path, zipped):
    service = DatasetService(Store(tmp_path/'store'))
    data = fit_bytes()
    files = [('rides.zip', archive('nested/a.FIT', data))] if zipped else [('a.fit', data)]
    ds = service.import_files(files, 'Activities')
    s, = ds['segments']
    assert s['kind'] == 'activity'
    assert s['activity_id'] == 'fit:'+sha(data)
    assert s['signals'] == ['raw']
    assert s['samples'] == 3 and s['duration_seconds'] == 5
    assert s['quality']['missing_power_samples'] == 1
    assert s['quality']['missing_hr_samples'] == 1
    assert 'recording_gaps' in s['warnings']
    t, p, h = series(service.store.read_blob(s['sha256']), 'raw')
    np.testing.assert_array_equal(t, [0, 1, 5])
    np.testing.assert_allclose(p, [200, 0, np.nan], equal_nan=True)
    np.testing.assert_allclose(h, [120, 121, np.nan], equal_nan=True)
    assert service.store.read_blob(s['source_metadata']['fit_sha256']) == data


def test_local_links_are_bounded_and_uploaded_links_rejected(tmp_path):
    root = tmp_path/'dataset'
    root.mkdir()
    target = root/'a.fit'
    target.write_bytes(fit_bytes())
    service = DatasetService(Store(tmp_path/'store'), dataset_root=root)
    data = archive('cleaned/a.fit', str(target), link=True)
    paths = {'links.zip': root/'links.zip'}
    ds = service.import_files([('links.zip', data)], 'D', local_paths=paths)
    assert len(ds['segments']) == 1
    with pytest.raises(ValueError, match='repository'):
        service.import_files([('links.zip', data)], 'D')
    outside = tmp_path/'outside.fit'
    outside.write_bytes(fit_bytes())
    with pytest.raises(ValueError, match='dataset/'):
        service.import_files([('links.zip', archive('a.fit', str(outside), True))], 'D', local_paths=paths)
    with pytest.raises(ValueError, match='non trovato'):
        service.import_files([('links.zip', archive('a.fit', str(root/'missing.fit'), True))], 'D', local_paths=paths)


def test_same_fit_under_different_names_stays_in_one_split(tmp_path):
    service = DatasetService(Store(tmp_path/'store'))
    ds = service.import_files([('a.fit', fit_bytes()), ('copy.fit', fit_bytes())], 'D')
    split = service.split(ds['id'], [70, 10, 20], 42, 'activity')
    assert len(split['assignments']['train']) == 2


@pytest.mark.parametrize('unit', ['activity', 'segment'])
def test_mixed_fit_csv_split_cannot_hide_overlapping_activity(tmp_path, unit):
    service = DatasetService(Store(tmp_path/'store'))
    csv = b'activity_id,elapsed_seconds,power_w,heart_rate_bpm\na,0,200,120\na,1,0,121\n'
    ds = service.import_files([('a.fit', fit_bytes()), ('part.csv', csv)], 'D')
    with pytest.raises(ValueError, match='FIT.*CSV'):
        service.split(ds['id'], [70, 10, 20], 42, unit)


def test_activity_does_not_inherit_segment_classification(tmp_path):
    service = DatasetService(Store(tmp_path/'store'))
    ds = service.import_files([('rides.zip', archive('UtD_G1/a.fit', fit_bytes()))], 'D')
    assert ds['segments'][0]['group'] == 'unknown'
    assert ds['segments'][0]['label'] == 'unknown'


def test_repository_raw_directory_link_is_supported(tmp_path):
    root = tmp_path/'dataset'
    (root/'raw').mkdir(parents=True)
    external = tmp_path/'raw_data'
    external.mkdir()
    (external/'a.fit').write_bytes(fit_bytes())
    raw = root/'raw/only_road_activities'
    try:
        raw.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlink privilege unavailable')
    service = DatasetService(Store(tmp_path/'store'), dataset_root=root)
    data = archive('a.fit', str(raw/'a.fit'), True)
    ds = service.import_files([('links.zip', data)], 'D', local_paths={'links.zip':root/'links.zip'})
    assert len(ds['segments']) == 1


def test_sources_include_cleaned_zip_and_fit(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from webapp.model_identification_app.backend import app
    root = tmp_path/'dataset'
    root.mkdir()
    (root/'a.fit').write_bytes(fit_bytes())
    (root/'cleaned.zip').write_bytes(archive('a.fit', fit_bytes()))
    monkeypatch.setattr(app, 'REPO_ROOT', tmp_path)
    with TestClient(app.create_app(tmp_path/'store')) as client:
        assert client.get('/api/sources').json() == ['dataset/a.fit', 'dataset/cleaned.zip']
        response = client.post('/api/datasets/import', json={'name':'D', 'paths':['dataset/cleaned.zip']})
        assert response.status_code == 200, response.text
