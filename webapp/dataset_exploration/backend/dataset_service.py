from __future__ import annotations
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from power_hr_eda.fit_reader import FitActivity, read_fit_activity
from .domain import ActivitySummary, LapBoundary
from .lap_service import close_lap_gaps

class DatasetPathError(ValueError): pass

@dataclass(frozen=True)
class DatasetInventory:
    dataset_path: str
    activities: tuple[ActivitySummary,...]

def resolve_dataset(path_text: str) -> Path:
    p=Path(path_text).expanduser()
    if not p.exists(): raise DatasetPathError('Il percorso del dataset non esiste')
    p=p.resolve(strict=True)
    if not p.is_dir(): raise DatasetPathError('Il percorso del dataset non è una directory')
    return p

def discover_fit_files(root: Path)->tuple[Path,...]: return tuple(sorted(p for p in root.rglob('*.fit') if p.is_file()))

def summarize_activity(path: Path, root: Path)->ActivitySummary:
    activity_id=path.relative_to(root).as_posix()
    try: target=path.resolve(strict=True)
    except OSError as exc:
        return ActivitySummary(activity_id,str(path),None,None,0.0,0,False,False,(),f'Link non risolvibile: {exc}')
    if target.stat().st_size==0:
        return ActivitySummary(activity_id,str(path),None,None,0.0,0,False,False,(),'File FIT vuoto')
    return summarize_decoded(read_fit_activity(target), activity_id, str(path))

def summarize_decoded(a: FitActivity, activity_id: str, source_path: str)->ActivitySummary:
    records=a.records; start=end=None
    if 'timestamp' in records:
        ts=pd.to_datetime(records.timestamp,utc=True,errors='coerce').dropna()
        if len(ts): start,end=ts.min().to_pydatetime(),ts.max().to_pydatetime()
    laps=[]
    for i,row in enumerate(a.messages.get('lap',[]),1):
        s,e=row.get('start_time'),row.get('timestamp')
        if s is not None and e is not None and e>=s: laps.append(LapBoundary(i,s,e))
    if laps and start is not None:
        ordered=sorted(laps,key=lambda lap:lap.start_time)
        stamps=ts.drop_duplicates().sort_values()
        step=float(stamps.diff().dt.total_seconds().dropna().median()) if len(stamps)>1 else 1.
        values=[{'index':l.index,'start':(l.start_time-start).total_seconds(),
                 'end':(l.end_time-start).total_seconds()} for l in ordered]
        # Preserve the previous overlap convention; positive holes are split equally.
        for left,right in zip(values,values[1:]):
            if left['end']>right['start']: left['end']=right['start']
        corrected=close_lap_gaps(values,(end-start).total_seconds()+step,start)
        laps=[LapBoundary(l.index,start+pd.Timedelta(seconds=v['start']),start+pd.Timedelta(seconds=v['end']),
                          l.start_time,l.end_time,True,v['boundary_adjustment'],step)
              for l,v in zip(ordered,corrected) if v['end']>v['start']]
    return ActivitySummary(activity_id,source_path,start,end,(end-start).total_seconds() if start and end else 0.0,len(records),'power' in records and records.power.notna().any(),'heart_rate' in records and records.heart_rate.notna().any(),tuple(laps),a.parse_error)

def inventory_dataset(path_text: str)->DatasetInventory:
    root=resolve_dataset(path_text)
    files=discover_fit_files(root)
    with ThreadPoolExecutor(max_workers=min(4,max(1,len(files)))) as pool:
        activities=tuple(pool.map(lambda p:summarize_activity(p,root),files))
    return DatasetInventory(str(root),activities)

def load_activity(root: str, activity_id: str)->FitActivity:
    base=Path(root).resolve(strict=True); path=(base/Path(activity_id)).resolve(strict=True)
    if base not in path.parents: raise DatasetPathError('Attività fuori dal dataset')
    return read_fit_activity(path)
