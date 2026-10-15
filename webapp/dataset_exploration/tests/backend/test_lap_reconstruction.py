import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from test_processing import archive
from test_reconstruction import load, proposal
from test_loaded_source import loaded


def with_laps(blob, laps):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(blob)) as source, zipfile.ZipFile(out, 'w') as dest:
        for name in source.namelist():
            data = source.read(name)
            if name == 'manifest.json':
                manifest = json.loads(data)
                manifest['segments'][0]['laps'] = laps
                data = json.dumps(manifest)
            dest.writestr(name, data)
    return out.getvalue()


def test_lap_targets_use_observed_mean_and_assign_boundary_once():
    c = TestClient(create_app())
    laps = [{'index': 1, 'start': 0, 'end': 3}, {'index': 2, 'start': 3, 'end': 6}]
    blob = with_laps(archive(range(6), [0, 200, None, 300, -1, 100]), laps)
    result = proposal(c, load(c, blob))
    assert result['blocks'] == [{'start': 0, 'end': 3, 'power': 100}, {'start': 3, 'end': 6, 'power': 200}]
    assert [lap['validSamples'] for lap in result['laps']] == [2, 2]
    assert [lap['invalidSamples'] for lap in result['laps']] == [1, 1]
    assert result['initialization'] == 'lap-mean-v1'


def test_no_laps_or_no_valid_power_does_not_invent_targets():
    c = TestClient(create_app())
    assert proposal(c, load(c, archive(range(20), [200]*20)))['blocks'] == []
    blob = with_laps(archive(range(3), [None, -1, None]), [{'index': 1, 'start': 0, 'end': 3}])
    result = proposal(c, load(c, blob))
    assert result['blocks'] == []
    assert result['laps'][0]['validSamples'] == 0


def test_fit_laps_survive_direct_transfer_and_extraction_zip(tmp_path):
    c, source = loaded(tmp_path)
    selection = {'activityId': 'ride.fit', 'firstLap': 1, 'lastLap': 1}
    direct = c.post('/api/reconstruction/from-loaded', json={'datasetId': source['datasetId'], 'segments': [selection]}).json()
    result = c.post('/api/reconstruction/propose', json={'datasetId': direct['datasetId'], 'sourceId': direct['segments'][0]['id']}).json()
    assert len(result['blocks']) == 1
    assert result['blocks'][0]['power'] == 225
    blob = c.post('/api/exports', json={'segments': [selection], 'normalization': {}}).content
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        entry = json.loads(z.read('manifest.json'))['segments'][0]
    assert entry['laps'][0]['index'] == 1
    assert entry['laps'][0]['source_start_timestamp']
    dataset = load(c, blob)
    reopened = c.post('/api/reconstruction/propose', json={'datasetId': dataset, 'sourceId': entry['csv_file']}).json()
    assert reopened['blocks'] == result['blocks']


def test_cut_rebases_laps_and_preserves_original_reference(tmp_path, monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS', str(tmp_path))
    c = TestClient(create_app())
    laps = [{'index': 7, 'start': 0, 'end': 6, 'source_start_timestamp': '2025-01-01T00:00:00Z'}]
    dataset = load(c, with_laps(archive(range(6), [200]*6), laps))
    response = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [
        {'sourceId': 'a.csv', 'start': 2, 'end': 5, 'blocks': [{'start': 0, 'end': 6, 'power': 220}]}]})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        entry = json.loads(z.read('manifest.json'))['segments'][0]
    lap = entry['laps'][0]
    assert (lap['start'], lap['end'], lap['index']) == (0, 3, 7)
    assert lap['partialStart'] and lap['partialEnd']
    assert lap['source_start_timestamp'] == laps[0]['source_start_timestamp']
    reopened = load(c, response.content)
    result = c.post('/api/reconstruction/propose', json={'datasetId': reopened, 'sourceId': entry['csv_file']}).json()
    assert result['saved']['blocks'] == [{'start': 0, 'end': 3, 'power': 220}]


@pytest.mark.parametrize('laps', [[{'index': 1, 'start': 0, 'end': float('nan')}],
                                 [{'index': 1, 'start': 0, 'end': 3}, {'index': 2, 'start': 2, 'end': 4}]])
def test_invalid_lap_metadata_is_rejected(laps):
    c = TestClient(create_app())
    assert c.post('/api/reconstruction/import', content=with_laps(archive(), laps)).status_code == 422


def test_saved_legacy_blocks_reopen_without_lap_initialization(tmp_path, monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS', str(tmp_path))
    c = TestClient(create_app())
    dataset = load(c, archive())
    blocks = [{'start': 0, 'end': 2, 'power': 310}, {'start': 2, 'end': 5, 'power': 120}]
    response = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [
        {'sourceId': 'a.csv', 'start': 0, 'end': 5, 'blocks': blocks}]})
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(response.content)) as source, zipfile.ZipFile(out, 'w') as dest:
        for name in source.namelist():
            data = source.read(name)
            if name == 'manifest.json':
                manifest = json.loads(data)
                for entry in manifest['segments']:
                    entry.pop('laps', None)
                    entry['reconstruction'].pop('initialization', None)
                data = json.dumps(manifest)
            dest.writestr(name, data)
    dataset = load(c, out.getvalue())
    result = c.post('/api/reconstruction/propose', json={'datasetId': dataset, 'sourceId': 'reconstructed/segment_0001.csv'}).json()
    assert result['saved']['blocks'] == blocks
    assert result['blocks'] == []
    assert result['initialization'] == 'legacy-saved'


def test_lap_spanning_recording_gap_reports_gap_without_inventing_samples():
    c = TestClient(create_app())
    dataset = load(c, archive([0, 1, 10, 11], [100, 100, 300, 300], laps=[{'index': 1, 'start': 0, 'end': 12}]))
    result = proposal(c, dataset)
    assert result['blocks'] == [{'start': 0, 'end': 12, 'power': 200}]
    assert [p['elapsed_seconds'] for p in result['points']] == [0, 1, 10, 11]
    assert result['gaps'] == [{'start': 2, 'end': 10}]
