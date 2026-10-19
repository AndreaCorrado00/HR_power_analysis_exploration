"""Transfer the current decoded FIT selection through the existing segment contract."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .domain import SegmentSelection
from .export_service import ExportSegment, build_export_zip
from .normalization import NormalizationRequest
from .processing_service import read_archive
from .segment_service import activity_series, extract_segment, validate_selection


class LoadedSelection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    activity_id: str = Field(alias='activityId', min_length=1)
    first_lap: int | None = Field(default=None, alias='firstLap', ge=1)
    last_lap: int | None = Field(default=None, alias='lastLap', ge=1)

    @model_validator(mode='after')
    def valid_laps(self):
        if (self.first_lap is None) != (self.last_lap is None):
            raise ValueError('Indicare entrambi i confini lap oppure nessuno per l’attività completa')
        return self


class LoadedRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    dataset_id: str = Field(alias='datasetId', min_length=1)
    segments: list[LoadedSelection] = Field(min_length=1, max_length=10000)


def snapshot_loaded(root, request, get_activity):
    exports, metadata, seen = [], [], set()
    for i, selection in enumerate(request.segments):
        key = (selection.activity_id, selection.first_lap, selection.last_lap)
        if key in seen:
            raise ValueError('Selezione duplicata')
        seen.add(key)
        activity, summary = get_activity(selection.activity_id)
        if 'timestamp' not in activity.records:
            raise ValueError('La sorgente non contiene timestamp')
        full = selection.first_lap is None
        if full:
            frame = activity_series(activity.records)
            invalid = len(activity.records)-len(frame)
            duplicates = int(frame.timestamp.duplicated().sum())
            frame = frame.drop_duplicates('timestamp').reset_index(drop=True)
        else:
            laps = validate_selection(summary, SegmentSelection(*key))
            frame = extract_segment(activity.records, laps)
            invalid = duplicates = None
        if frame.empty:
            raise ValueError('La selezione non contiene campioni con timestamp valido')
        for column in ('power', 'heart_rate'):
            if column not in frame:
                frame[column] = None
        # Unique archive names also handle equal FIT basenames in different folders.
        exports.append(ExportSegment(selection.activity_id, summary.source_path,
            selection.first_lap or 0, selection.last_lap or 0, frame,
            NormalizationRequest(), f'loaded_{i+1:04d}.csv', summary.laps if full else laps))
        metadata.append({'selection_kind': 'whole_activity' if full else 'lap_segment',
            'invalid_timestamp_count': invalid, 'duplicate_timestamp_count': duplicates})
    # Reuse precisely the ZIP serializer/parser in memory, without disk writes or browser transfer.
    dataset = read_archive(build_export_zip(root, tuple(exports)))
    for entry, detail in zip(dataset.manifest['segments'], metadata):
        entry.update(detail)
    dataset.manifest['loaded_source'] = {'dataset_id': request.dataset_id,
        'kind': 'decoded_fit_snapshot', 'source_path': root,
        'sha256_scope': 'in-memory segment archive before adding loaded_source metadata',
        'whole_activity_lap_convention': 'first_lap=last_lap=0 means no lap selection'}
    return dataset
