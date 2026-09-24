from dataclasses import dataclass
from pathlib import Path
import io,json,zipfile
import pandas as pd
from .normalization import NormalizationRequest
@dataclass(frozen=True)
class ExportSegment:
    activity_id:str; source_path:str; first_lap:int; last_lap:int; frame:pd.DataFrame; normalization:NormalizationRequest
@dataclass(frozen=True)
class ExportResult:
    written_path:str|None; download_bytes:bytes|None
def build_export_zip(dataset_path:str,segments:tuple[ExportSegment,...])->bytes:
    bio=io.BytesIO(); entries=[]; norms=None
    with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
      for s in segments:
        name=f"{Path(s.activity_id).stem}__laps_{s.first_lap:03d}-{s.last_lap:03d}.csv"
        f=s.frame.rename(columns={'power':'power_w','heart_rate':'heart_rate_bpm'})
        f.insert(0,'last_lap',s.last_lap); f.insert(0,'first_lap',s.first_lap); f.insert(0,'activity_id',s.activity_id)
        cols=[c for c in ['activity_id','first_lap','last_lap','timestamp','elapsed_seconds','power_w','heart_rate_bpm','power_w_kg','hr_pct_max','hr_pct_threshold'] if c in f]
        z.writestr(name,f[cols].to_csv(index=False)); entries.append({'activity_id':s.activity_id,'source_path':s.source_path,'first_lap':s.first_lap,'last_lap':s.last_lap,'csv_file':name})
        if len(f): entries[-1].update({'start_timestamp':pd.Timestamp(f.timestamp.iloc[0]).isoformat(),'end_timestamp':pd.Timestamp(f.timestamp.iloc[-1]).isoformat()})
        r=s.normalization; norms={'weight_kg':r.weight_kg,'hr_max_bpm':r.hr_max_bpm,'hr_threshold_bpm':r.hr_threshold_bpm,'active':{'power_w_kg':r.normalize_power,'hr_pct_max':r.normalize_hr_max,'hr_pct_threshold':r.normalize_hr_threshold},'formulas':{'power_w_kg':'power_w / weight_kg','hr_pct_max':'100 * heart_rate_bpm / hr_max_bpm','hr_pct_threshold':'100 * heart_rate_bpm / hr_threshold_bpm'}}
      manifest={'format_version':1,'dataset_path':dataset_path,'boundary_convention':'inclusive outer bounds; duplicate timestamps removed','columns':{'activity_id':{'unit':None},'first_lap':{'unit':None},'last_lap':{'unit':None},'timestamp':{'unit':'ISO 8601 UTC'},'elapsed_seconds':{'unit':'s'},'power_w':{'unit':'W'},'heart_rate_bpm':{'unit':'bpm'},'power_w_kg':{'unit':'W/kg'},'hr_pct_max':{'unit':'%'},'hr_pct_threshold':{'unit':'%'}},'normalization':norms or {},'segments':entries}
      z.writestr('manifest.json',json.dumps(manifest,indent=2,default=str))
    return bio.getvalue()
def write_or_return_export(blob:bytes,destination:str|None)->ExportResult:
    if destination:
      try:
        p=Path(destination); p.write_bytes(blob); return ExportResult(str(p.resolve()),None)
      except OSError: pass
    return ExportResult(None,blob)
