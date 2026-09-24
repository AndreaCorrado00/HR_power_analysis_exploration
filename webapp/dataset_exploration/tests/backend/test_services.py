from datetime import datetime, timedelta, timezone
from pathlib import Path
import io, json, zipfile
import pandas as pd
import pytest
from unittest.mock import Mock

from backend.domain import ActivitySummary, LapBoundary, SegmentSelection
from backend.dataset_service import DatasetPathError, discover_fit_files, resolve_dataset, summarize_activity
from power_hr_eda.fit_reader import FitActivity
from backend.segment_service import SelectionError, activity_series, extract_segment, validate_selection
from backend.normalization import NormalizationError, NormalizationRequest, apply_normalizations
from backend.export_service import ExportSegment, build_export_zip, write_or_return_export
from backend import run

def test_resolve_dataset_and_discover_fit():
    tmp_path=Path('webapp/dataset_exploration/tests/_tmp/discovery'); tmp_path.mkdir(parents=True,exist_ok=True)
    (tmp_path/'a.fit').write_bytes(b'x'); (tmp_path/'b.txt').write_text('x')
    assert [p.name for p in discover_fit_files(resolve_dataset(str(tmp_path)))] == ['a.fit']
    with pytest.raises(DatasetPathError): resolve_dataset(str(tmp_path/'missing'))

def test_summarize_activity_decodes_resolved_target(monkeypatch):
    root=Path('webapp/dataset_exploration/tests/_tmp/resolution'); root.mkdir(parents=True,exist_ok=True)
    logical=root/'ride.fit'; logical.write_bytes(b'not-empty'); seen=[]
    def fake_reader(path):
        seen.append(path)
        return FitActivity(path,pd.DataFrame(),{}, {},None)
    monkeypatch.setattr('backend.dataset_service.read_fit_activity',fake_reader)
    summarize_activity(logical,root)
    assert seen == [logical.resolve(strict=True)]

def test_runner_opens_the_selected_local_address(monkeypatch):
    timer=Mock(); timer_factory=Mock(return_value=timer)
    monkeypatch.setattr(run,'find_free_port',lambda host:54321)
    monkeypatch.setattr(run.threading,'Timer',timer_factory)
    monkeypatch.setattr(run.uvicorn,'run',Mock())
    run.main()
    assert timer_factory.call_args.args[0] == 1.0
    timer.start.assert_called_once_with()
    assert run.uvicorn.run.call_args.kwargs == {'host':'127.0.0.1','port':54321}

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
      csv_text=z.read(manifest['segments'][0]['csv_file']).decode()
      assert 'activity_id,first_lap,last_lap,timestamp,elapsed_seconds' in csv_text
      assert manifest['columns']['power_w']['unit']=='W'
      assert manifest['segments'][0]['start_timestamp']=='2026-01-01T00:00:00+00:00'
    fallback=write_or_return_export(blob,str(tmp_path/'missing'/'x.zip'))
    assert fallback.download_bytes==blob and fallback.written_path is None
