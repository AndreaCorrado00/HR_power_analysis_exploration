"""Read-only diagnostics at the dataset's nominal 1 Hz sampling rate.

Windows are hypothetical: no samples are cut or interpolated here.
"""
import numpy as np


def power_gaps(frame, expected_step_s=1.0):
    times=frame.elapsed_seconds.to_numpy(dtype=float)
    power=frame.power_w.to_numpy(dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError('Gap analysis requires finite, strictly increasing timestamps')
    valid=np.flatnonzero(np.isfinite(power)&(power>=0))
    gaps=[]
    if not len(valid):
        return [dict(left_index=None,right_index=None,bounded=False,
                     missing_duration_s=float(times[-1]-times[0]+expected_step_s) if len(times) else 0,
                     same_numeric_lap=False,endpoint_delta_w=None)]
    if valid[0]>0:
        gaps.append(dict(left_index=None,right_index=int(valid[0]),bounded=False,
                         missing_duration_s=float(times[valid[0]]-times[0]),
                         same_numeric_lap=False,endpoint_delta_w=None))
    for left,right in zip(valid[:-1],valid[1:]):
        missing=float(times[right]-times[left]-expected_step_s)
        if missing<=0: continue
        a=frame.iloc[left]; b=frame.iloc[right]
        same=bool(a.lap_index>0 and a.lap_index==b.lap_index and
                  a.prescription_kind==b.prescription_kind=='power' and
                  np.isfinite(a.power_target_w) and a.power_target_w==b.power_target_w)
        gaps.append(dict(left_index=int(left),right_index=int(right),bounded=True,
                         missing_duration_s=missing,same_numeric_lap=same,
                         endpoint_delta_w=float(abs(power[right]-power[left]))))
    if valid[-1]<len(times)-1:
        gaps.append(dict(left_index=int(valid[-1]),right_index=None,bounded=False,
                         missing_duration_s=float(times[-1]-times[valid[-1]]),
                         same_numeric_lap=False,endpoint_delta_w=None))
    return gaps


def dominant_window(frame,gaps,threshold_s):
    """Split at >= threshold missing seconds; rank whole observed laps first.

    A complete lap has all its exported rows inside this window. This is not
    proof of uninterrupted signal coverage or intact FIT boundary timestamps.
    """
    windows=[]; start=0
    for gap in gaps:
        if not gap['bounded'] or gap['missing_duration_s']<threshold_s: continue
        windows.append((start,gap['left_index']+1))
        start=gap['right_index']
    windows.append((start,len(frame)))
    totals=frame.loc[frame.lap_index>0,'lap_index'].value_counts()
    scored=[]
    for lo,hi in windows:
        part=frame.iloc[lo:hi]
        if part.empty: continue
        counts=part.loc[part.lap_index>0,'lap_index'].value_counts()
        complete=[int(lap) for lap,count in counts.items() if count==totals[lap]]
        power=part.power_w.to_numpy(dtype=float)
        valid=np.isfinite(power)&(power>=0)&part.prescription_kind.isin(['power','maximal']).to_numpy()
        scored.append(dict(start_elapsed_s=float(part.elapsed_seconds.iloc[0]),
                           end_elapsed_s=float(part.elapsed_seconds.iloc[-1]),
                           complete_laps=len(complete),complete_lap_indices=sorted(complete),
                           valid_prescribed_samples=int(valid.sum()),observed_samples=len(part)))
    return max(scored,key=lambda row:(row['complete_laps'],row['valid_prescribed_samples'],
                                     -row['start_elapsed_s'])) if scored else None
