from dataclasses import dataclass
from pathlib import Path
import io,json,zipfile
import pandas as pd
from .normalization import NormalizationRequest
@dataclass(frozen=True)
class ExportSegment:
    activity_id:str; source_path:str; first_lap:int; last_lap:int; frame:pd.DataFrame; normalization:NormalizationRequest
    csv_name:str|None=None
    laps:tuple=()
@dataclass(frozen=True)
class ExportResult:
    written_path:str|None; download_bytes:bytes|None
def build_export_zip(dataset_path:str,segments:tuple[ExportSegment,...])->bytes:
    bio=io.BytesIO(); entries=[]; norms=None
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
      for s in segments:
        name=s.csv_name or f"{Path(s.activity_id).stem}__laps_{s.first_lap:03d}-{s.last_lap:03d}.csv"
        f=s.frame.rename(columns={'power':'power_w','heart_rate':'heart_rate_bpm'})
        f.insert(0,'last_lap',s.last_lap); f.insert(0,'first_lap',s.first_lap); f.insert(0,'activity_id',s.activity_id)
        cols=[c for c in ['activity_id','first_lap','last_lap','timestamp','elapsed_seconds','power_w','heart_rate_bpm','power_w_kg','hr_pct_max','hr_pct_threshold'] if c in f]
        z.writestr(name,f[cols].to_csv(index=False)); entries.append({'activity_id':s.activity_id,'source_path':s.source_path,'first_lap':s.first_lap,'last_lap':s.last_lap,'csv_file':name})
        if len(f):
            entries[-1].update({'start_timestamp':pd.Timestamp(f.timestamp.iloc[0]).isoformat(),'end_timestamp':pd.Timestamp(f.timestamp.iloc[-1]).isoformat()})
            entries[-1]['laps']=lap_metadata(s.frame,s.laps)
            if s.laps and s.laps[-1].end_exclusive:
                entries[-1].update(sample_support_end=(pd.Timestamp(s.laps[-1].end_time)-pd.Timestamp(f.timestamp.iloc[0])).total_seconds(),
                                   sample_step=s.laps[-1].source_step_seconds)
        r=s.normalization; norms={'weight_kg':r.weight_kg,'hr_max_bpm':r.hr_max_bpm,'hr_threshold_bpm':r.hr_threshold_bpm,'active':{'power_w_kg':r.normalize_power,'hr_pct_max':r.normalize_hr_max,'hr_pct_threshold':r.normalize_hr_threshold},'formulas':{'power_w_kg':'power_w / weight_kg','hr_pct_max':'100 * heart_rate_bpm / hr_max_bpm','hr_pct_threshold':'100 * heart_rate_bpm / hr_threshold_bpm'}}
      for entry in entries: entry['origin_page']='extraction'
      manifest={'format_version':1,'dataset_path':dataset_path,'boundary_convention':'[start,end) for corrected laps; legacy selections inclusive; duplicate timestamps removed','columns':{'activity_id':{'unit':None},'first_lap':{'unit':None},'last_lap':{'unit':None},'timestamp':{'unit':'ISO 8601 UTC'},'elapsed_seconds':{'unit':'s'},'power_w':{'unit':'W'},'heart_rate_bpm':{'unit':'bpm'},'power_w_kg':{'unit':'W/kg'},'hr_pct_max':{'unit':'%'},'hr_pct_threshold':{'unit':'%'}},'normalization':norms or {},'segments':entries}
      z.writestr('manifest.json',json.dumps(manifest,indent=2,default=str))
    return bio.getvalue()

def lap_metadata(frame,laps):
    """Local half-open boundaries plus unchanged FIT references."""
    from .processing_service import time_blocks
    times,step,_=time_blocks(frame)
    origin=pd.Timestamp(frame.timestamp.iloc[0])
    limit=float(times[-1]+step)
    result=[]
    ordered=sorted(laps,key=lambda lap:lap.start_time)
    if ordered and ordered[-1].end_exclusive:
        limit=(pd.Timestamp(ordered[-1].end_time)-origin).total_seconds()
    for i,lap in enumerate(ordered):
        raw_start=(pd.Timestamp(lap.start_time)-origin).total_seconds()
        raw_end=(pd.Timestamp(lap.end_time)-origin).total_seconds()
        end=raw_end
        # Include the final recorded endpoint only in the last selected lap.
        if not lap.end_exclusive and i==len(ordered)-1 and raw_end>=times[-1]: end=max(end,limit)
        if i+1<len(ordered): end=min(end,(pd.Timestamp(ordered[i+1].start_time)-origin).total_seconds())
        start,end=max(0.,raw_start),min(limit,end)
        if end<=start: continue
        result.append({'index':lap.index,'start':start,'end':end,
            'source_start_timestamp':pd.Timestamp(lap.source_start_time or lap.start_time).isoformat(),
            'source_end_timestamp':pd.Timestamp(lap.source_end_time or lap.end_time).isoformat(),
            'partialStart':raw_start<0,'partialEnd':raw_end>end})
        if lap.boundary_adjustment: result[-1]['boundary_adjustment']=lap.boundary_adjustment
    return result
def write_or_return_export(blob:bytes,destination:str|None)->ExportResult:
    if destination:
      try:
        p=Path(destination); p.write_bytes(blob); return ExportResult(str(p.resolve()),None)
      except OSError: pass
    return ExportResult(None,blob)
