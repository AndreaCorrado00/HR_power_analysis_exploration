from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class LapBoundary:
    index: int
    start_time: datetime
    end_time: datetime

@dataclass(frozen=True)
class ActivitySummary:
    activity_id: str
    source_path: str
    start_time: datetime | None
    end_time: datetime | None
    duration_seconds: float
    record_count: int
    has_power: bool
    has_heart_rate: bool
    laps: tuple[LapBoundary, ...]
    parse_error: str | None = None
    @property
    def extractable(self) -> bool: return bool(self.laps) and self.parse_error is None
    @property
    def exclusion_reason(self) -> str | None:
        if self.parse_error: return f"FIT non leggibile: {self.parse_error}"
        if not self.laps: return "Nessun lap FIT utilizzabile"
        return None

@dataclass(frozen=True)
class SegmentSelection:
    activity_id: str
    first_lap: int
    last_lap: int
