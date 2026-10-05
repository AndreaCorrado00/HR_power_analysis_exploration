import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .normalization import NormalizationRequest
from .processing_service import MAX_ARCHIVE, read_archive, inventory, process, export_archive
from webapp.workspace import export_headers


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda s: s.split('_')[0] + ''.join(
        p.title() for p in s.split('_')[1:]), populate_by_name=True, allow_inf_nan=False)


class Normalization(Camel):
    weight_kg: float | None = None
    hr_max_bpm: float | None = None
    hr_threshold_bpm: float | None = None
    normalize_power: bool = False
    normalize_hr_max: bool = False
    normalize_hr_threshold: bool = False


class ProcessingRequest(Camel):
    dataset_id: str
    selected: list[str]
    window_seconds: Literal[3, 5, 10] = 3
    normalization: Normalization = Field(default_factory=Normalization)


def processing_router(destination=None) -> APIRouter:
    router = APIRouter(prefix='/api/processing')
    current = {}  # One imported dataset per local application, independent of FIT state.

    @router.post('/import')
    async def import_zip(request: Request):
        blob = bytearray()
        async for chunk in request.stream():
            blob.extend(chunk)
            if len(blob) > MAX_ARCHIVE:
                raise HTTPException(413, 'ZIP troppo grande (massimo 256 MiB)')
        try:
            dataset = read_archive(bytes(blob))
            summary = inventory(dataset)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        identifier = str(uuid4())
        current.clear(); current[identifier] = dataset
        return {'datasetId': identifier, 'segments': summary, 'sha256': dataset.sha256}

    def run(req):
        dataset = current.get(req.dataset_id)
        if dataset is None:
            raise HTTPException(409, 'Dataset non più disponibile: importare nuovamente lo ZIP')
        norm = NormalizationRequest(**req.normalization.model_dump())
        try:
            frames = process(dataset, req.selected, req.window_seconds, norm)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return dataset, norm, frames

    @router.post('/preview')
    def preview(req: ProcessingRequest):
        _, _, frames = run(req)
        return {'segments': [{'id': name, 'points': json.loads(frame.to_json(orient='records'))}
                             for name, frame in frames.items()]}

    @router.post('/export')
    def export(req: ProcessingRequest):
        dataset, norm, frames = run(req)
        blob = export_archive(dataset, frames, req.window_seconds, norm)
        return Response(blob, media_type='application/zip',
                        headers=export_headers(blob, 'dataset_segments_processed.zip', destination))

    return router
