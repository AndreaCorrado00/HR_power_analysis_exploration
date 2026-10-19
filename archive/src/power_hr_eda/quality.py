from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _as_python(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def summarize_timing(records: pd.DataFrame) -> dict[str, object]:
    empty = {
        "record_count": int(len(records)),
        "timestamp_observed_count": 0,
        "dt_zero_count": 0,
        "dt_negative_count": 0,
        "dt_positive_count": 0,
        "dt_over_2s_count": 0,
        "dt_over_5s_count": 0,
        "dt_over_10s_count": 0,
        "dt_over_30s_count": 0,
        "dt_median_positive_s": None,
        "dt_p95_positive_s": None,
        "dt_max_positive_s": None,
    }
    if "timestamp" not in records:
        return empty

    timestamps = pd.to_datetime(records["timestamp"], utc=True, errors="coerce")
    empty["timestamp_observed_count"] = int(timestamps.notna().sum())
    deltas = timestamps.diff().dt.total_seconds().dropna()
    positive = deltas[deltas > 0]
    empty.update(
        {
            "dt_zero_count": int((deltas == 0).sum()),
            "dt_negative_count": int((deltas < 0).sum()),
            "dt_positive_count": int((deltas > 0).sum()),
            "dt_over_2s_count": int((positive > 2).sum()),
            "dt_over_5s_count": int((positive > 5).sum()),
            "dt_over_10s_count": int((positive > 10).sum()),
            "dt_over_30s_count": int((positive > 30).sum()),
        }
    )
    if not positive.empty:
        empty.update(
            {
                "dt_median_positive_s": float(positive.median()),
                "dt_p95_positive_s": float(positive.quantile(0.95)),
                "dt_max_positive_s": float(positive.max()),
            }
        )
    return empty


def _longest_constant_run(series: pd.Series) -> int:
    longest = current = 0
    previous: object = object()
    have_previous = False
    for value in series:
        if pd.isna(value):
            current = 0
            have_previous = False
            continue
        if have_previous and value == previous:
            current += 1
        else:
            current = 1
        previous = value
        have_previous = True
        longest = max(longest, current)
    return longest


def summarize_signal(records: pd.DataFrame, column: str) -> dict[str, object]:
    series = records[column] if column in records else pd.Series([np.nan] * len(records))
    numeric = pd.to_numeric(series, errors="coerce")
    observed = numeric.dropna()
    result: dict[str, object] = {
        "field": column,
        "row_count": int(len(records)),
        "observed_count": int(observed.size),
        "missing_count": int(numeric.isna().sum()),
        "zero_count": int((observed == 0).sum()),
        "zero_fraction_observed": None,
        "longest_constant_run_samples": _longest_constant_run(numeric),
        "min": None,
        "p05": None,
        "median": None,
        "p95": None,
        "max": None,
    }
    if observed.empty:
        return result
    result.update(
        {
            "zero_fraction_observed": float((observed == 0).mean()),
            "min": _as_python(observed.min()),
            "p05": float(observed.quantile(0.05)),
            "median": float(observed.median()),
            "p95": float(observed.quantile(0.95)),
            "max": _as_python(observed.max()),
        }
    )
    return result


def summarize_joint_coverage(records: pd.DataFrame) -> dict[str, object]:
    if not {"power", "heart_rate"}.issubset(records.columns):
        return {
            "joint_observed_count": 0,
            "joint_observed_fraction": None,
        }
    if records.empty:
        return {
            "joint_observed_count": 0,
            "joint_observed_fraction": None,
        }
    joint = records["power"].notna() & records["heart_rate"].notna()
    return {
        "joint_observed_count": int(joint.sum()),
        "joint_observed_fraction": float(joint.mean()),
    }
