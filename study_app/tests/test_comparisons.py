import numpy as np
from study_app.backend.comparisons import align_series,is_prospective


def test_alignment_preserves_gap_and_does_not_shift_hr():
    workout={'start_time':'2026-10-18T10:00:00+00:00','timer_start':None,
      'series':{'elapsed_seconds':[0,1,5],'power_w':[100,110,150],'heart_rate_bpm':[120,121,125],'timer_paused':[False]*3}}
    scenario={'target':[100]*4,'power':{'mean':[101]*4,'lower':[90]*4,'upper':[110]*4},'hr':{'mean':[119]*4,'lower':[110]*4,'upper':[130]*4}}
    out=align_series(workout,scenario)
    assert out['elapsed']==[0.,1.,2.,3.,5.]
    assert np.isnan(out['hr'][2]) and np.isnan(out['hr_chain'][-1])
    assert out['hr'][1]==121


def test_late_import_is_not_prospective():
    w={'start_time':'2026-10-18T10:00:00Z','raw_sha256':'x'}
    assert not is_prospective({'created_at':'2026-10-18T11:00:00Z'},{'created_at':'2026-10-17T10:00:00Z','raw_hashes':{}},w)
    assert not is_prospective({'created_at':'2026-10-17T11:00:00Z'},{'created_at':'2026-10-17T10:00:00Z','raw_hashes':{'a':'x'}},w)
