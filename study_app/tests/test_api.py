from fastapi.testclient import TestClient
from study_app.backend.app import create_app


def test_fresh_install_empty_and_no_fitting_on_crud(tmp_path):
    with TestClient(create_app(tmp_path,execute_jobs=False)) as c:
        assert c.get('/api/athletes').json()==[]
        a=c.post('/api/athletes',json={'first_name':'Anna','last_name':'Rossi','age':32}).json()
        assert c.patch('/api/athletes/'+a['id'],json={'ftp_w':240}).status_code==200
        assert c.get('/api/athletes/'+a['id']+'/models').json()==[]
        assert c.get('/api/athletes/'+a['id']+'/jobs').json()==[]
        assert c.post('/api/athletes',headers={'Origin':'https://evil.example'},json={}).status_code==403
        assert c.get('/api/athletes',headers={'Host':'evil.example'}).status_code==400
