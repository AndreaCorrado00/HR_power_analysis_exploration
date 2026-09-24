from datetime import datetime, timedelta, timezone
from pathlib import Path
import io, json, zipfile
import pandas as pd
import pytest

from backend.domain import ActivitySummary, LapBoundary, SegmentSelection
from backend.dataset_service import DatasetPathError, discover_fit_files, resolve_dataset
from backend.segment_service import SelectionError, activity_series, extract_segment, validate_selection
from backend.normalization import NormalizationError, NormalizationRequest, apply_normalizations
from backend.export_service import ExportSegment, build_export_zip, write_or_return_export

def test_resolve_dataset_and_discover_fit():
    tmp_path=Path('webapp/dataset_exploration/tests/_tmp/discovery'); tmp_path.mkdir(parents=True,exist_ok=True)
    (tmp_path/'a.fit').write_bytes(b'x'); (tmp_path/'b.txt').write_text('x')
    assert [p.name for p in discover_fit_files(resolve_dataset(str(tmp_path)))] == ['a.fit']
    with pytest.raises(DatasetPathError): resolve_dataset(str(tmp_path/'missing'))

def _summary():
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    return ActivitySummary('ride.fit','ride.fit',t,t+timedelta(seconds=20),20,3,True,True,
      (LapBoundary(1,t,t+timedelta(seconds=10)),LapBoundary(2,t+timedelta(seconds=10),t+timedelta(seconds=20))))

def test_series_and_contiguous_segment_have_zero_time_and_unique_boundary():
    t=pd.Timestamp('2026-01-01T00:00:00Z'); records=pd.DataFrame({'timestamp':[t,t+pd.Timedelta(seconds=10),t+pd.Timedelta(seconds=20)],'power':[1,2,3],'heart_rate':[100,110,120]})
    assert activity_series(records).elapsed_seconds.tolist()==[0,10,20]
    laps=validate_selection(_summary(),SegmentSelection('ride.fit',1,2))
    result=extract_segment(records,laps)
    assert result.timestamp.is_unique and result.elapsed_seconds.tolist()==[0,10,20]
    with pytest.raises(SelectionError): validate_selection(_summary(),SegmentSelection('ride.fit',1,3))

@pytest.mark.parametrize('bad',[None,'',0,-1,float('nan'),float('inf')])
def test_active_normalization_rejects_invalid_values(bad):
    with pytest.raises(NormalizationError): apply_normalizations(pd.DataFrame({'power':[200]}),NormalizationRequest(weight_kg=bad,normalize_power=True))

def test_normalization_preserves_originals_and_export_is_reconstructible():
    tmp_path=Path('webapp/dataset_exploration/tests/_tmp/export'); tmp_path.mkdir(parents=True,exist_ok=True)
    frame=pd.DataFrame({'timestamp':[pd.Timestamp('2026-01-01T00:00:00Z')],'elapsed_seconds':[0.0],'power':[210.0],'heart_rate':[150.0]})
    norm=NormalizationRequest(70,190,170,True,True,True); result=apply_normalizations(frame,norm)
    assert frame.columns.tolist()==['timestamp','elapsed_seconds','power','heart_rate']
    assert result.power_w_kg.iloc[0]==3
    seg=ExportSegment('ride.fit','ride.fit',1,1,result,norm)
    blob=build_export_zip('dataset/cleaned',(seg,))
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
      assert not any(n.endswith('.fit') for n in z.namelist())
      manifest=json.loads(z.read('manifest.json')); assert manifest['normalization']['weight_kg']==70
      assert 'elapsed_seconds' in z.read(manifest['segments'][0]['csv_file']).decode()
    fallback=write_or_return_export(blob,str(tmp_path/'missing'/'x.zip'))
    assert fallback.download_bytes==blob and fallback.written_path is None
