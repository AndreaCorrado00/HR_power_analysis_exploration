from fastapi.testclient import TestClient
from backend.app import create_app
from backend.app import _summary, _points
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

def test_series_points_convert_numpy_and_missing_values_to_json_scalars():
    import pandas as pd
    frame=pd.DataFrame({'elapsed_seconds':[np.float64(0)],'power':[np.float64(200)],'heart_rate':[np.nan]})
    encoded=json.dumps(_points(frame))
    assert encoded == '[{"elapsedSeconds": 0.0, "power": 200.0, "heartRate": null, "powerWKg": null, "hrPctMax": null, "hrPctThreshold": null}]'
