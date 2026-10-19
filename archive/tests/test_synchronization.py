from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from power_hr_eda.synchronization import lagged_correlations, summarize_apparent_lag


def second_records(power: np.ndarray, heart_rate: np.ndarray) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(seconds=i) for i in range(len(power))],
            "power": power,
            "heart_rate": heart_rate,
        }
    )


def test_positive_lag_means_heart_rate_follows_power() -> None:
    rng = np.random.default_rng(42)
    power = rng.normal(size=360)
    heart_rate = np.r_[np.full(5, np.nan), power[:-5]]

    curve = lagged_correlations(second_records(power, heart_rate), max_lag_s=10)
    summary = summarize_apparent_lag(curve)

    assert int(curve.loc[curve["correlation"].idxmax(), "lag_s"]) == 5
    assert summary["apparent_lag_s"] == 5
    assert summary["max_correlation"] == 1.0


def test_lag_curve_is_empty_without_joint_signal() -> None:
    records = second_records(np.array([1.0, 2.0, 3.0]), np.full(3, np.nan))

    curve = lagged_correlations(records)

    assert curve.empty
    assert summarize_apparent_lag(curve)["apparent_lag_s"] is None


def test_constant_signal_has_no_defined_correlation() -> None:
    records = second_records(np.ones(100), np.arange(100, dtype=float))

    curve = lagged_correlations(records, max_lag_s=5, min_pairs=20)

    assert curve["correlation"].isna().all()
