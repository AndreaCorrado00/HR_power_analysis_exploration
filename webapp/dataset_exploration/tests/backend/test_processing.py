import io
import json
import zipfile

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app


def archive(times=(0, 1, 2, 3, 4), power=(0, 0, 90, 0, 0)):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as z:
        entries = []
        for name in ('a.csv', 'b.csv'):
            frame = pd.DataFrame({'activity_id': 'ride', 'first_lap': 1, 'last_lap': 2,
                'timestamp': [pd.Timestamp('2025-01-01', tz='UTC') + pd.Timedelta(seconds=t) for t in times],
                'elapsed_seconds': times, 'power_w': power, 'heart_rate_bpm': 150})
            z.writestr(name, frame.to_csv(index=False))
            entries.append({'csv_file': name, 'activity_id': 'ride', 'first_lap': 1, 'last_lap': 2})
        z.writestr('manifest.json', json.dumps({'format_version': 1, 'segments': entries}))
    return bio.getvalue()


def load(client, blob=None):
    r = client.post('/api/processing/import', content=blob or archive(), headers={'Content-Type': 'application/zip'})
    assert r.status_code == 200, r.text
    return r.json()


def request(data, **changes):
    return {'datasetId': data['datasetId'], 'selected': ['a.csv'], 'windowSeconds': 3, **changes}


def test_import_smooth_normalize_and_repeat_from_raw():
    c = TestClient(create_app()); data = load(c)
    assert len(data['segments']) == 2
    opts = request(data, normalization={'weightKg': 60, 'hrMaxBpm': 200, 'hrThresholdBpm': 180,
        'normalizePower': True, 'normalizeHrMax': True, 'normalizeHrThreshold': True})
    r = c.post('/api/processing/preview', json=opts)
    assert r.status_code == 200, r.text
    points = r.json()['segments'][0]['points']
    assert [p['power_ma_w'] for p in points] == [0, 30, 30, 30, 0]
    assert points[2]['power_w'] == 90
    assert points[2]['power_ma_w_kg'] == .5
    assert points[2]['hr_pct_max'] == 75
    assert points[2]['hr_ma_pct_threshold'] == pytest.approx(100 * 150 / 180)
    exported = c.post('/api/processing/export', json=opts)
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        manifest = json.loads(z.read('manifest.json'))
        assert len(manifest['segments']) == 1
        assert manifest['processing']['window_seconds'] == 3
        assert manifest['source']['sha256']
    again = load(c, exported.content)
    repeat = c.post('/api/processing/preview', json=request(again)).json()
    assert repeat['segments'][0]['points'][2]['power_ma_w'] == 30
    assert 'power_w_kg' not in repeat['segments'][0]['points'][2]


def test_gap_blocks_and_missing_values():
    c = TestClient(create_app())
    data = load(c, archive((0, 1, 2, 20, 21, 22), (0, None, 90, 300, 300, 300)))
    assert data['segments'][0]['gapCount'] == 1
    points = c.post('/api/processing/preview', json=request(data, windowSeconds=10)).json()['segments'][0]['points']
    assert points[2]['power_ma_w'] is None
    assert points[3]['power_ma_w'] == 300
    assert points[3]['ma_sample_count'] == 3
    assert points[3]['ma_incomplete'] is True


@pytest.mark.parametrize('changes', [ {'windowSeconds': 4}, {'selected': []},
    {'selected': ['unknown.csv']}, {'selected': ['a.csv', 'a.csv']},
    {'normalization': {'normalizePower': True, 'weightKg': 0}}])
def test_invalid_processing_requests(changes):
    c = TestClient(create_app()); data = load(c)
    assert c.post('/api/processing/export', json=request(data, **changes)).status_code == 422


def test_invalid_zip_is_reported():
    c = TestClient(create_app())
    assert c.post('/api/processing/import', content=b'bad zip').status_code == 422


def test_even_window_is_ten_samples_and_shared_by_signals():
    c = TestClient(create_app()); data = load(c, archive(tuple(range(30)), tuple(range(30))))
    p = c.post('/api/processing/preview', json=request(data, windowSeconds=10)).json()['segments'][0]['points'][15]
    assert p['ma_sample_count'] == 10
    assert p['power_ma_w'] == 14.5
    assert p['heart_rate_ma_bpm'] == 150
    assert p['ma_incomplete'] is False
