from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from power_hr_eda.quality import (
    summarize_joint_coverage,
    summarize_signal,
    summarize_timing,
)


def frame_at_seconds(seconds: list[int]) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return pd.DataFrame({"timestamp": [start + timedelta(seconds=x) for x in seconds]})


def test_timing_separates_duplicate_negative_and_long_intervals() -> None:
    result = summarize_timing(frame_at_seconds([0, 1, 1, 0, 8]))

    assert result["dt_zero_count"] == 1
    assert result["dt_negative_count"] == 1
    assert result["dt_over_5s_count"] == 1
    assert result["dt_median_positive_s"] == 4.5


def test_signal_summary_distinguishes_missing_zero_and_constant_runs() -> None:
    records = pd.DataFrame({"power": [100.0, 0.0, 0.0, np.nan, 250.0]})

    result = summarize_signal(records, "power")

    assert result["observed_count"] == 4
    assert result["missing_count"] == 1
    assert result["zero_count"] == 2
    assert result["longest_constant_run_samples"] == 2
    assert result["median"] == 50.0


def test_absent_signal_returns_explicitly_undefined_statistics() -> None:
    result = summarize_signal(pd.DataFrame({"cadence": [80, 90]}), "power")

    assert result["observed_count"] == 0
    assert result["missing_count"] == 2
    assert result["median"] is None
    assert result["zero_fraction_observed"] is None


def test_joint_coverage_is_unavailable_when_hr_column_is_absent() -> None:
    result = summarize_joint_coverage(pd.DataFrame({"power": [100, 200]}))

    assert result["joint_observed_count"] == 0
    assert result["joint_observed_fraction"] is None


def test_joint_coverage_uses_all_rows_as_denominator() -> None:
    records = pd.DataFrame(
        {"power": [100.0, np.nan, 200.0], "heart_rate": [120.0, 121.0, np.nan]}
    )

    result = summarize_joint_coverage(records)

    assert result["joint_observed_count"] == 1
    assert result["joint_observed_fraction"] == 1 / 3
