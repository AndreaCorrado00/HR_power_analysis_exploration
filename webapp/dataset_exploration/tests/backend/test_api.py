from fastapi.testclient import TestClient
from backend.app import create_app
from backend.app import _summary
from backend.domain import ActivitySummary
import json
import numpy as np

def test_health():
    assert TestClient(create_app()).get('/api/health').json()=={'status':'ok'}

def test_invalid_dataset_path_is_reported():
    r=TestClient(create_app()).post('/api/datasets/load',json={'path':'missing-path','maxDurationSeconds':None})
    assert r.status_code==400

def test_activity_summary_is_json_serializable_with_numpy_flags():
    activity=ActivitySummary('a.fit','a.fit',None,None,0,0,np.bool_(True),np.bool_(False),())
    json.dumps(_summary(activity))
