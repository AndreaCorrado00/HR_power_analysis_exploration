"""Local source and export locations selected by the athlete-workspace launcher."""
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException


def source_root(repo_root):
    return Path(os.environ.get('HR_POWER_SOURCE') or Path(repo_root) / 'dataset').expanduser().resolve()


def export_directory():
    value = os.environ.get('HR_POWER_EXPORTS')
    return Path(value).expanduser().resolve() if value else None


def export_headers(blob, filename, directory):
    """Keep the download and, when configured, archive a distinct copy in Y."""
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    if directory is not None:
        name = Path(filename).name
        path = directory / f'{Path(name).stem}_{uuid4().hex}{Path(name).suffix}'
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(blob)
        except OSError as exc:
            raise HTTPException(400, f'Impossibile salvare export in {directory}: {exc}') from exc
        # HTTP headers are Latin-1; the actual path can contain Unicode.
        from urllib.parse import quote
        headers['X-Export-Path'] = quote(str(path))
    return headers
