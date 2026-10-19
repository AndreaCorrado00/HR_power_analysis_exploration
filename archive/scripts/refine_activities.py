"""Refine the complete road-activity CSV export without overwriting sources.

Run from the repository root; see references/dataset_refinement_protocol.md.
"""
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ('power_w', 'heart_rate_bpm')
FLAGS = ['source_row_index', 'source_elapsed_seconds', 'activity_modified',
         'activity_trimmed', 'timestamp_inserted', 'power_imputed', 'hr_imputed']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def acf(values):
    x = np.asarray(values) - np.mean(values)
    den = float(x @ x)
    return float(x[1:] @ x[:-1] / den) if len(x) > 2 and den > 1e-15 else None


def detrend(t, y):
    return y - np.polyval(np.polyfit(t - t[0], y, 1), t - t[0])


def fill_gap(t, observed, a, z, rng):
    """Endpoint trend plus resampled local detrended residuals; never use imputed donors."""
    n = int(z-a)
    dt = float(np.median(np.diff(t)))
    duration = float(t[z]-t[a-1]-dt)
    trend = np.interp(t[a:z], [t[a-1], t[z]], [observed[a-1], observed[z]])
    donors, windows = [], []
    for side, anchor, direction in [('left', a-1, -1), ('right', z, 1)]:
        ids = []
        i = anchor
        while 0 <= i < len(t) and abs(t[i]-t[anchor]) <= duration+1e-8:
            if not np.isfinite(observed[i]):
                break
            ids.append(i)
            i += direction
        ids.sort()
        complete = len(ids) > 1 and t[ids[-1]]-t[ids[0]] >= duration-1e-8
        windows.append(dict(side=side, samples=len(ids), complete=bool(complete),
                            start_s=float(t[ids[0]]) if ids else None,
                            end_s=float(t[ids[-1]]) if ids else None))
        if len(ids) >= 3:
            donors.append(detrend(t[ids], observed[ids]))
    target_sd = float(np.std(np.concatenate(donors), ddof=1)) if donors else 0.
    residual = np.zeros(n)
    block_length = max(1, min(int(round(np.sqrt(n))), min(map(len, donors), default=1)))
    if donors and target_sd > 1e-12:
        pieces = []
        while sum(map(len, pieces)) < n:
            donor = donors[int(rng.integers(len(donors)))]
            start = int(rng.integers(len(donor)))
            pieces.append(donor[(start+np.arange(block_length)) % len(donor)])
        residual = np.concatenate(pieces)[:n]
        if n >= 3:
            residual = detrend(t[a:z], residual)
            sd = float(np.std(residual, ddof=1))
            if sd > 1e-12:
                residual *= target_sd/sd
    values = np.maximum(0., trend+residual)
    actual = values-trend
    info = dict(samples=int(n), start_s=float(t[a]), end_s=float(t[z-1]),
                anchor_span_s=float(t[z]-t[a-1]), reference_duration_s=duration,
                windows=windows, block_length=block_length,
                trend_slope=float((observed[z]-observed[a-1])/(t[z]-t[a-1])),
                target_residual_sd=target_sd,
                generated_residual_sd=float(np.std(actual, ddof=1)) if n > 1 else None,
                generated_residual_slope=float(np.polyfit(t[a:z]-t[a], actual, 1)[0]) if n > 1 else None,
                reference_acf_lag1=[acf(v) for v in donors], generated_acf_lag1=acf(actual),
                nonnegative_clipped=int(np.sum(trend+residual < 0)),
                insufficient_reference=not bool(donors),
                short_gap_statistics_unidentifiable=n < 3,
                truncated_reference=not all(w['complete'] for w in windows))
    return values, info


def refine(source, key, seed=42):
    t = np.array([number(r['elapsed_seconds']) for r in source])
    if len(t) < 4 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError(f'{key}: invalid timestamps or fewer than four records')
    stamps = [datetime.fromisoformat(r['timestamp']) for r in source]
    stamp_elapsed = np.array([(s-stamps[0]).total_seconds() for s in stamps])
    if not np.allclose(stamp_elapsed, t-t[0], atol=1e-6, rtol=0):
        raise ValueError(f'{key}: timestamp/elapsed mismatch')
    dt = float(np.median(np.diff(t)))
    meta = dict(excluded=False, modified=False, source_samples=len(source),
                source_duration_s=float(t[-1]-t[0]), max_timestamp_interval_s=float(np.diff(t).max()))
    if np.any(np.diff(t) > 10):
        meta.update(excluded=True, reason='timestamp_interval_gt_10s',
                    excluded_intervals=[dict(start_s=float(t[i]), end_s=float(t[i+1]))
                                        for i in np.flatnonzero(np.diff(t) > 10)])
        return [], meta, []
    if not np.isclose(dt, 1.):
        raise ValueError(f'{key}: protocol requires nominal 1-second sampling')
    missing = np.array([any(not np.isfinite(number(r[c])) for c in SIGNALS) for r in source])
    position = (t-t[0])/(t[-1]-t[0])
    head = np.flatnonzero(missing & (position < .1))
    tail = np.flatnonzero(missing & (position > .9))
    lo = int(head[-1]+1) if len(head) else 0
    hi = int(tail[0]) if len(tail) else len(t)
    # A run crossing a 10% boundary is removed completely, without iteration
    # of the percentage thresholds on the shortened activity.
    while lo < hi and missing[lo]: lo += 1
    while hi > lo and missing[hi-1]: hi -= 1
    if hi-lo < 4:
        raise ValueError(f'{key}: trimming leaves fewer than four samples')
    trimmed = lo > 0 or hi < len(t)
    output = []
    for i in range(lo, hi):
        row = dict(source[i])
        row.update(source_row_index=str(i), source_elapsed_seconds=source[i]['elapsed_seconds'],
                   timestamp_inserted='0', power_imputed='0', hr_imputed='0')
        output.append(row)
        if i+1 < hi:
            for tx in np.arange(t[i]+dt, t[i+1]-1e-8, dt):
                new = {c: '' for c in source[i]}
                new.update(activity_id=source[i]['activity_id'],
                           timestamp=(stamps[i]+timedelta(seconds=float(tx-t[i]))).isoformat(),
                           elapsed_seconds=format(tx, '.17g'), source_row_index='',
                           source_elapsed_seconds=format(tx, '.17g'), timestamp_inserted='1',
                           power_imputed='0', hr_imputed='0')
                output.append(new)
    ot = np.array([number(r['elapsed_seconds']) for r in output])
    events = []
    for column, flag in zip(SIGNALS, ['power_imputed', 'hr_imputed']):
        observed = np.array([number(r[column]) for r in output])
        for a, z in runs(~np.isfinite(observed)):
            if a == 0 or z == len(ot):
                raise ValueError(f'{key}: unbracketed gap remains')
            event_seed = int(sha(f'{seed}:{key}:{column}:{ot[a]}'.encode())[:16], 16)
            values, info = fill_gap(ot, observed, a, z, np.random.default_rng(event_seed))
            info.update(column=column, seed=event_seed)
            events.append(info)
            for j, v in zip(range(a, z), values):
                output[j][column] = format(v, '.17g')
                output[j][flag] = '1'
    modified = trimmed or bool(events)
    for row in output:
        row.update(elapsed_seconds=format(number(row['source_elapsed_seconds'])-t[lo], '.17g'),
                   activity_modified=str(int(modified)), activity_trimmed=str(int(trimmed)))
    meta.update(modified=modified, trimmed=trimmed, trimmed_head_rows=lo,
                trimmed_tail_rows=len(t)-hi, kept_source_start_s=float(t[lo]),
                kept_source_end_s=float(t[hi-1]), output_samples=len(output),
                inserted_rows=sum(int(r['timestamp_inserted']) for r in output),
                power_imputed=sum(int(r['power_imputed']) for r in output),
                hr_imputed=sum(int(r['hr_imputed']) for r in output),
                interpolation_events=len(events))
    # Verify preservation of every retained observed value and all non-signal data.
    for row in output:
        assert all(np.isfinite(number(row[c])) for c in SIGNALS)
        if row['source_row_index']:
            old = source[int(row['source_row_index'])]
            for c in old:
                if c == 'elapsed_seconds': continue
                if c in SIGNALS and not np.isfinite(number(old[c])): continue
                assert row[c] == old[c], (key, c)
    return output, meta, events


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    fields = list(dict.fromkeys(c for r in rows for c in r))
    w = csv.DictWriter(stream, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return stream.getvalue().encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'dataset/cleaned_only_road_activieties.zip')
    parser.add_argument('--csv-source', type=Path, default=ROOT/'dataset/cleaned_only_road_activities_csv.zip')
    parser.add_argument('--output', type=Path, default=ROOT/'dataset/refined_only_road_activities_csv.zip')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('Output exists; choose another path')
    source_hash = sha(args.source.read_bytes())
    csv_hash = sha(args.csv_source.read_bytes())
    entries, inventory, events, contents = [], [], [], []
    with zipfile.ZipFile(args.csv_source) as archive:
        parent = json.loads(archive.read('manifest.json'))
        assert parent['source_archive_sha256'] == source_hash
        for segment in parent['segments']:
            name = segment['csv_file']
            raw = archive.read(name)
            assert sha(raw) == segment['csv_sha256']
            original = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
            rows, refinement, diagnostic = refine(original, segment['fit_sha256'], args.seed)
            inventory.append(dict(csv_file=name, **refinement))
            if refinement['excluded']: continue
            blob = csv_bytes(rows)
            contents.append((name, blob))
            values = np.array([[number(r[c]) for r in rows] for c in SIGNALS])
            times = np.array([number(r['elapsed_seconds']) for r in rows])
            quality = dict(missing_power_samples=0, missing_hr_samples=0,
                           zero_power_samples=int(np.sum(values[0] == 0)),
                           sampling_interval_median_seconds=float(np.median(np.diff(times))),
                           max_gap_seconds=float(np.diff(times).max()),
                           gap_count=int(np.sum(np.diff(times)>1.5)))
            entries.append(dict(segment, csv_sha256=sha(blob),
                                original_csv_sha256=segment['csv_sha256'],
                                original_quality=segment['quality'], quality=quality,
                                original_warnings=segment['warnings'],
                                warnings=['synthetic_signal_values'] if diagnostic else [],
                                selection='refined complete activity; see refinement metadata',
                                refinement=refinement))
            events.extend(dict(csv_file=name, **e) for e in diagnostic)
    summary = dict(source_activities=len(inventory), excluded=sum(r['excluded'] for r in inventory),
                   retained=len(entries), modified=sum(e['refinement']['modified'] for e in entries),
                   trimmed=sum(e['refinement']['trimmed'] for e in entries),
                   inserted_rows=sum(e['refinement']['inserted_rows'] for e in entries),
                   power_imputed=sum(e['refinement']['power_imputed'] for e in entries),
                   hr_imputed=sum(e['refinement']['hr_imputed'] for e in entries),
                   interpolation_events=len(events),
                   insufficient_reference_events=sum(e['insufficient_reference'] for e in events),
                   short_gap_events=sum(e['short_gap_statistics_unidentifiable'] for e in events),
                   truncated_reference_events=sum(e['truncated_reference'] for e in events),
                   clipped_values=sum(e['nonnegative_clipped'] for e in events))
    protocol = (ROOT/'references/dataset_refinement_protocol.md').read_bytes()
    manifest = dict(format_version=1, dataset_kind='refined_complete_activities',
                    source_archive=str(args.source), source_archive_sha256=source_hash,
                    source_csv_archive_sha256=csv_hash, seed=args.seed,
                    generator_sha256=sha(Path(__file__).read_bytes()),
                    protocol_sha256=sha(protocol), columns=parent['columns'],
                    preprocessing=dict(exclude_timestamp_interval_gt_s=10,
                                       trim_original_duration_fractions=[.1,.9],
                                       interpolation='endpoint trend plus local residual block bootstrap',
                                       inserted_timestamp_step_s=1, time_origin='first retained observation',
                                       original_elapsed_column='source_elapsed_seconds',
                                       synthetic_values_are_not_observations=True),
                    summary=summary, segments=entries)
    # Fixed ZIP metadata makes identical inputs/seed produce identical archives.
    def add(archive, name, data):
        info = zipfile.ZipInfo(name, date_time=(2026,9,29,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, data)
    metadata = {
        'manifest.json': json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        'metadata/activity_audit.json': json.dumps(inventory, indent=2, allow_nan=False),
        'metadata/interpolation_events.json': json.dumps(events, indent=2, allow_nan=False),
        'metadata/activity_flags.csv': csv_bytes([
            {k:v for k,v in r.items() if k != 'excluded_intervals'} for r in inventory]),
        'metadata/protocol.md': protocol,
    }
    with zipfile.ZipFile(args.output, 'x') as archive:
        for name, data in contents: add(archive, name, data)
        for name, data in metadata.items(): add(archive, name, data)
    assert sha(args.source.read_bytes()) == source_hash
    assert sha(args.csv_source.read_bytes()) == csv_hash
    print(json.dumps(summary, indent=2))
    print(f'OUTPUT {args.output}\nSHA256 {sha(args.output.read_bytes())}')


if __name__ == '__main__':
    main()
