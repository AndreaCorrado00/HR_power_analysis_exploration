from __future__ import annotations
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from power_hr_eda.fit_reader import FitActivity, read_fit_activity
from .domain import ActivitySummary, LapBoundary

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
    a=read_fit_activity(target); records=a.records; start=end=None
    if 'timestamp' in records:
        ts=pd.to_datetime(records.timestamp,utc=True,errors='coerce').dropna()
        if len(ts): start,end=ts.min().to_pydatetime(),ts.max().to_pydatetime()
    laps=[]
    for i,row in enumerate(a.messages.get('lap',[]),1):
        s,e=row.get('start_time'),row.get('timestamp')
        if s is not None and e is not None and e>=s: laps.append(LapBoundary(i,s,e))
    return ActivitySummary(activity_id,str(path),start,end,(end-start).total_seconds() if start and end else 0.0,len(records),'power' in records and records.power.notna().any(),'heart_rate' in records and records.heart_rate.notna().any(),tuple(laps),a.parse_error)

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
