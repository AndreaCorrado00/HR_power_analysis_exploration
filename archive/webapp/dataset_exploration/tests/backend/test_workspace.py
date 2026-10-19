from fastapi.testclient import TestClient
from backend.app import create_app
from backend.source_browser import source_path


def test_empty_source_uses_selected_athlete_folder(tmp_path, monkeypatch):
    monkeypatch.setenv('HR_POWER_SOURCE', str(tmp_path))
    assert source_path('') == tmp_path.resolve()
    with TestClient(create_app()) as client:
        response = client.get('/api/datasets/browse')
        assert response.status_code == 200
        assert response.json()['path'] == str(tmp_path.resolve())
