import pandas as pd
from .domain import ActivitySummary, LapBoundary, SegmentSelection
class SelectionError(ValueError): pass
def activity_series(records: pd.DataFrame)->pd.DataFrame:
    out=records.copy(); out['timestamp']=pd.to_datetime(out['timestamp'],utc=True,errors='coerce'); out=out.dropna(subset=['timestamp']).sort_values('timestamp')
    out['elapsed_seconds']=(out.timestamp-out.timestamp.iloc[0]).dt.total_seconds() if len(out) else pd.Series(dtype=float)
    return out.reset_index(drop=True)
def validate_selection(summary: ActivitySummary, selection: SegmentSelection)->tuple[LapBoundary,...]:
    if selection.activity_id!=summary.activity_id or selection.first_lap>selection.last_lap: raise SelectionError('Selezione lap non valida')
    by={x.index:x for x in summary.laps}; wanted=range(selection.first_lap,selection.last_lap+1)
    if any(i not in by for i in wanted): raise SelectionError('I lap devono essere contigui')
    return tuple(by[i] for i in wanted)
def extract_segment(records: pd.DataFrame,laps:tuple[LapBoundary,...])->pd.DataFrame:
    ts=pd.to_datetime(records['timestamp'],utc=True,errors='coerce'); start=pd.Timestamp(laps[0].start_time); end=pd.Timestamp(laps[-1].end_time)
    out=records.loc[ts.between(start,end,inclusive='both')].copy(); out['timestamp']=ts.loc[out.index]
    out=out.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    out['elapsed_seconds']=(out.timestamp-out.timestamp.iloc[0]).dt.total_seconds() if len(out) else pd.Series(dtype=float)
    return out
