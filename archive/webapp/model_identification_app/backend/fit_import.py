"""Lossless signal mapping from FIT record messages; no filtering or resampling."""
import csv
from datetime import datetime
import io

import fitdecode
import numpy as np

from .storage import sha


def convert_fit(data, filename):
    activity = 'fit:' + sha(data)
    fields = {'power': 'power_w', 'heart_rate': 'heart_rate_bpm',
              'cadence': 'cadence_rpm', 'speed': 'speed_m_s',
              'altitude': 'altitude_m', 'temperature': 'temperature_c'}
    rows = []
    first = None
    try:
        with fitdecode.FitReader(io.BytesIO(data)) as reader:
            for frame in reader:
                if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.name != 'record':
                    continue
                values = {field.name: field.value for field in frame.fields}
                stamp = values.get('timestamp')
                if not isinstance(stamp, datetime):
                    raise ValueError('record senza timestamp valido')
                if first is None:
                    first = stamp
                row = {'activity_id': activity, 'timestamp': stamp.isoformat(),
                       'elapsed_seconds': (stamp-first).total_seconds()}
                row.update({column: values.get(field) for field, column in fields.items()})
                for field in ('speed', 'altitude'):
                    if values.get('enhanced_'+field) is not None:
                        row[fields[field]] = values['enhanced_'+field]
                rows.append(row)
    except Exception as exc:
        raise ValueError(f'{filename}: FIT non valido ({exc})') from exc
    if not rows:
        raise ValueError(f'{filename}: FIT senza record')
    t = np.array([r['elapsed_seconds'] for r in rows])
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError(f'{filename}: timestamp FIT non crescenti; nessun riordino automatico')
    p = np.array([r['power_w'] if r['power_w'] is not None else np.nan for r in rows])
    h = np.array([r['heart_rate_bpm'] if r['heart_rate_bpm'] is not None else np.nan for r in rows])
    median = float(np.median(dt)) if len(dt) else None
    quality = {'missing_power_samples': int((~np.isfinite(p)).sum()),
               'missing_hr_samples': int((~np.isfinite(h)).sum()),
               'zero_power_samples': int((p == 0).sum()),
               'sampling_interval_median_seconds': median,
               'max_gap_seconds': float(dt.max()) if len(dt) else None,
               'gap_count': int((dt > 1.5*median).sum()) if len(dt) else 0}
    warnings = []
    if quality['missing_power_samples']: warnings.append('missing_power')
    if quality['missing_hr_samples']: warnings.append('missing_hr')
    if quality['gap_count']: warnings.append('recording_gaps')
    if len(dt) and not np.allclose(dt, median, rtol=.01): warnings.append('irregular_sampling')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=['activity_id', 'timestamp', 'elapsed_seconds', *fields.values()])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8'), {
        'kind': 'activity', 'activity_id': activity, 'fit_sha256': sha(data),
        'source_file': filename, 'quality': quality, 'warnings': warnings,
        'conversion': {'version': 1, 'parser': 'fitdecode', 'parser_version': fitdecode.__version__,
                       'time_origin': 'first record timestamp', 'time_unit': 's',
                       'power_unit': 'W', 'hr_unit': 'bpm', 'resampling': False,
                       'filtering': False, 'missing_values': 'preserved as empty CSV cells',
                       'enhanced_speed_altitude': 'preferred when available'}}
