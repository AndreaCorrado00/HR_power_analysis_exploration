import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from test_zip_import import minimal_fit


def loaded(tmp_path):
    (tmp_path/'ride.fit').write_bytes(minimal_fit())
    c = TestClient(create_app())
    r = c.post('/api/datasets/load', json={'path': str(tmp_path)})
    assert r.status_code == 200
    return c, r.json()


def test_direct_processing_equals_export_import_and_survives_source_reload(tmp_path):
    c, source = loaded(tmp_path)
    selection = {'activityId': 'ride.fit', 'firstLap': 1, 'lastLap': 1}
    direct = c.post('/api/processing/from-loaded', json={'datasetId': source.get('datasetId'), 'segments': [selection]})
    assert direct.status_code == 200, direct.text
    data = direct.json()
    options = {'datasetId': data['datasetId'], 'selected': [data['segments'][0]['id']], 'windowSeconds': 5}
    direct_points = c.post('/api/processing/preview', json=options).json()['segments'][0]['points']
    blob = c.post('/api/exports', json={'segments': [selection], 'normalization': {}}).content
    # Reloading FIT state must not change the independent processing snapshot.
    c.post('/api/datasets/load', json={'path': str(tmp_path)})
    assert c.post('/api/processing/preview', json=options).json()['segments'][0]['points'] == direct_points
    exported = c.post('/api/processing/export', json=options)
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        m = json.loads(z.read('manifest.json'))
        assert m['source']['manifest']['loaded_source']['dataset_id'] == source['datasetId']
    imported = c.post('/api/processing/import', content=blob).json()
    zip_points = c.post('/api/processing/preview', json={**options, 'datasetId': imported['datasetId'],
                       'selected': [imported['segments'][0]['id']]}).json()['segments'][0]['points']
    assert direct_points == zip_points


def test_whole_activity_without_laps_opens_and_exports_as_reconstruction(tmp_path, monkeypatch):
    import backend.app as module
    # Exercise real FIT decoding but remove lap messages, as with lapless workouts.
    original = module.read_source_fit
    def no_laps(*args):
        activity = original(*args)
        activity.messages['lap'] = []
        return activity
    monkeypatch.setattr(module, 'read_source_fit', no_laps)
    c, source = loaded(tmp_path)
    assert not source['extractable']
    r = c.post('/api/reconstruction/from-loaded', json={'datasetId': source.get('datasetId'),
              'segments': [{'activityId': 'ride.fit'}]})
    assert r.status_code == 200, r.text
    data = r.json(); name = data['segments'][0]['id']
    proposal = c.post('/api/reconstruction/propose', json={'datasetId': data['datasetId'], 'sourceId': name}).json()
    assert [p['power_w'] for p in proposal['points']] == [200, 250]
    blob = c.post('/api/reconstruction/export', json={'datasetId': data['datasetId'], 'segments': [
        {'sourceId': name, 'start': 0, 'end': proposal['end'], 'blocks': proposal['blocks']}]}).content
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        entry = json.loads(z.read('manifest.json'))['segments'][0]
        assert entry['selection_kind'] == 'whole_activity'
        assert entry['first_lap'] == entry['last_lap'] == 0


@pytest.mark.parametrize('target', ['processing', 'reconstruction'])
def test_stale_loaded_selection_is_rejected_without_replacing_target(tmp_path, target):
    c, source = loaded(tmp_path)
    req = {'datasetId': source.get('datasetId'), 'segments': [{'activityId': 'ride.fit', 'firstLap': 1, 'lastLap': 1}]}
    r = c.post(f'/api/{target}/from-loaded', json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    c.post('/api/datasets/load', json={'path': str(tmp_path)})
    assert c.post(f'/api/{target}/from-loaded', json=req).status_code == 409
    if target == 'processing':
        assert c.post('/api/processing/preview', json={'datasetId': data['datasetId'], 'selected': [data['segments'][0]['id']]}).status_code == 200
    else:
        assert c.post('/api/reconstruction/propose', json={'datasetId': data['datasetId'], 'sourceId': data['segments'][0]['id']}).status_code == 200


def test_direct_selection_rejects_duplicates_partial_laps_and_unknown_activities(tmp_path):
    c, source = loaded(tmp_path)
    good = {'activityId': 'ride.fit', 'firstLap': 1, 'lastLap': 1}
    for segments in [[], [good, good], [{'activityId': 'ride.fit', 'firstLap': 1}],
                     [{'activityId': 'missing.fit'}]]:
        r = c.post('/api/reconstruction/from-loaded', json={'datasetId': source.get('datasetId'), 'segments': segments})
        assert r.status_code in (404, 422)


def test_direct_selection_keeps_equal_basenames_in_distinct_folders(tmp_path):
    for folder in ('one', 'two'):
        (tmp_path/folder).mkdir()
        (tmp_path/folder/'ride.fit').write_bytes(minimal_fit())
    c = TestClient(create_app())
    source = c.post('/api/datasets/load', json={'path': str(tmp_path)}).json()
    response = c.post('/api/processing/from-loaded', json={'datasetId': source['datasetId'],
        'segments': [{'activityId': f'{folder}/ride.fit', 'firstLap': 1, 'lastLap': 1} for folder in ('one', 'two')]})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len({s['id'] for s in data['segments']}) == 2
    assert {s['activityId'] for s in data['segments']} == {'one/ride.fit', 'two/ride.fit'}


def test_source_reload_during_transfer_cannot_mix_two_loaded_datasets(tmp_path, monkeypatch):
    import backend.app as module
    c, source = loaded(tmp_path)
    original_reader = module.read_source_fit
    def different_power(*args):
        activity = original_reader(*args)
        activity.records['power'] = 999
        return activity
    monkeypatch.setattr(module, 'read_source_fit', different_power)
    original_snapshot = module.snapshot_loaded
    def reload_during_snapshot(root, request, get_activity):
        assert c.post('/api/datasets/load', json={'path': str(tmp_path)}).status_code == 200
        return original_snapshot(root, request, get_activity)
    monkeypatch.setattr(module, 'snapshot_loaded', reload_during_snapshot)
    response = c.post('/api/reconstruction/from-loaded', json={'datasetId': source['datasetId'],
                       'segments': [{'activityId': 'ride.fit'}]})
    assert response.status_code == 200, response.text
    data = response.json()
    result = c.post('/api/reconstruction/propose', json={'datasetId': data['datasetId'], 'sourceId': data['segments'][0]['id']}).json()
    assert [p['power_w'] for p in result['points']] == [200, 250]
