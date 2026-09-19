from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .fit_reader import FitActivity
from .quality import summarize_joint_coverage, summarize_signal, summarize_timing
from .synchronization import lagged_correlations, summarize_apparent_lag


EXCLUDED_RECORD_FIELDS = {"left_right_balance"}


@dataclass(frozen=True)
class DatasetSummary:
    activities: tuple[FitActivity, ...]
    inventory: pd.DataFrame
    field_coverage: pd.DataFrame
    timing: pd.DataFrame
    signal_quality: pd.DataFrame
    monthly_volume: pd.DataFrame
    signal_distributions: pd.DataFrame
    lag_summary: pd.DataFrame
    lag_curves: dict[str, pd.DataFrame]
    message_types: pd.DataFrame


def _first_message(activity: FitActivity, name: str) -> dict[str, object]:
    values = activity.messages.get(name, [])
    return values[0] if values else {}


def _timestamp_bounds(records: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if "timestamp" not in records or records.empty:
        return None, None
    timestamps = pd.to_datetime(records["timestamp"], utc=True, errors="coerce").dropna()
    if timestamps.empty:
        return None, None
    return timestamps.min(), timestamps.max()


def _longest_run_detail(records: pd.DataFrame, field: str) -> dict[str, object]:
    empty = {
        f"{field}_longest_run_samples": 0,
        f"{field}_longest_run_value": None,
        f"{field}_longest_run_start": None,
        f"{field}_longest_run_end": None,
    }
    if field not in records or records.empty:
        return empty
    values = records[field]
    valid = values.notna()
    groups = (values.ne(values.shift()) | ~valid).cumsum()
    candidates = records.loc[valid, ["timestamp"]].copy() if "timestamp" in records else pd.DataFrame(index=records.index[valid])
    candidates["value"] = values.loc[valid]
    candidates["group"] = groups.loc[valid]
    if candidates.empty:
        return empty
    aggregate = candidates.groupby("group", sort=False).agg(
        value=("value", "first"),
        samples=("value", "size"),
        start=("timestamp", "first") if "timestamp" in candidates else ("value", lambda _: None),
        end=("timestamp", "last") if "timestamp" in candidates else ("value", lambda _: None),
    )
    row = aggregate.loc[aggregate["samples"].idxmax()]
    return {
        f"{field}_longest_run_samples": int(row["samples"]),
        f"{field}_longest_run_value": row["value"],
        f"{field}_longest_run_start": row["start"],
        f"{field}_longest_run_end": row["end"],
    }


def _alias_diagnostics(records: pd.DataFrame, first: str, second: str, prefix: str) -> dict[str, int]:
    if not {first, second}.issubset(records.columns):
        return {f"{prefix}_alias_pair_count": 0, f"{prefix}_alias_mismatch_count": 0}
    pair = records[[first, second]].dropna()
    return {
        f"{prefix}_alias_pair_count": int(len(pair)),
        f"{prefix}_alias_mismatch_count": int(pair[first].ne(pair[second]).sum()),
    }


def _inventory_row(activity: FitActivity) -> dict[str, object]:
    start, end = _timestamp_bounds(activity.records)
    session = _first_message(activity, "session")
    path = activity.path
    derived_work_kj = None
    if {"timestamp", "power"}.issubset(activity.records.columns):
        timestamps = pd.to_datetime(activity.records["timestamp"], utc=True, errors="coerce")
        power = pd.to_numeric(activity.records["power"], errors="coerce")
        forward_dt = (timestamps.shift(-1) - timestamps).dt.total_seconds()
        valid = forward_dt.gt(0) & power.notna()
        if valid.any():
            derived_work_kj = float((power[valid] * forward_dt[valid]).sum() / 1000)
    return {
        "activity_id": path.stem,
        "source_file": path.name,
        "source_path": str(path),
        "file_size_bytes": path.stat().st_size if path.exists() else None,
        "parse_error": activity.parse_error,
        "record_count": int(len(activity.records)),
        "start_time": start,
        "end_time": end,
        "observed_span_s": float((end - start).total_seconds()) if start is not None and end is not None else None,
        "fit_total_elapsed_time_s": session.get("total_elapsed_time"),
        "fit_total_timer_time_s": session.get("total_timer_time"),
        "fit_total_distance_m": session.get("total_distance"),
        "fit_total_ascent_m": session.get("total_ascent"),
        "fit_total_descent_m": session.get("total_descent"),
        "fit_avg_speed_m_s": session.get("avg_speed"),
        "fit_max_speed_m_s": session.get("max_speed"),
        "fit_avg_power_w": session.get("avg_power"),
        "fit_max_power_w": session.get("max_power"),
        "fit_avg_heart_rate_bpm": session.get("avg_heart_rate"),
        "fit_max_heart_rate_bpm": session.get("max_heart_rate"),
        "fit_avg_cadence_rpm": session.get("avg_cadence"),
        "fit_max_cadence_rpm": session.get("max_cadence"),
        "derived_work_kj": derived_work_kj,
        "sport": session.get("sport"),
        "sub_sport": session.get("sub_sport"),
        "record_field_count": int(len(activity.records.columns)),
        "power_observed_count": int(activity.records["power"].notna().sum()) if "power" in activity.records else 0,
        "heart_rate_observed_count": int(activity.records["heart_rate"].notna().sum()) if "heart_rate" in activity.records else 0,
        **_longest_run_detail(activity.records, "heart_rate"),
        **_alias_diagnostics(activity.records, "altitude", "enhanced_altitude", "altitude"),
        **_alias_diagnostics(activity.records, "speed", "enhanced_speed", "speed"),
        **summarize_joint_coverage(activity.records),
    }


def _build_field_coverage(activities: tuple[FitActivity, ...]) -> pd.DataFrame:
    fields = sorted(
        {
            column
            for a in activities
            for column in a.records.columns
            if column not in EXCLUDED_RECORD_FIELDS
        }
    )
    total_sessions = len(activities)
    total_records = sum(len(a.records) for a in activities)
    rows = []
    for field in fields:
        session_observed = sum(
            int(field in a.records and a.records[field].notna().any()) for a in activities
        )
        record_observed = sum(
            int(a.records[field].notna().sum()) for a in activities if field in a.records
        )
        rows.append(
            {
                "field": field,
                "session_observed_count": session_observed,
                "session_denominator": total_sessions,
                "session_fraction": session_observed / total_sessions if total_sessions else None,
                "record_observed_count": record_observed,
                "record_denominator": total_records,
                "record_fraction": record_observed / total_records if total_records else None,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "field",
            "session_observed_count",
            "session_denominator",
            "session_fraction",
            "record_observed_count",
            "record_denominator",
            "record_fraction",
        ],
    )


def _numeric_fields(activities: tuple[FitActivity, ...]) -> list[str]:
    excluded = {"timestamp", "position_lat", "position_long", *EXCLUDED_RECORD_FIELDS}
    fields: set[str] = set()
    for activity in activities:
        for column in activity.records.columns:
            if column in excluded:
                continue
            values = pd.to_numeric(activity.records[column], errors="coerce")
            if values.notna().any():
                fields.add(column)
    return sorted(fields)


def _pooled_values(activities: tuple[FitActivity, ...], field: str) -> pd.Series:
    parts = [
        pd.to_numeric(a.records[field], errors="coerce")
        for a in activities
        if field in a.records
    ]
    return pd.concat(parts, ignore_index=True).dropna() if parts else pd.Series(dtype=float)


def build_dataset_summary(activities: Iterable[FitActivity]) -> DatasetSummary:
    items = tuple(activities)
    inventory = pd.DataFrame([_inventory_row(activity) for activity in items])
    timing_rows = []
    quality_rows = []
    lag_rows = []
    lag_curves: dict[str, pd.DataFrame] = {}
    numeric_fields = _numeric_fields(items)

    for activity in items:
        activity_id = activity.path.stem
        timing_rows.append({"activity_id": activity_id, **summarize_timing(activity.records)})
        for field in numeric_fields:
            quality_rows.append(
                {"activity_id": activity_id, **summarize_signal(activity.records, field)}
            )
        curve = lagged_correlations(activity.records)
        lag_curves[activity_id] = curve
        lag_rows.append({"activity_id": activity_id, **summarize_apparent_lag(curve)})

    distributions = []
    for field in numeric_fields:
        values = _pooled_values(items, field)
        distributions.append(
            {
                "field": field,
                "observed_count": int(len(values)),
                "min": float(values.min()) if len(values) else None,
                "p05": float(values.quantile(0.05)) if len(values) else None,
                "median": float(values.median()) if len(values) else None,
                "mean": float(values.mean()) if len(values) else None,
                "p95": float(values.quantile(0.95)) if len(values) else None,
                "max": float(values.max()) if len(values) else None,
            }
        )

    monthly = pd.DataFrame()
    if not inventory.empty and inventory["start_time"].notna().any():
        monthly_source = inventory.loc[inventory["start_time"].notna()].copy()
        monthly_source["month"] = pd.to_datetime(monthly_source["start_time"], utc=True).dt.strftime("%Y-%m")
        monthly = (
            monthly_source.groupby("month", as_index=False)
            .agg(activity_count=("activity_id", "count"), observed_span_s=("observed_span_s", "sum"))
            .sort_values("month")
            .reset_index(drop=True)
        )

    message_rows = [
        {"activity_id": a.path.stem, "message_type": name, "message_count": count}
        for a in items
        for name, count in sorted(a.message_counts.items())
    ]
    return DatasetSummary(
        activities=items,
        inventory=inventory,
        field_coverage=_build_field_coverage(items),
        timing=pd.DataFrame(timing_rows),
        signal_quality=pd.DataFrame(quality_rows),
        monthly_volume=monthly,
        signal_distributions=pd.DataFrame(distributions),
        lag_summary=pd.DataFrame(lag_rows),
        lag_curves=lag_curves,
        message_types=pd.DataFrame(message_rows),
    )


def export_summary_tables(summary: DatasetSummary, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "activity_inventory": summary.inventory,
        "field_coverage": summary.field_coverage,
        "timing_quality": summary.timing,
        "signal_quality": summary.signal_quality,
        "monthly_volume": summary.monthly_volume,
        "signal_distributions": summary.signal_distributions,
        "lag_summary": summary.lag_summary,
        "message_types": summary.message_types,
    }
    paths = []
    for name, frame in tables.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
        paths.append(path)
    return paths
