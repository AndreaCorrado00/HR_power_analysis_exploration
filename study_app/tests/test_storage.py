import pytest
from study_app.backend.repository import Repository


def test_athletes_are_isolated_and_artifacts_immutable(tmp_path):
    r=Repository(tmp_path)
    a=r.create_athlete({'first_name':'A','last_name':'B','age':30,'ftp_w':260})
    b=r.create_athlete({'first_name':'A','last_name':'B','age':30})
    assert a['id'] != b['id']
    x=r.create('models',a['id'],{'value':1})
    assert r.list('models',b['id']) == []
    with pytest.raises(ValueError): r.get(x['id'],b['id'])
    r.update_athlete(a['id'],{'ftp_w':300})
    assert r.get(x['id'])['value']==1
    r2=Repository(tmp_path)
    assert len(r2.list('athletes'))==2
    with pytest.raises(ValueError): r.update_athlete(a['id'],{'age':-1})


def test_modified_artifact_is_detected_before_use(tmp_path):
    r=Repository(tmp_path);a=r.create_athlete({'first_name':'A','last_name':'B','age':30})
    x=r.create('models',a['id'],{'value':1})
    path=tmp_path/'athletes'/a['id']/'models'/(x['id']+'.json')
    path.write_text(path.read_text().replace('"value": 1','"value": 999'))
    with pytest.raises(ValueError,match='integrità'):r.get(x['id'])
