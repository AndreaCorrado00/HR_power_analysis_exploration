import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from test_processing import archive


def load(client, blob):
    response = client.post('/api/reconstruction/import', content=blob)
    assert response.status_code == 200, response.text
    return response.json()['datasetId']


def proposal(client, dataset, sensitivity=50):
    response = client.post('/api/reconstruction/propose', json={
        'datasetId': dataset, 'sourceId': 'a.csv', 'sensitivity': sensitivity})
    assert response.status_code == 200, response.text
    return response.json()


def test_noisy_thirty_fifteen_laps_keep_their_boundaries():
    c = TestClient(create_app())
    levels = np.tile(np.r_[np.full(30, 300), np.full(15, 100)], 3)
    power = levels + np.random.default_rng(42).normal(0, 3, len(levels))
    bounds = [0, 30, 45, 75, 90, 120, 135]
    laps = [{'index': i+1, 'start': start, 'end': end} for i, (start, end) in enumerate(zip(bounds, bounds[1:]))]
    dataset = load(c, archive(range(len(power)), power, laps=laps))
    result = proposal(c, dataset)
    assert len(result['blocks']) == 6
    assert [b['power'] for b in result['blocks']] == pytest.approx([300, 100]*3, abs=3)
    assert [b['start'] for b in result['blocks']] == pytest.approx([0, 30, 45, 75, 90, 120], abs=1)
    assert result['points'][0]['power_w'] == pytest.approx(power[0])
    # Legacy sensitivity inputs cannot alter the explicit lap structure.
    assert proposal(c, dataset, 0)['blocks'] == proposal(c, dataset, 100)['blocks']


def test_gaps_and_missing_power_are_not_bridged():
    c = TestClient(create_app())
    times = list(range(20))+list(range(40, 60))
    power = [200]*40
    power[10] = None
    result = proposal(c, load(c, archive(times, power)))
    assert result['gapCount'] == 1
    assert result['missingPower'] == 1
    assert all(not (b['start'] <= 10 < b['end']) for b in result['blocks'])
    assert all(not (b['start'] < 40 and b['end'] > 20) for b in result['blocks'])


def test_cut_export_roundtrip_preserves_samples_targets_and_origin(tmp_path, monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS', str(tmp_path))
    c = TestClient(create_app())
    dataset = load(c, archive(range(90), [300]*30+[100]*15+[300]*30+[100]*15, laps=[
        {'index': 1, 'start': 0, 'end': 30}, {'index': 2, 'start': 30, 'end': 45},
        {'index': 3, 'start': 45, 'end': 75}, {'index': 4, 'start': 75, 'end': 90}]))
    auto = proposal(c, dataset)
    blocks = [dict(b, power=310 if b['power'] > 200 else 110) for b in auto['blocks']]
    parts = [{'sourceId': 'a.csv', 'start': start, 'end': end, 'blocks': blocks,
              'sensitivity': 50, 'automaticBlocks': auto['blocks'], 'constraints': []}
             for start, end in [(0, 45), (45, 90)]]
    response = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': parts})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        manifest = json.loads(z.read('manifest.json'))
        assert len(manifest['segments']) == 2
        frames = [pd.read_csv(z.open(e['csv_file'])) for e in manifest['segments']]
        assert len(pd.concat(frames).timestamp.unique()) == 90
        assert sum(map(len, frames)) == 90
        assert frames[1].elapsed_seconds.iloc[0] == 0
        assert frames[1].source_elapsed_seconds.iloc[0] == 45
        assert frames[0].power_w.iloc[0] == 300
        assert frames[0].power_target_w.iloc[0] == 310
        assert all(e['origin_page'] == 'reconstruction' for e in manifest['segments'])
        assert manifest['reconstruction']['source_sha256']
        entry = manifest['segments'][0]
        assert entry['reconstruction']['automaticBlocks'][0]['power'] == 300
        assert z.read('intervals.csv')
    assert len(list(tmp_path.glob('dataset_segments_reconstructed_*.zip'))) == 1
    again = load(c, response.content)
    restored = c.post('/api/reconstruction/propose', json={
        'datasetId': again, 'sourceId': entry['csv_file'], 'sensitivity': 50}).json()
    assert restored['saved']['blocks'][0]['power'] == 310
    # The existing processing page can still read reconstructed archives.
    assert c.post('/api/processing/import', content=response.content).status_code == 200


@pytest.mark.parametrize('change', [
    {'start': 12, 'end': 5}, {'start': -1}, {'end': 1000},
    {'blocks': [{'start': 0, 'end': 20, 'power': -5}]},
    {'blocks': [{'start': 0, 'end': 15, 'power': 200}, {'start': 10, 'end': 20, 'power': 100}]},
])
def test_invalid_edits_rejected(change):
    c = TestClient(create_app()); dataset = load(c, archive(range(20), [200]*20))
    part = {'sourceId': 'a.csv', 'start': 0, 'end': 20,
            'blocks': [{'start': 0, 'end': 20, 'power': 200}], **change}
    assert c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [part]}).status_code == 422


def test_reimport_keeps_previous_dataset_available():
    c = TestClient(create_app())
    first = load(c, archive()); load(c, archive())
    assert c.post('/api/reconstruction/propose', json={'datasetId': first, 'sourceId': 'a.csv'}).status_code == 200


def test_cut_inside_locked_repeat_preserves_partial_lock_on_reopen():
    c = TestClient(create_app()); dataset = load(c, archive(range(90), [300]*30+[100]*15+[300]*30+[100]*15, laps=[
        {'index': 1, 'start': 0, 'end': 30}, {'index': 2, 'start': 30, 'end': 45},
        {'index': 3, 'start': 45, 'end': 75}, {'index': 4, 'start': 75, 'end': 90}]))
    blocks = proposal(c, dataset)['blocks']
    part = {'sourceId': 'a.csv', 'start': 35, 'end': 80, 'blocks': blocks,
            'constraints': [{'start': 0, 'end': 90, 'on': 30, 'off': 15}]}
    response = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [part]})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        manifest = json.loads(z.read('manifest.json'))
        saved = manifest['segments'][0]['reconstruction']
        assert saved['constraints'] == [{'start': 0, 'end': 45, 'on': 30, 'off': 15,
                                          'phase': 1, 'partialStart': True, 'partialEnd': True}]
        assert manifest['reconstruction']['excluded_ranges']['a.csv'] == [[0, 35], [80, 90]]
    again = load(c, response.content)
    part = {'sourceId': manifest['segments'][0]['csv_file'], 'start': 0, 'end': 45, **saved}
    assert c.post('/api/reconstruction/export', json={'datasetId': again, 'segments': [part]}).status_code == 200


def test_inconsistent_on_off_contract_is_rejected():
    c = TestClient(create_app()); dataset = load(c, archive(range(60), [300]*30+[100]*30))
    part = {'sourceId': 'a.csv', 'start': 0, 'end': 60, 'blocks': [{'start': 0, 'end': 30, 'power': 300}, {'start': 30, 'end': 60, 'power': 100}],
            'constraints': [{'start': 0, 'end': 60, 'on': 30, 'off': 15}]}
    assert c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [part]}).status_code == 422


def test_mixed_archive_keeps_both_origins_and_processing_compatibility():
    from backend.processing_service import read_archive
    from backend.reconstruction_api import Part
    from backend.reconstruction_service import export_reconstruction
    dataset = read_archive(archive(range(20), [200]*20))
    part = Part(source_id='a.csv', start=0, end=20, blocks=[{'start': 0, 'end': 20, 'power': 210}])
    blob = export_reconstruction(dataset, [part], archive())
    imported = read_archive(blob)
    assert [e['origin_page'] for e in imported.manifest['segments']] == ['reconstruction', 'extraction', 'extraction']
    assert len(imported.frames) == 3


def test_subsample_cut_does_not_export_negative_interval_duration():
    c = TestClient(create_app()); dataset = load(c, archive(range(20), [200]*20))
    part = {'sourceId': 'a.csv', 'start': 5.5, 'end': 15.5,
            'blocks': [{'start': 0, 'end': 5.8, 'power': 200}, {'start': 5.8, 'end': 20, 'power': 210}]}
    response = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [part]})
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        saved = json.loads(z.read('manifest.json'))['segments'][0]['reconstruction']
        assert all(b['start'] < b['end'] for b in saved['blocks'])


@pytest.mark.parametrize('times,end', [([0, 2, 4, 6, 8], 2), ([0, 1, 3, 6, 9], 6)])
def test_reopen_cut_preserves_source_support_instead_of_reestimating_it(times, end):
    c = TestClient(create_app()); dataset = load(c, archive(times, [200]*len(times)))
    part = {'sourceId': 'a.csv', 'start': 0, 'end': end, 'blocks': [{'start': 0, 'end': end, 'power': 200}]}
    exported = c.post('/api/reconstruction/export', json={'datasetId': dataset, 'segments': [part]})
    assert exported.status_code == 200
    again = load(c, exported.content)
    result = c.post('/api/reconstruction/propose', json={'datasetId': again, 'sourceId': 'reconstructed/segment_0001.csv'})
    assert result.status_code == 200
    assert result.json()['end'] == end
    assert result.json()['saved']['supportEnd'] == end
