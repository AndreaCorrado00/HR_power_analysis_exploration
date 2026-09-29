import importlib.util
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/refine_activities.py'
    assert path.exists(), 'Missing refinement implementation'
    spec = importlib.util.spec_from_file_location('refine', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rows(times=range(101)):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [dict(activity_id='test', elapsed_seconds=str(t),
                 timestamp=(base + timedelta(seconds=t)).isoformat(),
                 power_w=str(200 + t + 10*np.sin(t)),
                 heart_rate_bpm=str(120 + .2*t + np.sin(t)), cadence_rpm='90')
            for t in times]


def test_exclusion_strict_threshold_and_inserted_rows():
    f = module().refine
    assert f(rows([*range(40), *range(50,101)]), 'a')[1]['excluded']
    out, meta, events = f(rows([*range(40), *range(49,101)]), 'a')
    assert not meta['excluded']
    assert len(out) == 101
    assert sum(int(r['timestamp_inserted']) for r in out) == 9


def test_tail_cut_original_duration_and_preservation():
    f = module().refine
    source = rows()
    for i in [2, 8, 95]: source[i]['power_w'] = ''
    source[50]['heart_rate_bpm'] = ''
    out, meta, events = f(source, 'a')
    assert [int(float(r['source_elapsed_seconds'])) for r in out] == list(range(9,95))
    assert out[0]['elapsed_seconds'] == '0'
    assert meta['trimmed_head_rows'] == 9 and meta['trimmed_tail_rows'] == 6
    for r in out:
        original = source[int(r['source_row_index'])]
        for key in ['timestamp', 'cadence_rpm', 'power_w', 'heart_rate_bpm']:
            if original[key]: assert r[key] == original[key]
    assert all(np.isfinite(float(r['heart_rate_bpm'])) for r in out)


def test_reproducible_noise_and_no_trimming_at_exact_ten_percent():
    f = module().refine
    source = rows(range(201))
    for i in [20, *range(80,91), 180]: source[i]['power_w'] = ''
    first = f(source, 'stable', seed=42)
    second = f(source, 'stable', seed=42)
    assert first == second
    out, meta, events = first
    assert len(out) == 201
    event = next(e for e in events if e['samples'] == 11)
    assert event['target_residual_sd'] > 0
    assert np.isclose(event['generated_residual_sd'], event['target_residual_sd'])
    assert abs(event['generated_residual_slope']) < 1e-8
    json.dumps(first, allow_nan=False)


def test_unchanged_activity_is_not_flagged_modified():
    out, meta, _ = module().refine(rows(), 'a')
    assert not meta['modified']
    assert all(r['activity_modified'] == '0' for r in out)
