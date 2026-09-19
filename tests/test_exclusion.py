from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

import power_hr_eda.exclusion as exclusion
from power_hr_eda.exclusion import classify_heart_rate, run_exclusion_analysis
from power_hr_eda.fit_reader import FitActivity


GENERATED = Path(__file__).parent / "_generated" / "exclusion"


def records(heart_rate: list[float], seconds: list[float] | None = None) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    elapsed = seconds if seconds is not None else list(range(len(heart_rate)))
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(seconds=value) for value in elapsed],
            "heart_rate": heart_rate,
        }
    )


def activity(path: Path, heart_rate: list[float], seconds: list[float] | None = None) -> FitActivity:
    frame = records(heart_rate, seconds)
    return FitActivity(path, frame, {}, {"record": len(frame)})


def test_non_positive_value_drops_the_entire_file() -> None:
    result = classify_heart_rate(activity(Path("zero.fit"), [120, 0, 121], [0, 4, 8]))

    assert result.decision == "DROP"
    assert result.triggered_criteria == ("HR_NON_POSITIVE",)
    assert result.flagged_indices == (1,)


def test_values_above_240_are_dropped_but_boundary_is_kept() -> None:
    keep = classify_heart_rate(activity(Path("boundary.fit"), [120, 240, 121], [0, 4, 8]))
    drop = classify_heart_rate(activity(Path("high.fit"), [120, 241, 121], [0, 4, 8]))

    assert keep.decision == "KEEP"
    assert drop.decision == "DROP"
    assert drop.triggered_criteria == ("HR_EXTREME_HIGH",)


def test_rate_change_uses_only_consecutive_samples_up_to_two_seconds_apart() -> None:
    drop = classify_heart_rate(activity(Path("jump.fit"), [100, 121], [0, 1]))
    boundary = classify_heart_rate(activity(Path("boundary.fit"), [100, 120], [0, 1]))
    gap = classify_heart_rate(activity(Path("gap.fit"), [100, 180], [0, 4]))

    assert drop.decision == "DROP"
    assert drop.triggered_criteria == ("HR_RATE_OF_CHANGE",)
    assert drop.flagged_indices == (0, 1)
    assert boundary.decision == "KEEP"
    assert gap.decision == "KEEP"


def test_missing_heart_rate_does_not_trigger_a_physiological_exclusion() -> None:
    result = classify_heart_rate(activity(Path("missing.fit"), [120, float("nan"), 121]))

    assert result.decision == "KEEP"
    assert result.triggered_criteria == ()


def test_analysis_exports_tables_and_drop_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = GENERATED / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    keep_path = raw / "keep.fit"
    drop_path = raw / "drop.fit"
    keep_path.write_bytes(b"keep")
    drop_path.write_bytes(b"drop")
    tables = GENERATED / "tables"
    images = GENERATED / "images"
    cleaned = GENERATED / "cleaned"
    images.mkdir(parents=True, exist_ok=True)
    stale_plot = images / "stale.png"
    stale_plot.write_bytes(b"stale")
    monkeypatch.setattr(exclusion, "_create_keep_symlinks", lambda results, output: None)

    results = run_exclusion_analysis(
        [activity(keep_path, [100, 110]), activity(drop_path, [100, 0])],
        tables,
        images,
        cleaned,
    )

    assert results["decision"].tolist() == ["KEEP", "DROP"]
    assert (tables / "exclusion_criteria.csv").exists()
    assert (tables / "fit_exclusion_results.csv").exists()
    assert (tables / "keep_files.csv").exists()
    assert (tables / "drop_files.csv").exists()
    assert (images / "drop.png").exists()
    assert not stale_plot.exists()


def test_analysis_creates_relative_symlink_for_keep_file() -> None:
    raw = GENERATED / "symlink-raw"
    cleaned = GENERATED / "symlink-cleaned"
    raw.mkdir(parents=True, exist_ok=True)
    source = raw / "keep.fit"
    source.write_bytes(b"keep")
    try:
        exclusion._create_keep_symlinks(
            [classify_heart_rate(activity(source, [100, 110]))], cleaned
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege is unavailable in the test process")
        raise

    link = cleaned / "keep.fit"
    assert link.is_symlink()
    assert link.resolve() == source.resolve()
