from datetime import datetime, timezone

from backend.domain import ActivitySummary, LapBoundary


def test_activity_summary_marks_missing_laps_as_excluded() -> None:
    activity = ActivitySummary(
        activity_id="ride.fit", source_path="ride.fit", start_time=None,
        end_time=None, duration_seconds=3600.0, record_count=3601,
        has_power=True, has_heart_rate=True, laps=(), parse_error=None,
    )
    assert activity.extractable is False
    assert activity.exclusion_reason == "Nessun lap FIT utilizzabile"


def test_activity_summary_with_a_valid_lap_is_extractable() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    activity = ActivitySummary(
        activity_id="ride.fit", source_path="ride.fit", start_time=start,
        end_time=start, duration_seconds=0.0, record_count=1,
        has_power=True, has_heart_rate=True,
        laps=(LapBoundary(1, start, start),), parse_error=None,
    )
    assert activity.extractable is True
    assert activity.exclusion_reason is None
