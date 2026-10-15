"""Editable offline power hypotheses; never coach ground truth."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
import zipfile
import hashlib
import numpy as np
import pandas as pd
from .normalization import NormalizationRequest
from .processing_service import smooth, time_blocks, SegmentDataset


def combine_sources(sources, parts, default_id=None):
    """Namespace in-memory source references; preserve each source manifest and hash."""
    frames, entries, renamed = {}, [], []
    for part in parts:
        identifier = part.dataset_id or default_id
        source = sources[identifier]
        if part.source_id not in source.frames:
            raise ValueError('Segmento sorgente sconosciuto')
        name = f'{identifier}/{part.source_id}'
        if name not in frames:
            frames[name] = source.frames[part.source_id]
            entry = deepcopy(next(e for e in source.manifest['segments'] if e['csv_file']==part.source_id))
            entry.update(csv_file=name, source_dataset_id=identifier, source_csv_file=part.source_id)
            entries.append(entry)
        renamed.append(part.model_copy(update={'source_id':name}))
    descriptors = [{'dataset_id':key,'sha256':value.sha256,'manifest':value.manifest} for key,value in sources.items()]
    digest = hashlib.sha256(json.dumps(descriptors,sort_keys=True).encode()).hexdigest()
    manifest = {'format_version':2,'segments':entries,'source_datasets':descriptors,
                'sha256_scope':'JSON source dataset descriptors; individual archive hashes in source_datasets'}
    return SegmentDataset(manifest,frames,digest), renamed


def support(frame):
    times, step, runs = time_blocks(frame, frame.attrs.get('reconstruction_step'))
    ends = np.r_[times[1:], times[-1] + step]
    for start, end in runs:
        ends[end-1] = times[end-1] + step
    if 'reconstruction_end' in frame.attrs:
        ends[-1] = frame.attrs['reconstruction_end']
    return times, ends, step, runs


def validate_laps(laps):
    if not isinstance(laps, list):
        raise ValueError('Metadati lap non validi')
    previous = 0.
    for lap in laps:
        if not isinstance(lap, dict):
            raise ValueError('Metadati lap non validi')
        start, end = float(lap.get('start', -1)), float(lap.get('end', -1))
        if not np.isfinite(start) or not np.isfinite(end) or start < previous or end <= start:
            raise ValueError('Confini lap non validi o sovrapposti')
        previous = end


def propose(frame, sensitivity=50, laps=None, saved=None):
    times, ends, step, runs = support(frame)
    filtered = smooth(frame, 5, NormalizationRequest(), step)
    raw = frame.power_w.to_numpy(dtype=float)
    valid = np.isfinite(raw) & (raw >= 0)
    blocks, details = [], []
    validate_laps(laps or [])
    for lap in laps or []:
        start, end = max(0., float(lap['start'])), min(float(ends[-1]), float(lap['end']))
        if end <= start:
            continue
        left, right = np.searchsorted(times, [start, end])
        values = raw[left:right][valid[left:right]]
        details.append({**lap, 'validSamples': int(len(values)),
                        'invalidSamples': int(right-left-len(values))})
        if len(values) and saved is None:
            blocks.append({'start': start, 'end': end, 'power': round(float(values.mean()), 1)})
    point_columns = ['elapsed_seconds', 'power_w', 'heart_rate_bpm', 'power_ma_w',
                     'heart_rate_ma_bpm', 'ma_sample_count', 'ma_incomplete']
    return {'points': json.loads(filtered[point_columns].to_json(orient='records', date_format='iso')),
            'blocks': blocks, 'end': float(ends[-1]), 'gapCount': len(runs)-1,
            'gaps': [{'start': float(ends[end-1]), 'end': float(times[next_start])}
                     for (_, end), (next_start, _) in zip(runs, runs[1:])],
            'missingPower': int((~valid).sum()), 'laps': details,
            'initialization': saved.get('initialization', 'legacy-saved') if saved else 'lap-mean-v1',
            'step': step, 'sensitivity': sensitivity, 'saved': saved}


def validate_part(frame, part):
    times, ends, _, _ = support(frame)
    if not 0 <= part.start < part.end <= ends[-1] + 1e-8:
        raise ValueError('Confini del segmento fuori dalla sorgente')
    previous = -1.
    for b in part.blocks:
        if b.start < previous or b.start >= b.end or b.end > ends[-1]+1e-8:
            raise ValueError('Intervalli sovrapposti, invertiti o fuori dalla sorgente')
        previous = b.end
    previous_locks = []
    for c in part.constraints:
        members = [b for b in part.blocks if b.start < c.end and b.end > c.start]
        if (not members or abs(members[0].start-c.start) > 1e-6 or abs(members[-1].end-c.end) > 1e-6
                or any(c.start < end and c.end > start for start, end in previous_locks)):
            raise ValueError('Vincolo ON/OFF fuori dai blocchi o sovrapposto')
        for i, b in enumerate(members):
            expected = c.on if (i+c.phase) % 2 == 0 else c.off
            duration = b.end-b.start
            partial = (i == 0 and c.partial_start) or (i == len(members)-1 and c.partial_end)
            if (i and abs(members[i-1].end-b.start) > 1e-6) or (duration > expected+1e-6 if partial else abs(duration-expected) > 1e-6):
                raise ValueError('Durata dei blocchi incoerente con il vincolo ON/OFF')
        previous_locks.append((c.start, c.end))
    mask = (times >= part.start) & (times < part.end)
    if not mask.any():
        raise ValueError('Il segmento non contiene campioni')
    return mask


def export_reconstruction(dataset, parts, extraction_blob=None):
    if not parts and not extraction_blob:
        raise ValueError('Nessun segmento in esportazione')
    entries, files, intervals, included, columns = [], {}, [], {}, {}
    units = {'timestamp': 'ISO 8601 UTC', 'elapsed_seconds': 's', 'source_elapsed_seconds': 's',
             'power_w': 'W', 'heart_rate_bpm': 'bpm', 'power_target_w': 'W',
             'power_w_kg': 'W/kg', 'hr_pct_max': '%', 'hr_pct_threshold': '%'}
    source_entries = {e['csv_file']: e for e in dataset.manifest['segments']} if dataset else {}
    for i, part in enumerate(parts):
        if part.source_id not in dataset.frames:
            raise ValueError('Segmento sorgente sconosciuto')
        frame = dataset.frames[part.source_id]
        mask = validate_part(frame, part)
        ranges = included.setdefault(part.source_id, [])
        if any(part.start < end and part.end > start for start, end in ranges):
            raise ValueError('Porzioni duplicate o sovrapposte della stessa sorgente')
        ranges.append((part.start, part.end))
        out = frame.loc[mask].copy()
        offset = float(out.elapsed_seconds.iloc[0])
        source_times = out.elapsed_seconds.to_numpy(dtype=float)
        if 'source_elapsed_seconds' not in out:
            out['source_elapsed_seconds'] = source_times
        out['elapsed_seconds'] = source_times-offset
        target = np.full(len(out), np.nan)
        local_blocks = []
        for b in part.blocks:
            start, end = max(part.start, b.start, offset), min(part.end, b.end)
            if end <= start:
                continue
            target[(source_times >= start) & (source_times < end)] = b.power
            local_blocks.append({'start': max(0., start-offset), 'end': end-offset, 'power': b.power})
        target[~np.isfinite(out.power_w) | (out.power_w < 0)] = np.nan
        out['power_target_w'] = target
        columns.update({col: {'unit': units.get(col)} for col in out.columns})
        name = f'reconstructed/segment_{i+1:04d}.csv'
        files[name] = out.to_csv(index=False)
        entry = deepcopy(source_entries[part.source_id])
        entry.update(csv_file=name, origin_page='reconstruction',
                     start_timestamp=str(out.timestamp.iloc[0]), end_timestamp=str(out.timestamp.iloc[-1]))
        entry.update(sample_support_end=part.end-offset, sample_step=support(frame)[2])
        entry['laps'] = [{**lap, 'start': max(lap['start'], part.start, offset)-offset,
                          'end': min(lap['end'], part.end)-offset,
                          'partialStart': lap.get('partialStart', False) or lap['start'] < max(part.start, offset),
                          'partialEnd': lap.get('partialEnd', False) or lap['end'] > part.end}
                         for lap in entry.get('laps', [])
                         if lap['end'] > max(part.start, offset) and lap['start'] < part.end]
        constraints = []
        for c in part.constraints:
            start, end = max(c.start, part.start, offset), min(c.end, part.end)
            if start >= end:
                continue
            members = [b for b in part.blocks if b.start < c.end and b.end > c.start]
            skipped = sum(b.end <= start for b in members)
            constraints.append({'start': start-offset, 'end': end-offset, 'on': c.on, 'off': c.off,
                'phase': (c.phase+skipped) % 2,
                'partialStart': start > members[skipped].start or (skipped == 0 and c.partial_start),
                'partialEnd': any(b.start < end < b.end for b in members) or (end == c.end and c.partial_end)})
        entry['reconstruction'] = {
            'initialization': source_entries[part.source_id].get('reconstruction', {}).get('initialization',
                'legacy-saved' if 'reconstruction' in source_entries[part.source_id] else 'lap-mean-v1'),
            'blocks': local_blocks, 'sensitivity': part.sensitivity, 'constraints': constraints,
            'automaticBlocks': [dict(b.model_dump(), start=max(0., b.start-offset), end=min(part.end, b.end)-offset)
                                for b in part.automatic_blocks if b.end > max(part.start, offset) and b.start < part.end],
            'source_id': part.source_id, 'source_bounds': [part.start, part.end], 'source_time_offset': offset}
        entry['reconstruction'].update(supportEnd=part.end-offset, sourceStep=support(frame)[2])
        entries.append(entry)
        for b in local_blocks:
            intervals.append({'csv_file': name, 'activity_id': entry['activity_id'],
                              'start_seconds': b['start'], 'end_seconds': b['end'], 'power_target_w': b['power']})
    if extraction_blob:
        with zipfile.ZipFile(io.BytesIO(extraction_blob)) as z:
            original = json.loads(z.read('manifest.json'))
            columns.update(original.get('columns', {}))
            for i, entry in enumerate(original['segments']):
                name = f'extracted/segment_{i+1:04d}.csv'
                files[name] = z.read(entry['csv_file'])
                entries.append({**entry, 'csv_file': name, 'origin_page': 'extraction'})
    exclusions = {}
    for name, ranges in included.items():
        cursor, omitted = 0., []
        for start, end in sorted(ranges):
            if start > cursor:
                omitted.append([cursor, start])
            cursor = end
        last = float(support(dataset.frames[name])[1][-1])
        if cursor < last:
            omitted.append([cursor, last])
        exclusions[name] = omitted
    manifest = {'format_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
        'segments': entries, 'boundary_convention': '[start,end); final support = last timestamp + median step',
        'columns': columns,
        'reconstruction': {'algorithm': 'lap-mean-with-manual-edits', 'algorithm_version': 1,
            'lap_boundary_correction': 'midpoint-gaps-v1 where recorded in lap boundary_adjustment; saved reconstructions preserved',
            'repeat_editing': 'keep selected count; alternate ON/OFF; first phase from first two levels; anchor start; adjust next start; no persistent constraints in current editor',
            'window_seconds': 5, 'window_role': 'visual reference only',
            'target': 'arithmetic mean of finite nonnegative raw samples in each lap; zeros included; rounded to 0.1 W',
            'lap_boundary_convention': '[start,end); final selected FIT endpoint includes last sample support',
            'smoothing_interval': '[t-2.5,t+2.5); truncated at temporal block edges',
            'gap_rule': 'dt > 1.5 * median(dt); gaps reported, never interpolated',
            'interpolation': False, 'resampling': False,
            'interpretation': 'editable hypothesis, not observed coach prescription',
            'source_sha256': dataset.sha256 if dataset else None,
            'source_manifest': dataset.manifest if dataset else None, 'excluded_ranges': exclusions}}
    if extraction_blob:
        manifest['extraction'] = original
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
        z.writestr('intervals.csv', pd.DataFrame(intervals, columns=[
            'csv_file', 'activity_id', 'start_seconds', 'end_seconds', 'power_target_w']).to_csv(index=False))
        z.writestr('manifest.json', json.dumps(manifest, indent=2, allow_nan=False))
    return bio.getvalue()
