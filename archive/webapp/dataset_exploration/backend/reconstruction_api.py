from uuid import uuid4
import math
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import Field
from .processing_api import Camel
from .processing_service import MAX_ARCHIVE, read_archive, inventory
from .loaded_source import LoadedRequest
from .lap_service import close_lap_gaps
from .reconstruction_service import propose, export_reconstruction, support, validate_part, validate_laps, combine_sources
from webapp.workspace import export_headers


class Block(Camel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    power: float = Field(ge=0)


class Constraint(Camel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    on: float = Field(gt=0)
    off: float = Field(gt=0)
    phase: Literal[0, 1] = 0
    partial_start: bool = False
    partial_end: bool = False


class Proposal(Camel):
    dataset_id: str
    source_id: str
    sensitivity: float = Field(default=50, ge=0, le=100)


class Part(Camel):
    dataset_id: str | None = None
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    blocks: list[Block] = Field(max_length=20000)
    sensitivity: float = Field(default=50, ge=0, le=100)
    automatic_blocks: list[Block] = Field(default_factory=list, max_length=20000)
    constraints: list[Constraint] = Field(default_factory=list, max_length=10000)


class Export(Camel):
    dataset_id: str | None = None
    segments: list[Part] = Field(default_factory=list, max_length=10000)
    extraction: dict | None = None


def reconstruction_router(destination=None, extract=None, from_loaded=None):
    router = APIRouter(prefix='/api/reconstruction')
    current = {}

    @router.post('/from-loaded')
    def use_loaded(req: LoadedRequest):
        if from_loaded is None:
            raise HTTPException(409, 'Caricare prima un dataset in Estrazione')
        try:
            dataset = from_loaded(req)
            summary = inventory(dataset)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        identifier = str(uuid4())
        current[identifier] = dataset
        return {'datasetId': identifier, 'segments': summary, 'sha256': dataset.sha256}

    def get(identifier):
        if identifier not in current:
            raise HTTPException(409, 'Dataset non più disponibile: reimportare lo ZIP')
        return current[identifier]

    @router.post('/import')
    async def import_zip(request: Request):
        blob = bytearray()
        async for chunk in request.stream():
            blob.extend(chunk)
            if len(blob) > MAX_ARCHIVE:
                raise HTTPException(413, 'ZIP troppo grande (massimo 256 MiB)')
        try:
            dataset = read_archive(bytes(blob))
            for entry in dataset.manifest['segments']:
                validate_laps(entry.get('laps', []))
                saved = entry.get('reconstruction')
                if saved is None and entry.get('laps') and not all(l.get('boundary_adjustment') for l in entry['laps']):
                    frame = dataset.frames[entry['csv_file']]
                    entry['laps'] = close_lap_gaps(entry['laps'], float(support(frame)[1][-1]), frame.timestamp.iloc[0])
                    validate_laps(entry['laps'])
                if saved is not None:
                    frame = dataset.frames[entry['csv_file']]
                    if not isinstance(saved, dict):
                        raise ValueError('Metadati di ricostruzione non validi')
                    if 'supportEnd' in saved or 'sourceStep' in saved:
                        end, step = float(saved.get('supportEnd', 0)), float(saved.get('sourceStep', 0))
                        if not math.isfinite(end) or not math.isfinite(step) or end <= frame.elapsed_seconds.iloc[-1] or step <= 0:
                            raise ValueError('Supporto temporale salvato non valido')
                        frame.attrs.update(reconstruction_end=end, reconstruction_step=step)
                    state = Part.model_validate({**saved, 'sourceId': entry['csv_file'],
                                                 'start': 0, 'end': float(support(frame)[1][-1])})
                    validate_part(frame, state)
            summary = inventory(dataset)
        except (ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        identifier = str(uuid4())
        current[identifier] = dataset
        return {'datasetId': identifier, 'segments': summary, 'sha256': dataset.sha256}

    @router.post('/propose')
    def proposal(req: Proposal):
        dataset = get(req.dataset_id)
        if req.source_id not in dataset.frames:
            raise HTTPException(422, 'Sorgente non trovata')
        entry = next(e for e in dataset.manifest['segments'] if e['csv_file'] == req.source_id)
        return propose(dataset.frames[req.source_id], req.sensitivity, entry.get('laps', []), entry.get('reconstruction'))

    @router.post('/export')
    def export(req: Export):
        sources = {part.dataset_id or req.dataset_id: get(part.dataset_id or req.dataset_id) for part in req.segments}
        parts = req.segments
        dataset = next(iter(sources.values())) if sources else None
        try:
            if len(sources)>1:
                dataset, parts = combine_sources(sources, req.segments, req.dataset_id)
            extraction = extract(req.extraction) if req.extraction and extract else None
            blob = export_reconstruction(dataset, parts, extraction)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(blob, media_type='application/zip',
                        headers=export_headers(blob, 'dataset_segments_reconstructed.zip', destination))
    return router
