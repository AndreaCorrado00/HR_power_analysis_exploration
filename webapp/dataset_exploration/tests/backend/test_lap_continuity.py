from pathlib import Path
from dataclasses import replace
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from power_hr_eda.fit_reader import FitActivity
from backend.app import create_app
from backend.dataset_service import summarize_decoded
from backend.segment_service import extract_segment
from backend.export_service import ExportSegment, build_export_zip
from backend.normalization import NormalizationRequest
from backend.processing_service import read_archive
from test_processing import archive
from test_reconstruction import load, proposal


def activity():
    origin = pd.Timestamp('2025-01-01', tz='UTC')
    stamp = lambda t: origin + pd.Timedelta(seconds=t)
    records = pd.DataFrame({'timestamp': [stamp(t) for t in range(21)],
                            'power': list(range(21)), 'heart_rate': 150})
    messages = {'lap': [{'start_time': stamp(0), 'timestamp': stamp(8)},
                        {'start_time': stamp(12), 'timestamp': stamp(18)}]}
    return FitActivity(Path('ride.fit'), records, messages, {}, None)


def test_loaded_laps_split_gap_at_midpoint_and_extend_last_to_activity_support():
    a = activity()
    s = summarize_decoded(a, 'ride.fit', 'ride.fit')
    origin = a.records.timestamp.iloc[0]
    assert [(lap.start_time-origin).total_seconds() for lap in s.laps] == [0, 10]
    assert [(lap.end_time-origin).total_seconds() for lap in s.laps] == [10, 21]
    left, right = [extract_segment(a.records, (lap,)) for lap in s.laps]
    assert left.power.tolist() == list(range(10))
    assert right.power.tolist() == list(range(10, 21))
    assert set(left.timestamp).isdisjoint(set(right.timestamp))
    assert a.messages['lap'][0]['timestamp'] == origin + pd.Timedelta(seconds=8)
    exported = read_archive(build_export_zip('dataset', (ExportSegment('ride.fit','ride.fit',1,2,
        extract_segment(a.records,s.laps),NormalizationRequest(),laps=s.laps),)))
    laps = exported.manifest['segments'][0]['laps']
    assert laps[0]['source_end_timestamp'] == (origin+pd.Timedelta(seconds=8)).isoformat()
    assert laps[0]['boundary_adjustment']['method'] == 'midpoint-gaps-v1'
    assert laps[0]['end'] == laps[1]['start'] == 10


def test_unsaved_archive_laps_close_gaps_and_recompute_mean_without_new_samples():
    c = TestClient(create_app())
    dataset = load(c, archive(range(21), list(range(21)), laps=[
        {'index': 1, 'start': 0, 'end': 8}, {'index': 2, 'start': 12, 'end': 18}]))
    result = proposal(c, dataset)
    assert result['blocks'] == [{'start': 0, 'end': 10, 'power': 4.5}, {'start': 10, 'end': 21, 'power': 15}]
    assert len(result['points']) == 21
    assert result['laps'][1]['boundary_adjustment']['input_end'] == 18


def test_midpoint_can_be_fractional():
    a = activity()
    a.messages['lap'][1]['start_time'] -= pd.Timedelta(seconds=1)
    s = summarize_decoded(a, 'ride.fit', 'ride.fit')
    assert (s.laps[0].end_time-a.records.timestamp.iloc[0]).total_seconds() == 9.5
    assert s.laps[0].end_time == s.laps[1].start_time


@pytest.mark.parametrize('times,boundary', [(list(range(21)),9.5), ([0,1,2,3,4,5,6,7,8,9,16,17,18,19,20],12)])
def test_selected_corrected_lap_preserves_support_through_zip_and_reconstruction(times,boundary,tmp_path,monkeypatch):
    monkeypatch.setenv('HR_POWER_EXPORTS', str(tmp_path))
    a = activity()
    a = replace(a, records=a.records.iloc[times].reset_index(drop=True))
    a.messages['lap'][1]['start_time'] = a.records.timestamp.iloc[0]+pd.Timedelta(seconds=2*boundary-8)
    summary = summarize_decoded(a, 'ride.fit', 'ride.fit')
    lap = summary.laps[0]
    blob = build_export_zip('dataset', (ExportSegment('ride.fit','ride.fit',1,1,
        extract_segment(a.records,(lap,)),NormalizationRequest(),laps=(lap,)),))
    d = read_archive(blob); entry = d.manifest['segments'][0]
    assert entry['laps'][0]['end'] == boundary
    c = TestClient(create_app()); dataset = load(c, blob)
    result = c.post('/api/reconstruction/propose',json={'datasetId':dataset,'sourceId':entry['csv_file']}).json()
    assert result['end'] == boundary
    assert result['blocks'][0]['end'] == boundary
    response = c.post('/api/reconstruction/export',json={'datasetId':dataset,'segments':[
        {'sourceId':entry['csv_file'],'start':2,'end':boundary,'blocks':result['blocks']}]})
    assert response.status_code == 200, response.text
    reopened = load(c,response.content)
    again = c.post('/api/reconstruction/propose',json={'datasetId':reopened,'sourceId':'reconstructed/segment_0001.csv'}).json()
    assert again['end'] == boundary-2
