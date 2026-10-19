import numpy as np
import pandas as pd
import pytest

from power_hr_eda.prescription_segments import annotate_segments


def frame(time,power,hr):
    return pd.DataFrame(dict(elapsed_seconds=time,power_w=power,heart_rate_bpm=hr,
                            lap_index=[1]*len(time),prescription_kind=['power']*len(time)))


def test_missing_samples_split_without_filling_and_keep_zero():
    original=frame([0,1,2,3,5],[100,0,np.nan,100,100],[100]*5)
    out=annotate_segments(original,[])
    assert out.power_segment_id.tolist()==[1,1,0,2,3]
    assert out.hr_segment_id.tolist()==[1,1,1,1,2]
    assert out.dynamics_segment_id.tolist()==[1,1,0,2,3]
    pd.testing.assert_frame_equal(out[original.columns],original)


def test_hr_missing_splits_only_hr_and_joint_dynamics():
    out=annotate_segments(frame([0,1,2],[100]*3,[100,np.nan,99]),[])
    assert out.power_segment_id.tolist()==[1,1,1]
    assert out.hr_segment_id.tolist()==[1,0,2]
    assert out.dynamics_segment_id.tolist()==[1,0,2]


def test_timer_pause_between_adjacent_samples_is_a_boundary():
    out=annotate_segments(frame([0,1,2],[0,0,100],[100]*3),[(1,2)])
    assert out.power_segment_id.tolist()==[1,2,3]
    assert out.timer_paused.tolist()==[False,True,False]


def test_pause_state_never_changes_within_a_segment():
    out=annotate_segments(frame([0,1,2,3,4],[0]*5,[100]*5),[(1,4)])
    assert out.power_segment_id.tolist()==[1,2,2,2,3]
    assert out.groupby('power_segment_id').timer_paused.nunique().max()==1


def test_nonincreasing_timestamps_are_rejected():
    with pytest.raises(ValueError):annotate_segments(frame([0,0],[1,2],[90,90]),[])
