from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pandas as pd
import pytest

from power_hr_eda.fit_reader import FitActivity
from power_hr_eda.prescriptions import classify, extract_laps, recognize_blocks


@pytest.fixture
def rules():
    return json.loads((Path(__file__).parents[1] / 'references/prescription_rules.json').read_text())


@pytest.mark.parametrize('duration,expected', [(60,293), (600,293), (3000,269), (5400,245), (6000,245)])
def test_z3_interpolation_and_clamping(rules, duration, expected):
    result = classify(270, duration, rules)
    assert result['category'] == 'Z3'
    assert result['power_target_w'] == expected


def test_overlap_is_selected_by_distance_and_retained(rules):
    result = classify(305, 1200, rules)
    assert result['category'] == 'Z4_low'
    assert set(result['candidate_categories']) == {'sweet_spot', 'Z4_low'}
    assert 'overlapping_categories' in result['flags']
    assert result['power_target_w'] == pytest.approx(304.667, abs=.001)


def test_no_invented_numeric_maximal_target_or_z4_duration(rules):
    assert classify(600, 10, rules)['power_target_w'] is None
    assert classify(310, 900, rules)['base_zone'] == 'Z4'
    assert classify(310, 900, rules)['power_target_w'] is None
    assert classify(None, 900, rules)['power_target_w'] is None


def test_decimal_zone_boundaries_use_nearest_integer_watt(rules):
    assert classify(244.4, 1800, rules)['base_zone'] == 'Z2'
    assert classify(244.6, 1800, rules)['base_zone'] == 'Z3'


def activity(laps, values):
    origin = datetime(2025,1,1,tzinfo=timezone.utc)
    records = pd.DataFrame({'timestamp':[origin+timedelta(seconds=i) for i in range(len(values))],
                            'power':values})
    messages = {'lap':[{'start_time':origin+timedelta(seconds=start),
                        'timestamp':origin+timedelta(seconds=end),
                        'total_timer_time':end-start+1,'total_elapsed_time':end-start+1,
                        'avg_power':111,'lap_trigger':'manual'} for start,end in laps]}
    return FitActivity(Path('test.fit'),records,messages,{'lap':len(laps)})


def test_mean_uses_actual_lap_samples_zeros_and_missing_are_explicit(rules):
    a=activity([(0,2),(3,5)], [300,300,300,0,None,150])
    rows, assignment = extract_laps(a, rules)
    assert [r['mean_power_w'] for r in rows] == [300,75]
    assert rows[1]['missing_power_samples'] == 1
    assert rows[0]['fit_avg_power_w'] == 111
    assert assignment.tolist() == [1,1,1,2,2,2]
    assert a.records.power.tolist()[0] == 300


def test_boundary_ties_go_to_later_lap_gaps_are_not_filled(rules):
    a=activity([(0,2),(2,3),(5,6)], [100]*7)
    rows, assignment = extract_laps(a,rules)
    assert assignment.tolist() == [1,1,2,2,0,3,3]
    assert sum(r['sample_count'] for r in rows) == 6


def lap_rows(sequence, rules):
    rows=[]
    start=0
    for i,(duration,power) in enumerate(sequence,1):
        rows.append({'lap_index':i,'duration_s':duration,'mean_power_w':power,
                     'start_elapsed_s':start,'end_elapsed_s':start+duration-1,
                     **classify(power,duration,rules)})
        start+=duration
    return rows


def test_irregular_30_15_and_multiple_blocks_share_targets(rules):
    sequence=[(600,210),(30,365),(20,130),(30,370),(17,135),(29,360),(15,125),
              (300,180),(31,368),(16,130),(30,366),(15,128),(30,364),(16,132),(600,210)]
    rows=lap_rows(sequence,rules)
    before=deepcopy(rows)
    blocks=recognize_blocks(rows,rules)
    assert len(blocks)==2
    assert {b['protocol'] for b in blocks} == {'30_15_candidate'}
    assert len({b['family_id'] for b in blocks})==1
    on=[r for r in rows if r.get('phase_role')=='on']
    off=[r for r in rows if r.get('phase_role')=='off']
    assert len(on)==len(off)==6
    assert len({r['power_target_w'] for r in on})==1
    assert {r['ideal_duration_s'] for r in on}=={30}
    assert {r['ideal_duration_s'] for r in off}=={15}
    assert [r['duration_s'] for r in rows]==[r['duration_s'] for r in before]


def test_progressive_efforts_are_not_flattened(rules):
    rows=lap_rows([(300,250),(120,100),(300,320),(120,100),(300,390),(120,100)],rules)
    assert recognize_blocks(rows,rules)==[]


def test_long_repeats_and_multiphase_motifs(rules):
    rows=lap_rows([(600,320),(300,120)]*3,rules)
    blocks=recognize_blocks(rows,rules)
    assert len(blocks)==1
    assert blocks[0]['protocol']=='extensive_repeats_candidate'
    rows=lap_rows([(180,350),(120,280),(15,470),(240,120)]*3,rules)
    blocks=recognize_blocks(rows,rules)
    assert len(blocks)==1
    assert blocks[0]['period_laps']==4


def test_unrelated_blocks_do_not_share_family(rules):
    rows=lap_rows([(30,360),(15,100)]*3+[(600,200)]+[(120,380),(120,130)]*3,rules)
    blocks=recognize_blocks(rows,rules)
    assert len(blocks)==2
    assert len({b['family_id'] for b in blocks})==2


@pytest.mark.parametrize('sequence', [
    [(30,470),(15,100)]*3+[(600,200)]+[(30,505),(15,100)]*3,
    [(600,240),(120,100)]*3+[(1000,100)]+[(600,250),(120,100)]*3,
])
def test_shared_targets_cannot_resolve_unmapped_laps(sequence,rules):
    rules['z1_policy']='unresolved'
    rules['z2_open_upper_policy']='unresolved'
    rows=lap_rows(sequence,rules)
    initially_unresolved=[r['lap_index'] for r in rows if r['power_target_w'] is None]
    recognize_blocks(rows,rules)
    assert all(r['power_target_w'] is None for r in rows if r['lap_index'] in initially_unresolved)


@pytest.mark.parametrize('power,duration,expected', [
    (132,15,130), (178,60,179), (0,300,0),
    (210,1800,244), (210,21600,180), (210,30000,180),
])
def test_approved_z1_and_z2_rules(rules,power,duration,expected):
    assert classify(power,duration,rules)['power_target_w']==expected


@pytest.mark.parametrize('power', [488.1, 489, 650])
def test_above_z6_is_categorical_maximal_without_invented_watts(rules,power):
    result=classify(power,30,rules)
    assert result['category']=='Z7'
    assert result['prescription_kind']=='maximal'
    assert result['power_target_w'] is None
    assert 'maximal_by_dataset_convention' in result['flags']


def test_maximal_repeats_stay_distinct_from_numeric_targets(rules):
    rows=lap_rows([(30,600),(15,100)]*3,rules)
    blocks=recognize_blocks(rows,rules)
    assert len(blocks)==1
    on=[r for r in rows if r.get('phase_role')=='on']
    assert all(r['prescription_kind']=='maximal' for r in on)
    assert all('unresolved_phase_members' not in r['flags'] for r in on)
