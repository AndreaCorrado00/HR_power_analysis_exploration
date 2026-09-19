from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from power_hr_eda.dataset import build_dataset_summary
from power_hr_eda.fit_reader import FitActivity


def activity(name: str, records: list[dict[str, object]], error: str | None = None) -> FitActivity:
    frame = pd.DataFrame(records)
    return FitActivity(
        path=Path(name),
        records=frame,
        messages={},
        message_counts={"record": len(frame)} if len(frame) else {},
        parse_error=error,
    )


def timestamps(count: int) -> list[datetime]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(seconds=i) for i in range(count)]


def test_inventory_retains_good_empty_and_corrupt_files() -> None:
    good = activity(
        "good.fit",
        [
            {"timestamp": timestamps(2)[0], "power": 100, "heart_rate": 120},
            {"timestamp": timestamps(2)[1], "power": 200, "heart_rate": 125},
        ],
    )
    empty = activity("empty.fit", [])
    corrupt = activity("corrupt.fit", [], "FitHeaderError: invalid")

    summary = build_dataset_summary([good, empty, corrupt])

    assert len(summary.inventory) == 3
    assert summary.inventory["parse_error"].notna().sum() == 1
    assert summary.inventory["record_count"].tolist() == [2, 0, 0]


def test_field_coverage_separates_session_and_record_denominators() -> None:
    with_power = activity(
        "power.fit",
        [
            {"timestamp": timestamps(2)[0], "power": 100},
            {"timestamp": timestamps(2)[1], "power": 200},
        ],
    )
    without_power = activity("other.fit", [{"timestamp": timestamps(1)[0], "cadence": 80}])

    summary = build_dataset_summary([with_power, without_power])
    row = summary.field_coverage.set_index("field").loc["power"]

    assert row["session_observed_count"] == 1
    assert row["session_fraction"] == 0.5
    assert row["record_observed_count"] == 2
    assert row["record_fraction"] == 2 / 3


def test_monthly_volume_uses_observed_timestamp_span() -> None:
    start = datetime(2026, 2, 3, tzinfo=timezone.utc)
    records = [
        {"timestamp": start, "power": 100},
        {"timestamp": start + timedelta(seconds=90), "power": 120},
    ]

    summary = build_dataset_summary([activity("ride.fit", records)])

    assert summary.monthly_volume.loc[0, "month"] == "2026-02"
    assert summary.monthly_volume.loc[0, "activity_count"] == 1
    assert summary.monthly_volume.loc[0, "observed_span_s"] == 90


def test_inventory_preserves_fit_session_metrics_and_derives_work() -> None:
    start = datetime(2026, 2, 3, tzinfo=timezone.utc)
    fit_activity = FitActivity(
        path=Path("ride.fit"),
        records=pd.DataFrame(
            [
                {"timestamp": start, "power": 100.0},
                {"timestamp": start + timedelta(seconds=1), "power": 200.0},
                {"timestamp": start + timedelta(seconds=3), "power": 300.0},
            ]
        ),
        messages={"session": [{"total_distance": 12_300.0, "total_ascent": 450.0}]},
        message_counts={"record": 3, "session": 1},
    )

    row = build_dataset_summary([fit_activity]).inventory.iloc[0]

    assert row["fit_total_distance_m"] == 12_300.0
    assert row["fit_total_ascent_m"] == 450.0
    assert row["derived_work_kj"] == 0.5


def test_excludes_unavailable_left_right_balance_from_eda_outputs() -> None:
    records = pd.DataFrame(
        {
            "timestamp": timestamps(2),
            "power": [100.0, 120.0],
            "left_right_balance": [0.0, 0.0],
        }
    )

    summary = build_dataset_summary([activity("ride.fit", records.to_dict("records"))])

    assert "left_right_balance" not in summary.field_coverage["field"].tolist()
    assert "left_right_balance" not in summary.signal_quality["field"].tolist()
    assert "left_right_balance" not in summary.signal_distributions["field"].tolist()


def test_inventory_records_longest_hr_plateau_and_duplicate_aliases() -> None:
    start = datetime(2026, 8, 21, tzinfo=timezone.utc)
    records = pd.DataFrame(
        {
            "timestamp": [start + timedelta(seconds=i) for i in range(6)],
            "heart_rate": [100, 93, 93, 93, 110, 111],
            "power": [100, 110, 120, 130, 140, 150],
            "altitude": [10, 11, 12, 13, 14, 15],
            "enhanced_altitude": [10, 11, 12, 13, 14, 15],
            "speed": [5, 6, 7, 8, 9, 10],
            "enhanced_speed": [5, 6, 7, 8, 9, 10],
        }
    )

    row = build_dataset_summary(
        [FitActivity(Path("ride.fit"), records, {}, {"record": 6})]
    ).inventory.iloc[0]

    assert row["heart_rate_longest_run_samples"] == 3
    assert row["heart_rate_longest_run_value"] == 93
    assert row["heart_rate_longest_run_start"] == start + timedelta(seconds=1)
    assert row["heart_rate_longest_run_end"] == start + timedelta(seconds=3)
    assert row["altitude_alias_mismatch_count"] == 0
    assert row["speed_alias_mismatch_count"] == 0
    assert row["power_observed_count"] == 6
