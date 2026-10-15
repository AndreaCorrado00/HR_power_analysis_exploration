import pandas as pd

from power_hr_eda.prescription_gaps import power_gaps, dominant_window


def frame(times, power, laps=None, kinds=None):
    return pd.DataFrame(dict(elapsed_seconds=times,power_w=power,
                            lap_index=laps or [1]*len(times),
                            prescription_kind=kinds or ['power']*len(times),
                            power_target_w=[100]*len(times)))


def test_nan_and_absent_records_are_counted_once():
    gaps=power_gaps(frame([0,1,2,63,64],[100,float('nan'),100,110,110]))
    assert [g['missing_duration_s'] for g in gaps]==[1,60]
    assert all(g['same_numeric_lap'] for g in gaps)


def test_transition_and_maximal_are_not_interpolation_candidates():
    assert not power_gaps(frame([0,20],[100,200],[1,2]))[0]['same_numeric_lap']
    assert not power_gaps(frame([0,20],[600,620],kinds=['maximal']*2))[0]['same_numeric_lap']


def test_unbounded_missing_is_reported():
    gaps=power_gaps(frame([0,1,2,3],[float('nan'),100,100,float('nan')]))
    assert len(gaps)==2
    assert all(not g['bounded'] for g in gaps)


def test_most_complete_laps_precedes_longest_window():
    data=frame([0,1,2,100,101,102,103],[100]*7,[1,2,2,3,3,3,3])
    result=dominant_window(data,power_gaps(data),60)
    assert result['start_elapsed_s']==0
    assert result['complete_laps']==2
    assert result['valid_prescribed_samples']==3
