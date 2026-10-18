"""Explicit common support, source hashes and activity-level temporal split."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from power_response_estimation.data import inventory, chronological_split, segment_frame, sha256

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/processed/prescribed_workouts_final'
OUTPUT = HERE / 'results'


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def hr_parts(frame, workout_id, *, training):
    """Missing HR changes fitting support only; no future HR conditions prediction."""
    parts, _ = segment_frame(frame, workout_id, split_at_prescription=False)
    indexed = frame.set_index('elapsed_seconds')
    result = []
    for part in parts:
        hr = indexed.loc[part.time, 'heart_rate_bpm'].to_numpy(float)
        valid = np.isfinite(hr) if training else np.ones(len(hr), bool)
        edges = np.r_[0, np.flatnonzero(valid[1:] != valid[:-1])+1, len(hr)]
        for a, b in zip(edges[:-1], edges[1:]):
            if not valid[a] or b-a < 301:
                continue
            result.append(dict(id=f'{workout_id}_{part.segment_id}_{a}', workout_id=workout_id,
                power_segment_id=part.segment_id, offset=a, elapsed=part.time[a:b].copy(),
                time=part.time[a:b]-part.time[a], power=(part.target+part.residual)[a:b].copy(),
                target=part.target[a:b].copy(), hr=hr[a:b].copy()))
    return result


def prepare(output=OUTPUT):
    records = inventory(SOURCE)
    if len(records) != 60:
        raise ValueError('Expected the approved 60-workout dataset')
    split = chronological_split(records, 42, 9)
    rows, segments = [], []
    for record in records:
        wid = record['workout_id']
        group = next(k for k, ids in split.items() if wid in ids)
        f = pd.read_csv(record['path'])
        power_parts, coverage = segment_frame(f, wid, split_at_prescription=False)
        parts = hr_parts(f, wid, training=group == 'train')
        dt = np.diff(f.elapsed_seconds.to_numpy(float))
        hr = f.heart_rate_bpm.to_numpy(float)
        power = f.power_w.to_numpy(float)
        rows.append(dict(**coverage, split=group, hr_segments=len(parts),
            hr_samples=sum(len(p['time']) for p in parts), missing_hr=int((~np.isfinite(hr)).sum()),
            missing_power=int((~np.isfinite(power)).sum()), zero_power=int((power == 0).sum()),
            negative_power=int((power < 0).sum()), non_1s_intervals=int((dt != 1).sum()),
            max_interval_s=float(dt.max()), hr_jumps_over_10bpm_1s=int(((abs(np.diff(hr))>10)&(dt==1)).sum()),
            hr_outside_30_240=int(((hr<30)|(hr>240)).sum()),
            duration_s=float(f.elapsed_seconds.iloc[-1]-f.elapsed_seconds.iloc[0]),
            power_quantiles_w=np.nanquantile(power,[0,.25,.5,.75,1]).tolist(),
            power_segment_lengths=[len(p.time) for p in power_parts]))
        segments.extend(dict(id=p['id'], activity_id=wid, split=group,
            source_start_s=float(p['elapsed'][0]), source_end_s=float(p['elapsed'][-1]),
            samples=len(p['time']), sha256=record['sha256']) for p in parts)
    portable = [{**r, 'path':str(Path(r['path']).relative_to(ROOT))} for r in records]
    manifest = dict(id='prescribed_joint_42_9_9', records=portable, split=split,
        segments=segments, quality=rows, protocol_sha256=sha256(HERE/'PROTOCOL.md'))
    if (output/'manifest.json').exists():
        old = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if old != manifest:
            raise ValueError('Input/protocol changed; use a new output directory')
    save(output/'manifest.json', manifest)
    save(output/'split.json', split)
    return manifest


def load_parts(manifest, split):
    result = []
    for record in manifest['records']:
        if record['workout_id'] not in manifest['split'][split]:
            continue
        path = ROOT/record['path']
        if sha256(path) != record['sha256']:
            raise ValueError(f'Changed source: {path}')
        result.extend(hr_parts(pd.read_csv(path), record['workout_id'], training=split=='train'))
    return result
