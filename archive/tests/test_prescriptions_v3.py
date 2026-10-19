from copy import deepcopy
import json
from pathlib import Path

import pytest

from power_hr_eda.prescriptions import classify, recognize_blocks
from test_prescriptions import lap_rows


@pytest.fixture
def rules3():
    rules=json.loads((Path(__file__).parents[1]/'references/prescription_rules.json').read_text())
    rules.update(version='prescription-inference-v3',power_model='rounded_observed_mean',target_rounding_w=5)
    rules['patterns'].update(power_match_mode='relative_to_shared_target',power_tolerance_fraction=.05,
                             power_tolerance_floor_w=0)
    return rules


@pytest.mark.parametrize('power,duration,expected',[(210,30,210),(399,30,400),(270,6000,270),(310,900,310),(178,15,180)])
def test_v3_target_is_rounded_mean_not_duration_curve(rules3,power,duration,expected):
    assert classify(power,duration,rules3)['power_target_w']==expected


def test_v3_duration_does_not_choose_overlap_category(rules3):
    short=classify(300,30,rules3); long=classify(300,3600,rules3)
    assert short['category']==long['category']
    assert short['power_target_w']==long['power_target_w']==300


def test_nearby_cross_zone_efforts_can_share_target(rules3):
    rows=lap_rows([(30,389),(15,100),(30,393),(15,100),(30,391),(15,100)],rules3)
    blocks=recognize_blocks(rows,rules3)
    assert len(blocks)==1
    assert {r['power_target_w'] for r in rows if r['phase_role']=='on'}=={390}


def test_five_percent_is_checked_on_every_family_member(rules3):
    seq=[(30,380),(15,100)]*3+[(300,200)]+[(30,420),(15,100)]*3
    rows=lap_rows(seq,rules3)
    blocks=recognize_blocks(rows,rules3)
    assert len(blocks)==2
    assert len({b['family_id'] for b in blocks})==1
    for row in rows:
        if row.get('family_id') and row['prescription_kind']=='power':
            assert abs(row['mean_power_w']-row['power_target_w'])<=.05*row['power_target_w']+1e-9


def test_blocks_farther_than_five_percent_are_not_forced_together(rules3):
    rows=lap_rows([(30,365),(15,100)]*3+[(300,200)]+[(30,410),(15,100)]*3,rules3)
    blocks=recognize_blocks(rows,rules3)
    assert len(blocks)==2
    assert len({b['family_id'] for b in blocks})==2
    assert {b['phases'][0]['power_target_w'] for b in blocks}=={365,410}


def test_maximal_remains_categorical(rules3):
    result=classify(600,20,rules3)
    assert result['prescription_kind']=='maximal'
    assert result['power_target_w'] is None


def test_candidate_may_be_valid_when_full_median_stabilizes(rules3):
    rows=lap_rows([(30,380),(15,100),(30,420),(15,100)]*2,rules3)
    blocks=recognize_blocks(rows,rules3)
    assert len(blocks)==1
    assert blocks[0]['complete_repetitions']==4
    assert blocks[0]['phases'][0]['power_target_w']==400
