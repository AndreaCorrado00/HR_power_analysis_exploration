"""Reproducible offline processing of exported segment archives."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import PurePosixPath
import zipfile

import numpy as np
import pandas as pd

from .normalization import NormalizationRequest, apply_normalizations

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
RAW = ('power_w', 'heart_rate_bpm')
DERIVED = {'power_ma_w', 'heart_rate_ma_bpm', 'ma_sample_count', 'ma_incomplete',
           'power_w_kg', 'hr_pct_max', 'hr_pct_threshold', 'power_ma_w_kg',
           'hr_ma_pct_max', 'hr_ma_pct_threshold'}


@dataclass
class SegmentDataset:
    manifest: dict
    frames: dict[str, pd.DataFrame]
    sha256: str


def read_archive(blob: bytes) -> SegmentDataset:
    if len(blob) > MAX_ARCHIVE:
        raise ValueError('ZIP troppo grande (massimo 256 MiB)')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or len(names) > 10000:
                raise ValueError('Archivio con nomi duplicati o troppi file')
            if sum(i.file_size for i in z.infolist()) > MAX_EXPANDED:
                raise ValueError('Archivio espanso troppo grande (massimo 512 MiB)')
            manifest = json.loads(z.read('manifest.json'))
            if not isinstance(manifest, dict) or manifest.get('format_version') not in (1, 2):
                raise ValueError('Versione del manifest non supportata')
            entries = manifest.get('segments')
            if not isinstance(entries, list) or not entries:
                raise ValueError('Nessun segmento nel manifest')
            frames = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError('Voce segmento non valida')
                name = entry.get('csv_file')
                if (not isinstance(name, str) or not name.endswith('.csv') or
                    '\\' in name or ':' in name or PurePosixPath(name).is_absolute() or
                    '..' in PurePosixPath(name).parts or name in frames):
                    raise ValueError('Nome CSV non valido o duplicato')
                frame = pd.read_csv(io.BytesIO(z.read(name)))
                required = {'timestamp', 'elapsed_seconds', 'activity_id', 'first_lap', 'last_lap', *RAW}
                if not required.issubset(frame.columns) or frame.empty:
                    raise ValueError(f'{name}: colonne originali mancanti o segmento vuoto')
                for col in ('elapsed_seconds', *RAW):
                    frame[col] = pd.to_numeric(frame[col], errors='raise')
                    if np.isinf(frame[col]).any():
                        raise ValueError(f'{name}: valori infiniti in {col}')
                times = frame.elapsed_seconds.to_numpy(dtype=float)
                if not np.isfinite(times).all() or times[0] != 0 or (np.diff(times) <= 0).any():
                    raise ValueError(f'{name}: tempi relativi non crescenti o non inizianti da zero')
                stamps = pd.to_datetime(frame.timestamp, utc=True, errors='raise')
                if stamps.isna().any() or not np.allclose((stamps-stamps.iloc[0]).dt.total_seconds(), times, atol=1e-6, rtol=0):
                    raise ValueError(f'{name}: timestamp incoerenti con il tempo relativo')
                for key in ('activity_id', 'first_lap', 'last_lap'):
                    if key not in entry or not frame[key].eq(entry[key]).all():
                        raise ValueError(f'{name}: {key} incoerente con il manifest')
                frames[name] = frame.drop(columns=list(DERIVED), errors='ignore')
            return SegmentDataset(manifest, frames, hashlib.sha256(blob).hexdigest())
    except (zipfile.BadZipFile, KeyError, UnicodeError, pd.errors.ParserError, TypeError, RuntimeError) as exc:
        raise ValueError(f'ZIP dei segmenti non valido: {exc}') from exc


def time_blocks(frame: pd.DataFrame):
    times = frame.elapsed_seconds.to_numpy(dtype=float)
    delta = np.diff(times)
    step = float(np.median(delta)) if len(delta) else 1.0
    starts = np.r_[0, np.flatnonzero(delta > 1.5 * step) + 1]
    return times, step, list(zip(starts, np.r_[starts[1:], len(times)]))


def inventory(dataset: SegmentDataset) -> list[dict]:
    result = []
    for entry in dataset.manifest['segments']:
        name = entry['csv_file']; frame = dataset.frames[name]
        times, step, blocks = time_blocks(frame)
        missing = {c: int(frame[c].isna().sum()) for c in RAW}
        result.append({'id': name, 'activityId': entry['activity_id'],
            'firstLap': entry['first_lap'], 'lastLap': entry['last_lap'],
            'durationSeconds': float(times[-1]), 'sampleCount': len(frame),
            'gapCount': len(blocks)-1, 'medianStepSeconds': step, 'missing': missing})
    return result


def smooth(frame: pd.DataFrame, window: int, norm: NormalizationRequest) -> pd.DataFrame:
    out = frame.copy()
    times, step, blocks = time_blocks(frame)
    for source, target in zip(RAW, ('power_ma_w', 'heart_rate_ma_bpm')):
        out[target] = np.nan
    out['ma_sample_count'] = 0
    out['ma_incomplete'] = False
    for start, end in blocks:
        t = times[start:end]
        # Half-open interval gives exactly W samples at regular 1 Hz, also for W=10.
        left = np.searchsorted(t, t - window / 2, side='left')
        right = np.searchsorted(t, t + window / 2, side='left')
        count = right-left
        idx = out.index[start:end]
        out.loc[idx, 'ma_sample_count'] = count
        # Compare window support to the sample cells, each of width median step.
        out.loc[idx, 'ma_incomplete'] = ((t-window/2 < t[0]-step/2) |
                                               (t+window/2 > t[-1]+step/2))
        for source, target in zip(RAW, ('power_ma_w', 'heart_rate_ma_bpm')):
            values = out[source].iloc[start:end].to_numpy(dtype=float)
            missing = np.r_[0, np.cumsum(np.isnan(values))]
            sums = np.r_[0, np.cumsum(np.nan_to_num(values))]
            means = (sums[right]-sums[left])/count
            means[missing[right] != missing[left]] = np.nan
            out.loc[idx, target] = means
    # Reuse the existing global normalization validation and formulas.
    for power, hr, names in (
        ('power_w', 'heart_rate_bpm', {}),
        ('power_ma_w', 'heart_rate_ma_bpm', {'power_w_kg': 'power_ma_w_kg',
            'hr_pct_max': 'hr_ma_pct_max', 'hr_pct_threshold': 'hr_ma_pct_threshold'})):
        normalized = apply_normalizations(pd.DataFrame({'power': out[power], 'heart_rate': out[hr]}), norm)
        for col in ('power_w_kg', 'hr_pct_max', 'hr_pct_threshold'):
            if col in normalized:
                out[names.get(col, col)] = normalized[col]
    return out


def process(dataset: SegmentDataset, selected: list[str], window: int,
            norm: NormalizationRequest) -> dict[str, pd.DataFrame]:
    if window not in (3, 5, 10):
        raise ValueError('La finestra deve essere 3, 5 o 10 secondi')
    if not selected or len(selected) != len(set(selected)) or any(s not in dataset.frames for s in selected):
        raise ValueError('Selezionare segmenti validi e non duplicati')
    return {name: smooth(dataset.frames[name], window, norm) for name in selected}


def export_archive(dataset: SegmentDataset, frames: dict[str, pd.DataFrame],
                   window: int, norm: NormalizationRequest) -> bytes:
    units = {'power_w': 'W', 'heart_rate_bpm': 'bpm', 'power_ma_w': 'W',
        'heart_rate_ma_bpm': 'bpm', 'elapsed_seconds': 's', 'timestamp': 'ISO 8601 UTC',
        'power_w_kg': 'W/kg', 'power_ma_w_kg': 'W/kg', 'hr_pct_max': '%',
        'hr_pct_threshold': '%', 'hr_ma_pct_max': '%', 'hr_ma_pct_threshold': '%',
        'ma_sample_count': 'samples', 'ma_incomplete': 'boolean'}
    manifest = {'format_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
        'source': {'sha256': dataset.sha256, 'manifest': dataset.manifest},
        'segments': [e for e in dataset.manifest['segments'] if e['csv_file'] in frames],
        'columns': {c: {'unit': units.get(c)} for f in frames.values() for c in f.columns},
        'normalization': asdict(norm),
        'processing': {'algorithm': 'centered-time-mean', 'algorithm_version': 1,
            'window_seconds': window, 'scope': 'all selected segments and both signals',
            'interval': '[t-W/2, t+W/2)', 'gap_rule': 'dt > 1.5 * median(dt) per segment',
            'endpoints': 'truncate within contiguous block; report ma_incomplete',
            'missing': 'propagate independently per signal', 'interpolation': False,
            'resampling': False, 'source_columns': list(RAW),
            'normalization_formulas': {'power_w_kg': 'power_w / weight_kg',
                'power_ma_w_kg': 'power_ma_w / weight_kg',
                'hr_pct_max': '100 * heart_rate_bpm / hr_max_bpm',
                'hr_pct_threshold': '100 * heart_rate_bpm / hr_threshold_bpm',
                'hr_ma_pct_max': '100 * heart_rate_ma_bpm / hr_max_bpm',
                'hr_ma_pct_threshold': '100 * heart_rate_ma_bpm / hr_threshold_bpm'}}}
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, frame in frames.items():
            z.writestr(name, frame.to_csv(index=False))
        z.writestr('manifest.json', json.dumps(manifest, indent=2, allow_nan=False))
    return bio.getvalue()
