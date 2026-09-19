from __future__ import annotations

import numpy as np
import pandas as pd


def lagged_correlations(
    records: pd.DataFrame,
    max_lag_s: int = 120,
    min_pairs: int = 60,
) -> pd.DataFrame:
    columns = ["lag_s", "pair_count", "correlation"]
    required = {"timestamp", "power", "heart_rate"}
    if not required.issubset(records.columns):
        return pd.DataFrame(columns=columns)

    base = records.loc[:, ["timestamp", "power", "heart_rate"]].copy()
    base["timestamp"] = pd.to_datetime(base["timestamp"], utc=True, errors="coerce")
    base["power"] = pd.to_numeric(base["power"], errors="coerce")
    base["heart_rate"] = pd.to_numeric(base["heart_rate"], errors="coerce")

    power = base.loc[base["power"].notna(), ["timestamp", "power"]].dropna()
    hr = base.loc[base["heart_rate"].notna(), ["timestamp", "heart_rate"]].dropna()
    if power.empty or hr.empty:
        return pd.DataFrame(columns=columns)

    power = power.loc[~power["timestamp"].duplicated(keep=False)]
    hr = hr.loc[~hr["timestamp"].duplicated(keep=False)]
    rows: list[dict[str, object]] = []
    for lag_s in range(-int(max_lag_s), int(max_lag_s) + 1):
        shifted_hr = hr.copy()
        shifted_hr["timestamp"] = shifted_hr["timestamp"] - pd.to_timedelta(
            lag_s, unit="s"
        )
        paired = power.merge(shifted_hr, on="timestamp", how="inner")
        correlation: float | None = None
        if (
            len(paired) >= min_pairs
            and paired["power"].nunique() > 1
            and paired["heart_rate"].nunique() > 1
        ):
            value = paired["power"].corr(paired["heart_rate"])
            if pd.notna(value):
                correlation = float(value)
        rows.append(
            {
                "lag_s": lag_s,
                "pair_count": int(len(paired)),
                "correlation": correlation,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def summarize_apparent_lag(curve: pd.DataFrame) -> dict[str, object]:
    if curve.empty or "correlation" not in curve or curve["correlation"].isna().all():
        return {
            "apparent_lag_s": None,
            "max_correlation": None,
            "pair_count_at_max": None,
        }
    index = curve["correlation"].idxmax()
    row = curve.loc[index]
    return {
        "apparent_lag_s": int(row["lag_s"]),
        "max_correlation": float(np.round(row["correlation"], 12)),
        "pair_count_at_max": int(row["pair_count"]),
    }
