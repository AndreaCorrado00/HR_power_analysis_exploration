from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .fit_reader import FitActivity


CRITERIA = (
    {
        "criterion": "HR_NON_POSITIVE",
        "condition": "heart_rate <= 0 bpm",
        "rationale": "A non-positive heart rate is not physiologically compatible with a recorded cycling activity.",
    },
    {
        "criterion": "HR_EXTREME_HIGH",
        "condition": "heart_rate > 240 bpm",
        "rationale": "A deliberately permissive absolute ceiling avoids age-predicted HRmax formulas while flagging extreme values.",
    },
    {
        "criterion": "HR_RATE_OF_CHANGE",
        "condition": "abs(delta heart_rate) / delta time > 20 bpm/s for 0 < delta time <= 2 s",
        "rationale": "Changes faster than an exceptionally rapid sinus response are treated as discontinuities.",
    },
)


@dataclass(frozen=True)
class ExclusionResult:
    source_path: Path
    decision: str
    triggered_criteria: tuple[str, ...]
    flagged_indices: tuple[object, ...]
    violation_counts: dict[str, int]


def classify_heart_rate(activity: FitActivity) -> ExclusionResult:
    records = activity.records
    masks = {item["criterion"]: pd.Series(False, index=records.index) for item in CRITERIA}
    if "heart_rate" in records:
        heart_rate = pd.to_numeric(records["heart_rate"], errors="coerce")
        masks["HR_NON_POSITIVE"] = heart_rate.le(0) & heart_rate.notna()
        masks["HR_EXTREME_HIGH"] = heart_rate.gt(240) & heart_rate.notna()

        if "timestamp" in records:
            timestamp = pd.to_datetime(records["timestamp"], utc=True, errors="coerce")
            delta_time = timestamp.diff().dt.total_seconds()
            rate = heart_rate.diff().abs().div(delta_time)
            transitions = rate.gt(20) & delta_time.gt(0) & delta_time.le(2)
            rate_mask = transitions | transitions.shift(-1, fill_value=False)
            masks["HR_RATE_OF_CHANGE"] = rate_mask

    triggered = tuple(name for name, mask in masks.items() if bool(mask.any()))
    flagged = pd.Series(False, index=records.index)
    for mask in masks.values():
        flagged |= mask
    return ExclusionResult(
        source_path=activity.path,
        decision="DROP" if triggered else "KEEP",
        triggered_criteria=triggered,
        flagged_indices=tuple(records.index[flagged].tolist()),
        violation_counts={name: int(mask.sum()) for name, mask in masks.items()},
    )


def _result_row(result: ExclusionResult) -> dict[str, object]:
    return {
        "activity_id": result.source_path.stem,
        "source_file": result.source_path.name,
        "source_path": str(result.source_path),
        "decision": result.decision,
        "triggered_criteria": ";".join(result.triggered_criteria),
        "flagged_record_count": len(result.flagged_indices),
        **{f"{name.lower()}_count": count for name, count in result.violation_counts.items()},
    }


def _save_drop_plot(activity: FitActivity, result: ExclusionResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = activity.records
    heart_rate = pd.to_numeric(records["heart_rate"], errors="coerce")
    if "timestamp" in records:
        x = pd.to_datetime(records["timestamp"], utc=True, errors="coerce")
        xlabel = "Timestamp"
    else:
        x = pd.Series(range(len(records)), index=records.index)
        xlabel = "Record index"
    flagged = records.index.isin(result.flagged_indices)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.plot(x, heart_rate, color="#176B87", linewidth=0.9, label="Heart rate")
    ax.scatter(x[flagged], heart_rate[flagged], color="#C62828", s=34, zorder=3, label="Violazione hard check")
    for position in x[flagged]:
        if pd.notna(position):
            ax.axvline(position, color="#C62828", alpha=0.18, linewidth=1.5)
    ax.set_title(f"DROP {activity.path.name}: {', '.join(result.triggered_criteria)}", loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Heart rate (bpm)")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = output_dir / f"{activity.path.stem}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _create_keep_symlinks(results: list[ExclusionResult], cleaned_dir: Path) -> None:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    expected = {result.source_path.name for result in results if result.decision == "KEEP"}
    for existing in cleaned_dir.glob("*.fit"):
        if existing.name not in expected and existing.is_symlink():
            existing.unlink()
    for result in results:
        if result.decision != "KEEP":
            continue
        link = cleaned_dir / result.source_path.name
        if link.is_symlink() and link.resolve() == result.source_path.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise FileExistsError(f"Refusing to replace non-matching cleaned entry: {link}")
        relative_target = os.path.relpath(result.source_path.resolve(), start=cleaned_dir.resolve())
        link.symlink_to(relative_target)


def run_exclusion_analysis(
    activities: Iterable[FitActivity],
    tables_dir: Path,
    images_dir: Path,
    cleaned_dir: Path,
) -> pd.DataFrame:
    items = list(activities)
    results = [classify_heart_rate(activity) for activity in items]
    frame = pd.DataFrame([_result_row(result) for result in results])
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(CRITERIA).to_csv(tables_dir / "exclusion_criteria.csv", index=False)
    frame.to_csv(tables_dir / "fit_exclusion_results.csv", index=False)
    frame.loc[frame["decision"] == "KEEP"].to_csv(tables_dir / "keep_files.csv", index=False)
    frame.loc[frame["decision"] == "DROP"].to_csv(tables_dir / "drop_files.csv", index=False)

    by_path = {activity.path: activity for activity in items}
    expected_plots = {
        f"{result.source_path.stem}.png" for result in results if result.decision == "DROP"
    }
    images_dir.mkdir(parents=True, exist_ok=True)
    for existing in images_dir.glob("*.png"):
        if existing.name not in expected_plots:
            existing.unlink()
    for result in results:
        if result.decision == "DROP":
            _save_drop_plot(by_path[result.source_path], result, images_dir)
    _create_keep_symlinks(results, cleaned_dir)
    return frame
