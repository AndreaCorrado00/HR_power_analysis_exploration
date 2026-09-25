"""Read local folders and ZIP entries without extracting archives to disk."""
from pathlib import Path, PurePosixPath
from io import BytesIO
import stat
import zipfile
import fitdecode
import pandas as pd
from power_hr_eda.fit_reader import FitActivity, collect_activity, read_fit_activity
from .dataset_service import DatasetPathError

MAX_FIT_BYTES = 256 * 1024 * 1024

def project_root():
    root = Path(__file__).resolve().parents[3]
    marker = root / '.git'
    if marker.is_file():
        gitdir = Path(marker.read_text().strip().removeprefix('gitdir: ').strip())
        for parent in gitdir.parents:
            if parent.name == '.git':
                return parent.parent
    return root

def source_path(value):
    path = Path(value).expanduser() if value else project_root() / 'dataset'
    if not path.is_absolute():
        path = project_root() / path
    if not path.exists():
        raise DatasetPathError('Percorso non trovato')
    return path.resolve()

def zip_members(archive):
    result = {}
    for item in archive.infolist():
        name = PurePosixPath(item.filename)
        if name.is_absolute() or '..' in name.parts or '\\' in item.filename:
            raise DatasetPathError('Archivio ZIP con percorsi non validi')
        if not item.is_dir() and name.suffix.lower() == '.fit':
            if item.filename in result:
                raise DatasetPathError('Archivio ZIP con nomi FIT duplicati')
            result[item.filename] = item
    return result

def browse_source(path_text='', folder=''):
    path = source_path(path_text)
    if path.is_dir():
        entries = []
        for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            kind = 'directory' if item.is_dir() else item.suffix.lower().lstrip('.')
            if kind in ('directory', 'zip', 'fit'):
                entries.append({'name': item.name, 'path': str(item), 'kind': kind})
        return {'path': str(path), 'folder': '', 'isZip': False, 'parent': str(path.parent), 'entries': entries}
    if path.suffix.lower() != '.zip':
        raise DatasetPathError('Selezionare una cartella o un archivio ZIP')
    prefix = folder.strip('/')
    if '..' in PurePosixPath(prefix).parts:
        raise DatasetPathError('Cartella ZIP non valida')
    prefix = prefix + '/' if prefix else ''
    with zipfile.ZipFile(path) as archive:
        members = zip_members(archive)
    entries = {}
    for name in members:
        if not name.startswith(prefix):
            continue
        remainder = name[len(prefix):]
        first, sep, _ = remainder.partition('/')
        entries[first] = {'name': first, 'path': prefix + first, 'kind': 'directory' if sep else 'fit'}
    return {'path': str(path), 'folder': prefix.rstrip('/'), 'isZip': True, 'parent': str(path.parent),
            'entries': sorted(entries.values(), key=lambda x: (x['kind'] != 'directory', x['name']))}

def fit_ids(path, folder='', selected=None):
    if path.is_dir():
        available = {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file() and p.suffix.lower() == '.fit'}
    else:
        with zipfile.ZipFile(path) as archive:
            available = set(zip_members(archive))
        prefix = folder.strip('/')
        if prefix:
            available = {name for name in available if name.startswith(prefix + '/')}
    if selected is not None:
        if not set(selected) <= available:
            raise DatasetPathError('Selezione FIT non appartenente alla cartella scelta')
        available = set(selected)
    return sorted(available)

def read_source_fit(path, activity_id):
    logical = Path(str(path) + '!' + activity_id) if path.is_file() else path / activity_id
    try:
        if path.is_dir():
            return read_fit_activity((path / activity_id).resolve(strict=True))
        with zipfile.ZipFile(path) as archive:
            item = zip_members(archive)[activity_id]
            if item.file_size > MAX_FIT_BYTES:
                raise DatasetPathError('Voce FIT oltre il limite di 256 MiB')
            data = archive.read(item)
            if stat.S_ISLNK(item.external_attr >> 16):
                target_text = data.decode('utf-8').strip()
                target = Path(target_text)
                if not target.is_absolute():
                    target = path.parent / PurePosixPath(activity_id).parent / target
                if not target.is_file():
                    raise DatasetPathError(f'Lo ZIP contiene un collegamento: FIT sorgente non trovato ({target_text})')
                return read_fit_activity(target.resolve(strict=True))
        if len(data) < 12 or data[8:12] != b'.FIT':
            raise DatasetPathError('La voce ZIP non contiene dati FIT: firma .FIT assente')
        with fitdecode.FitReader(BytesIO(data)) as reader:
            return collect_activity(logical, (f for f in reader if f.frame_type == fitdecode.FIT_FRAME_DATA))
    except Exception as exc:
        return FitActivity(logical, pd.DataFrame(), {}, {}, str(exc))
