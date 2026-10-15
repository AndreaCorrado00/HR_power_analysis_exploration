"""Read-only input handling; segmentation and workout-level time splits."""
from dataclasses import dataclass
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd


@dataclass
class Segment:
    workout_id: str
    segment_id: int
    time: np.ndarray
    residual: np.ndarray
    target: np.ndarray


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(source):
    records = []
    for path in sorted((Path(source)/'samples').glob('*.csv.gz')):
        first = pd.read_csv(path, usecols=['timestamp'], nrows=1)
        start = pd.to_datetime(first.timestamp.iloc[0], utc=True)
        if pd.isna(start):
            raise ValueError(f'Invalid start timestamp: {path}')
        records.append(dict(workout_id=path.name.split('.')[0], path=str(path.resolve()),
                            start_time=start.isoformat(), sha256=sha256(path)))
    return sorted(records, key=lambda r: (r['start_time'], r['workout_id']))


def chronological_split(records, train_count, validation_count):
    if train_count < 1 or validation_count < 1 or train_count+validation_count >= len(records):
        raise ValueError('Need nonempty train, validation and test workout sets')
    ids = [r['workout_id'] for r in sorted(records, key=lambda r: (r['start_time'], r['workout_id']))]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate workout identifiers')
    return dict(train=ids[:train_count], validation=ids[train_count:train_count+validation_count],
                test=ids[train_count+validation_count:])


def verify_inputs(records):
    for record in records:
        if sha256(record['path']) != record['sha256']:
            raise ValueError(f"Input changed: {record['workout_id']}")


def segment_frame(frame, workout_id, *, split_at_prescription=True):
    t, power, target = [frame[c].to_numpy(float) for c in
                        ['elapsed_seconds', 'power_w', 'power_target_w']]
    if not len(t) or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError(f'{workout_id}: timestamps must be finite and strictly increasing')
    if frame.timer_paused.isna().any() or not frame.timer_paused.isin([True, False]).all():
        raise ValueError('timer_paused must contain booleans')
    paused = frame.timer_paused.to_numpy(bool)
    sid = frame.power_segment_id.to_numpy(float)
    lap = frame.lap_index.to_numpy(float)
    observed = np.isfinite(power) & (power >= 0)
    numeric = np.isfinite(target)
    valid = observed & numeric & ~paused & np.isfinite(sid) & (sid > 0) & np.isfinite(lap) & (lap > 0)
    link = valid[:-1] & valid[1:] & (np.diff(t) == 1) & (sid[:-1] == sid[1:])
    if split_at_prescription:
        link &= (target[:-1] == target[1:]) & (lap[:-1] == lap[1:])
    boundaries = np.r_[0, np.flatnonzero(~link)+1, len(t)]
    segments = []
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        if valid[a]:
            segments.append(Segment(str(workout_id), len(segments)+1, t[a:b].copy(),
                                    (power[a:b]-target[a:b]).copy(), target[a:b].copy()))
    coverage = dict(workout_id=str(workout_id), total_samples=len(t), valid_samples=int(valid.sum()),
                    invalid_power_samples=int((~observed).sum()), nonnumeric_target_samples=int((~numeric).sum()),
                    paused_samples=int(paused.sum()), excluded_samples=int((~valid).sum()),
                    zero_power_valid_samples=int((valid & (power == 0)).sum()), segments=len(segments))
    return segments, coverage


def load_segments(records, ids, *, split_at_prescription=True):
    selected = set(ids)
    segments, coverage = [], []
    for record in records:
        if record['workout_id'] in selected:
            parts, counts = segment_frame(pd.read_csv(record['path']), record['workout_id'],
                                          split_at_prescription=split_at_prescription)
            segments.extend(parts)
            coverage.append(counts)
    if len(coverage) != len(selected):
        raise ValueError('Missing workout in inventory')
    return segments, pd.DataFrame(coverage)
