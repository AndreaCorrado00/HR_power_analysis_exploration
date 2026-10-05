"""Repository sources, including the existing road-data directory alias."""
import os
from pathlib import Path


def dataset_path(path, root):
    root = Path(root).resolve()
    logical = Path(os.path.abspath(path))
    if not logical.is_relative_to(root):
        raise ValueError('Selezionare una sorgente in dataset/')
    resolved = logical.resolve()
    if resolved.is_relative_to(root):
        return resolved
    # This repository stores its road FITs through this directory symlink.
    raw = root/'raw/only_road_activities'
    if logical.is_relative_to(raw) and raw.is_dir() and resolved.is_relative_to(raw.resolve()):
        return resolved
    raise ValueError('Collegamento fuori dalle sorgenti di dataset/')
