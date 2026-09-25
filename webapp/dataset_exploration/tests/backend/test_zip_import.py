import io
import json
import stat
import struct
import zipfile
import pytest
from fastapi.testclient import TestClient
from fitdecode.utils import compute_crc
from backend.app import create_app


def minimal_fit():
    # Two records and one lap. Timestamp, power and HR are unmodified FIT values.
    records = bytes([0x40, 0, 0]) + struct.pack('<H', 20) + bytes([3, 253, 4, 0x86, 7, 2, 0x84, 3, 1, 2])
    records += bytes([0]) + struct.pack('<IHB', 1000000000, 200, 120)
    records += bytes([0]) + struct.pack('<IHB', 1000000010, 250, 130)
    records += bytes([0x41, 0, 0]) + struct.pack('<H', 19) + bytes([2, 253, 4, 0x86, 2, 4, 0x86])
    records += bytes([1]) + struct.pack('<II', 1000000010, 1000000000)
    header = struct.pack('<BBHI4s', 12, 0x10, 100, len(records), b'.FIT')
    content = header + records
    return content + struct.pack('<H', compute_crc(content))


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / 'rides.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('rides/day/a.fit', minimal_fit())
        z.writestr('rides/day/b.FIT', minimal_fit())
        z.writestr('rides/other/c.fit', minimal_fit())
    return path


def test_browse_zip_select_fit_preview_and_export(archive):
    client = TestClient(create_app())
    listing = client.get('/api/datasets/browse', params={'path': str(archive), 'folder': 'rides/day'}).json()
    assert [e['name'] for e in listing['entries']] == ['a.fit', 'b.FIT']
    response = client.post('/api/datasets/load', json={'path': str(archive), 'folder': 'rides/day', 'selectedFiles': ['rides/day/a.fit']})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['extractable']) == 1 and not data['excluded']
    activity = data['extractable'][0]
    assert activity['recordCount'] == 2 and len(activity['laps']) == 1
    points = client.get('/api/activities/rides/day/a.fit/series').json()['points']
    assert [p['power'] for p in points] == [200, 250]
    selection = {'activityId': activity['activityId'], 'firstLap': 1, 'lastLap': 1}
    preview = client.post('/api/segments/preview', json={**selection, 'normalizePower': True, 'weightKg': 50})
    assert preview.json()['points'][0]['powerWKg'] == 4
    exported = client.post('/api/exports', json={'segments': [selection]})
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        assert len(json.loads(z.read('manifest.json'))['segments']) == 1
    assert not (archive.parent / 'rides').exists()


def test_zip_folder_selection_and_invalid_selection(archive):
    client = TestClient(create_app())
    data = client.post('/api/datasets/load', json={'path': str(archive), 'folder': 'rides/day'}).json()
    assert len(data['extractable']) == 2
    bad = client.post('/api/datasets/load', json={'path': str(archive), 'folder': 'rides/day', 'selectedFiles': ['rides/other/c.fit']})
    assert bad.status_code == 400
    assert client.post('/api/datasets/load', json={'path': str(archive), 'selectedFiles': []}).status_code == 400


def test_zip_symlink_and_missing_target(tmp_path):
    target = tmp_path / 'original.fit'
    target.write_bytes(minimal_fit())
    path = tmp_path / 'links.zip'
    with zipfile.ZipFile(path, 'w') as z:
        for name, destination in [('linked.fit', str(target)), ('missing.fit', str(tmp_path/'missing.fit'))]:
            item = zipfile.ZipInfo(name); item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(item, destination)
    client = TestClient(create_app())
    data = client.post('/api/datasets/load', json={'path': str(path)}).json()
    assert data['extractable'][0]['recordCount'] == 2
    assert 'sorgente non trovato' in data['excluded'][0]['exclusionReason']
    assert client.get('/api/activities/linked.fit/series').status_code == 200


def test_local_folder_browse_and_fit_selection(tmp_path):
    (tmp_path/'a.fit').write_bytes(minimal_fit())
    (tmp_path/'b.fit').write_bytes(minimal_fit())
    client = TestClient(create_app())
    assert len(client.get('/api/datasets/browse', params={'path':str(tmp_path)}).json()['entries']) == 2
    data = client.post('/api/datasets/load', json={'path':str(tmp_path), 'selectedFiles':['b.fit']}).json()
    assert [a['activityId'] for a in data['extractable']] == ['b.fit']


def test_bad_zip_and_unsafe_names_are_rejected(tmp_path):
    path = tmp_path/'bad.zip'; path.write_bytes(b'not zip')
    client = TestClient(create_app())
    assert client.get('/api/datasets/browse', params={'path':str(path)}).status_code == 400
    with zipfile.ZipFile(path,'w') as z: z.writestr('../outside.fit',minimal_fit())
    assert client.post('/api/datasets/load',json={'path':str(path)}).status_code == 400
