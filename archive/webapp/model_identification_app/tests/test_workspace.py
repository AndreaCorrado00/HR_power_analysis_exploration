from fastapi.testclient import TestClient

from webapp.model_identification_app.backend.app import create_app


def test_external_sources_and_separate_athlete_storage(tmp_path, monkeypatch):
    source = tmp_path / 'external'
    source.mkdir()
    csv = b'elapsed_seconds,power_w,heart_rate_bpm\n0,100,100\n1,120,101\n2,130,102\n'
    (source / 'ride.csv').write_bytes(csv)
    monkeypatch.setenv('HR_POWER_SOURCE', str(source))
    with TestClient(create_app(tmp_path / 'athlete-a')) as a:
        sources = a.get('/api/sources').json()
        assert sources == [str(source / 'ride.csv')]
        response = a.post('/api/datasets/import', json={'name': 'A', 'paths': sources})
        assert response.status_code == 200, response.text
        assert len(a.get('/api/datasets').json()) == 1
        outside = tmp_path / 'other.csv'
        outside.write_bytes(csv)
        assert a.post('/api/datasets/import', json={'name': 'outside', 'paths': [str(outside)]}).status_code == 400
    with TestClient(create_app(tmp_path / 'athlete-b')) as b:
        assert b.get('/api/datasets').json() == []
    assert (source / 'ride.csv').read_bytes() == csv


def test_exports_are_copied_to_destination_without_overwriting(tmp_path, monkeypatch):
    destination = tmp_path / 'exports'
    monkeypatch.setenv('HR_POWER_EXPORTS', str(destination))
    app = create_app(tmp_path / 'storage')
    monkeypatch.setattr(app.state.runs, 'export', lambda key, kind: (b'report', 'report.pdf'))
    with TestClient(app) as client:
        for _ in range(2):
            response = client.post('/api/runs/example/exports/pdf')
            assert response.status_code == 200
            assert response.content == b'report'
            assert response.headers['x-export-path']
    files = list(destination.glob('*.pdf'))
    assert len(files) == 2
    assert all(path.read_bytes() == b'report' for path in files)
