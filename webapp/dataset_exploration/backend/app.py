from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Any
import zipfile
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from .dataset_service import DatasetPathError, inventory_dataset, load_activity
from .dataset_service import summarize_decoded
from .source_browser import browse_source, source_path, fit_ids, read_source_fit
from .domain import SegmentSelection
from .segment_service import activity_series, extract_segment, validate_selection, SelectionError
from .normalization import NormalizationRequest, apply_normalizations, NormalizationError
from .export_service import ExportSegment, build_export_zip, write_or_return_export
from .processing_api import processing_router

class Camel(BaseModel):
    model_config=ConfigDict(alias_generator=lambda s:s.split('_')[0]+''.join(x.title() for x in s.split('_')[1:]),populate_by_name=True)
class LoadRequest(Camel):
    path:str
    max_duration_seconds:float|None=None
    folder:str=''
    selected_files:list[str]|None=None
class SegmentBody(Camel): activity_id:str; first_lap:int; last_lap:int
class NormBody(Camel):
    weight_kg:float|None=None; hr_max_bpm:float|None=None; hr_threshold_bpm:float|None=None
    normalize_power:bool=False; normalize_hr_max:bool=False; normalize_hr_threshold:bool=False
class PreviewBody(SegmentBody,NormBody): pass
class ExportBody(Camel): segments:list[SegmentBody]; normalization:NormBody=NormBody(); destination:str|None=None

class State:
    def __init__(self): self.root:str|None=None; self.summaries:dict[str,Any]={}; self.activities={}

def _summary(s):
    d={'activityId':s.activity_id,'sourcePath':s.source_path,'durationSeconds':float(s.duration_seconds),'recordCount':int(s.record_count),'hasPower':bool(s.has_power),'hasHeartRate':bool(s.has_heart_rate),'extractable':bool(s.extractable),'exclusionReason':s.exclusion_reason,'laps':[]}
    if s.start_time:
      for l in s.laps: d['laps'].append({'index':l.index,'startElapsedSeconds':(l.start_time-s.start_time).total_seconds(),'endElapsedSeconds':(l.end_time-s.start_time).total_seconds(),'durationSeconds':(l.end_time-l.start_time).total_seconds()})
    return d
def _points(frame):
    def scalar(value): return None if value is None or pd.isna(value) else float(value)
    return [{'elapsedSeconds':float(r.elapsed_seconds),'power':scalar(r.get('power')),'heartRate':scalar(r.get('heart_rate')),'powerWKg':scalar(r.get('power_w_kg')),'hrPctMax':scalar(r.get('hr_pct_max')),'hrPctThreshold':scalar(r.get('hr_pct_threshold'))} for _,r in frame.iterrows()]
def _norm(n): return NormalizationRequest(n.weight_kg,n.hr_max_bpm,n.hr_threshold_bpm,n.normalize_power,n.normalize_hr_max,n.normalize_hr_threshold)

def create_app()->FastAPI:
    app=FastAPI(title='Dataset Exploration'); state=State()
    app.include_router(processing_router())
    @app.get('/api/health')
    def health(): return {'status':'ok'}
    @app.get('/api/datasets/browse')
    def browse(path:str='', folder:str=''):
      try: return browse_source(path, folder)
      except (DatasetPathError,OSError,zipfile.BadZipFile) as e: raise HTTPException(400,str(e))
    @app.post('/api/datasets/load')
    def load(req:LoadRequest):
      try:
        root=source_path(req.path)
        if not root.is_dir() and root.suffix.lower()!='.zip': raise DatasetPathError('Selezionare una cartella o un archivio ZIP')
        ids=fit_ids(root,req.folder,req.selected_files)
        if not ids: raise DatasetPathError('Nessun FIT selezionato nella cartella')
        activities={i:read_source_fit(root,i) for i in ids}
      except (DatasetPathError,OSError,zipfile.BadZipFile) as e: raise HTTPException(400,str(e))
      summaries={i:summarize_decoded(a,i,str(a.path)) for i,a in activities.items()}
      state.root=str(root); state.summaries=summaries; state.activities=activities
      acts=[a for a in summaries.values() if req.max_duration_seconds is None or a.duration_seconds<=req.max_duration_seconds]
      return {'datasetPath':str(root),'extractable':[_summary(a) for a in acts if a.extractable],'excluded':[_summary(a) for a in acts if not a.extractable]}
    def get(activity_id):
      if not state.root or activity_id not in state.summaries: raise HTTPException(404,'Attività non trovata')
      a=state.activities[activity_id]
      if a.parse_error: raise HTTPException(422,a.parse_error)
      return a,state.summaries[activity_id]
    @app.get('/api/activities/{activity_id:path}/series')
    def series(activity_id:str):
      a,_=get(activity_id); return {'points':_points(activity_series(a.records))}
    @app.post('/api/segments/preview')
    def preview(req:PreviewBody):
      try:
        a,s=get(req.activity_id); laps=validate_selection(s,SegmentSelection(req.activity_id,req.first_lap,req.last_lap)); frame=apply_normalizations(extract_segment(a.records,laps),_norm(req)); return {'points':_points(frame)}
      except (SelectionError,NormalizationError) as e: raise HTTPException(422,str(e))
    @app.post('/api/exports')
    def export(req:ExportBody):
      if not state.root: raise HTTPException(400,'Caricare prima un dataset')
      norm=_norm(req.normalization); segments=[]
      try:
       for q in req.segments:
        a,s=get(q.activity_id); laps=validate_selection(s,SegmentSelection(q.activity_id,q.first_lap,q.last_lap)); f=apply_normalizations(extract_segment(a.records,laps),norm); segments.append(ExportSegment(q.activity_id,s.source_path,q.first_lap,q.last_lap,f,norm))
       blob=build_export_zip(state.root,tuple(segments)); result=write_or_return_export(blob,req.destination)
      except (SelectionError,NormalizationError) as e: raise HTTPException(422,str(e))
      if result.written_path: return {'writtenPath':result.written_path}
      return Response(result.download_bytes,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="dataset_segments.zip"'})
    dist=Path(__file__).parents[1]/'dist'
    if dist.exists():
      assets=dist/'assets'
      if assets.exists(): app.mount('/assets',StaticFiles(directory=assets),name='assets')
      @app.get('/{path:path}',include_in_schema=False)
      def spa(path:str): return FileResponse(dist/'index.html')
    return app

app=create_app()
