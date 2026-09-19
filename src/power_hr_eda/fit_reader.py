from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitdecode
import pandas as pd


@dataclass(frozen=True)
class FitActivity:
    path: Path
    records: pd.DataFrame
    messages: dict[str, list[dict[str, object]]]
    message_counts: dict[str, int]
    parse_error: str | None = None


def _frame_values(frame: object) -> dict[str, object]:
    fields = getattr(frame, "fields", {})
    if isinstance(fields, dict):
        return dict(fields)

    values: dict[str, object] = {}
    duplicate_counts: Counter[str] = Counter()
    for field in fields:
        base_name = str(getattr(field, "name", None) or getattr(field, "def_num", "field"))
        duplicate_counts[base_name] += 1
        name = base_name
        if duplicate_counts[base_name] > 1:
            name = f"{base_name}__{duplicate_counts[base_name]}"
        values[name] = getattr(field, "value", None)
    return values


def collect_activity(path: Path, frames: Iterable[object]) -> FitActivity:
    messages: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    counts: Counter[str] = Counter()

    for frame in frames:
        name = getattr(frame, "name", None)
        if not name:
            continue
        values = _frame_values(frame)
        messages[str(name)].append(values)
        counts[str(name)] += 1

    records = pd.DataFrame(messages.get("record", []))
    return FitActivity(
        path=Path(path),
        records=records,
        messages=dict(messages),
        message_counts=dict(counts),
    )


def read_fit_activity(path: Path) -> FitActivity:
    path = Path(path)
    try:
        with fitdecode.FitReader(path) as reader:
            frames = (
                frame
                for frame in reader
                if getattr(frame, "frame_type", None) == fitdecode.FIT_FRAME_DATA
            )
            return collect_activity(path, frames)
    except Exception as exc:
        return FitActivity(
            path=path,
            records=pd.DataFrame(),
            messages={},
            message_counts={},
            parse_error=f"{type(exc).__name__}: {exc}",
        )
