from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from power_hr_eda.fit_reader import collect_activity, read_fit_activity


@dataclass
class FakeFrame:
    name: str
    fields: dict[str, object]


def ts(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_collects_original_record_values() -> None:
    frames = [
        FakeFrame("file_id", {"manufacturer": "garmin"}),
        FakeFrame("record", {"timestamp": ts(0), "power": 210, "heart_rate": 142}),
        FakeFrame("record", {"timestamp": ts(1), "power": 0, "heart_rate": 143}),
    ]

    activity = collect_activity(Path("ride.fit"), frames)

    assert activity.records["power"].tolist() == [210, 0]
    assert activity.records["heart_rate"].tolist() == [142, 143]
    assert activity.message_counts == {"file_id": 1, "record": 2}
    assert activity.parse_error is None


def test_corrupt_fit_returns_inventory_error() -> None:
    generated = Path(__file__).parent / "_generated"
    generated.mkdir(exist_ok=True)
    path = generated / "broken.fit"
    try:
        path.write_bytes(b"not-a-fit")
        activity = read_fit_activity(path)
        assert activity.records.empty
        assert activity.parse_error
    finally:
        path.unlink(missing_ok=True)


def test_activity_without_records_is_retained() -> None:
    activity = collect_activity(
        Path("empty.fit"), [FakeFrame("session", {"sport": "cycling"})]
    )

    assert activity.message_counts == {"session": 1}
    assert activity.records.empty
    assert activity.messages["session"][0]["sport"] == "cycling"
