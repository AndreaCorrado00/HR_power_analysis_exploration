from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from power_hr_eda.fit_reader import FitActivity
from power_hr_eda.plateau import (
    apply_plateau_review,
    build_exclusion_manifest,
    classify_plateau_files,
    estimate_survival_breakpoint,
    export_plateau_study,
    extract_plateau_runs,
    merge_plateau_review_into_manifest,
    save_plateau_review_plot,
)


GENERATED = Path(__file__).parent / "_generated" / "plateau"


def activity(heart_rate: list[float], seconds: list[int]) -> FitActivity:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = pd.DataFrame(
        {
            "timestamp": [start + timedelta(seconds=value) for value in seconds],
            "heart_rate": heart_rate,
        }
    )
    return FitActivity(Path("ride.fit"), records, {}, {"record": len(records)})


def test_plateau_runs_break_on_changed_or_missing_heart_rate() -> None:
    runs = extract_plateau_runs(
        activity([100, 100, float("nan"), 100, 101, 101], [0, 1, 2, 3, 4, 6])
    )

    assert runs[["heart_rate_bpm", "sample_count", "duration_s"]].to_dict("records") == [
        {"heart_rate_bpm": 100.0, "sample_count": 2, "duration_s": 1.0},
        {"heart_rate_bpm": 100.0, "sample_count": 1, "duration_s": 0.0},
        {"heart_rate_bpm": 101.0, "sample_count": 2, "duration_s": 2.0},
    ]
    assert runs.iloc[-1]["max_internal_gap_s"] == 2.0


def test_survival_breakpoint_separates_a_constructed_long_tail() -> None:
    body = pd.Series([0, 1, 2, 3, 4, 5] * 30, dtype=float)
    tail = pd.Series([40, 50, 60, 80, 100, 140], dtype=float)

    result = estimate_survival_breakpoint(pd.concat([body, tail], ignore_index=True))

    assert 5 < result["threshold_s"] < 40
    assert result["method"] == "two_segment_log_survival_least_squares"


def test_manifest_labels_only_previous_phase_drops() -> None:
    decisions = pd.DataFrame(
        [
            {
                "source_file": "keep.fit",
                "decision": "KEEP",
                "triggered_criteria": "",
                "flagged_record_count": 0,
            },
            {
                "source_file": "drop.fit",
                "decision": "DROP",
                "triggered_criteria": "HR_NON_POSITIVE;HR_RATE_OF_CHANGE",
                "flagged_record_count": 2,
            },
        ]
    )

    manifest = build_exclusion_manifest(decisions, proposed_threshold_s=31.0)

    assert manifest["previous_phase_excluded_files"] == [
        {
            "source_file": "drop.fit",
            "triggered_criteria": ["HR_NON_POSITIVE", "HR_RATE_OF_CHANGE"],
            "flagged_record_count": 2,
        }
    ]
    assert manifest["plateau_analysis"]["proposed_threshold_s"] == 31.0
    assert manifest["plateau_analysis"]["status"] == "threshold_research_only"
    assert "files_to_be_reviewed" not in manifest["plateau_analysis"]


def test_exported_study_contains_plots_runs_and_no_plateau_labels() -> None:
    runs = pd.DataFrame(
        {
            "activity_id": ["a"] * 8,
            "source_file": ["a.fit"] * 8,
            "heart_rate_bpm": [100.0] * 8,
            "start_time": pd.date_range("2026-01-01", periods=8, tz="UTC"),
            "end_time": pd.date_range("2026-01-01", periods=8, tz="UTC"),
            "sample_count": [1, 2, 3, 4, 5, 6, 40, 60],
            "duration_s": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 40.0, 60.0],
            "max_internal_gap_s": [0.0] * 8,
        }
    )
    decisions = pd.DataFrame(
        [
            {
                "source_file": "drop.fit",
                "decision": "DROP",
                "triggered_criteria": "HR_NON_POSITIVE",
                "flagged_record_count": 1,
            }
        ]
    )

    result = export_plateau_study(
        runs,
        decisions,
        GENERATED / "tables",
        GENERATED / "images",
        GENERATED / "manifest.json",
    )

    assert (GENERATED / "tables" / "plateau_runs.csv").exists()
    assert len(list((GENERATED / "images").glob("*.png"))) == 4
    assert (GENERATED / "manifest.json").exists()
    assert result["plateau_analysis"]["files_labeled_from_plateau_analysis"] == 0
    assert "threshold_sensitivity" in result["plateau_analysis"]


def test_plateau_file_classification_uses_strict_21_5_second_threshold() -> None:
    runs = pd.DataFrame(
        {
            "source_file": ["short.fit", "boundary.fit", "review.fit", "large.fit"],
            "duration_s": [10.0, 21.5, 30.0, 45.0],
        }
    )

    result = classify_plateau_files(
        runs,
        ["short.fit", "boundary.fit", "review.fit", "large.fit", "no-hr.fit"],
    ).set_index("source_file")

    assert result.loc["short.fit", "automatic_decision"] == "KEEP"
    assert result.loc["boundary.fit", "automatic_decision"] == "KEEP"
    assert result.loc["review.fit", "automatic_decision"] == "REVIEW"
    assert result.loc["review.fit", "highest_candidate_threshold_that_keeps_file_s"] == 39.0
    assert result.loc["large.fit", "automatic_decision"] == "REVIEW"
    assert pd.isna(result.loc["large.fit", "highest_candidate_threshold_that_keeps_file_s"])
    assert result.loc["no-hr.fit", "automatic_decision"] == "KEEP"


def test_review_manifest_preserves_existing_manual_decisions() -> None:
    manifest = {
        "plateau_review": {
            "files": [
                {"source_file": "review.fit", "manual_decision": "DROP"},
            ]
        }
    }
    classifications = pd.DataFrame(
        [
            {
                "source_file": "review.fit",
                "automatic_decision": "REVIEW",
                "max_plateau_duration_s": 30.0,
                "suspicious_plateau_count": 1,
                "highest_candidate_threshold_that_keeps_file_s": 39.0,
            },
            {
                "source_file": "keep.fit",
                "automatic_decision": "KEEP",
                "max_plateau_duration_s": 10.0,
                "suspicious_plateau_count": 0,
                "highest_candidate_threshold_that_keeps_file_s": 39.0,
            },
        ]
    )

    merged = merge_plateau_review_into_manifest(manifest, classifications, {})
    files = {item["source_file"]: item for item in merged["plateau_review"]["files"]}

    assert files["review.fit"]["manual_decision"] == "DROP"
    assert files["keep.fit"]["manual_decision"] is None
    assert merged["plateau_review"]["manual_decision_allowed_values"] == ["KEEP", "DROP"]


def test_review_plot_does_not_modify_activity_records() -> None:
    fit_activity = activity([100, 100, 100, 101], [0, 1, 30, 31])
    fit_activity.records["power"] = [100, 110, 120, 130]
    original = fit_activity.records.copy(deep=True)
    suspicious = extract_plateau_runs(fit_activity)
    suspicious = suspicious.loc[suspicious["duration_s"].gt(21.5)]
    output = GENERATED / "review-plot.png"

    result = save_plateau_review_plot(fit_activity, suspicious, output)

    assert result == output
    assert output.exists()
    pd.testing.assert_frame_equal(fit_activity.records, original)


def test_apply_review_plots_only_review_files() -> None:
    review_activity = activity([100, 100, 100, 101], [0, 1, 30, 31])
    review_activity.records["power"] = [100, 110, 120, 130]
    keep_activity = activity([100, 100, 101], [0, 1, 2])
    keep_activity = FitActivity(
        Path("keep.fit"), keep_activity.records.assign(power=[100, 110, 120]), {}, {"record": 3}
    )
    runs = pd.concat(
        [extract_plateau_runs(review_activity), extract_plateau_runs(keep_activity)],
        ignore_index=True,
    )
    manifest: dict[str, object] = {}
    output_dir = GENERATED / "review-files"

    result = apply_plateau_review(
        {"ride.fit": review_activity, "keep.fit": keep_activity},
        runs,
        ["ride.fit", "keep.fit"],
        manifest,
        output_dir,
    )

    assert result["plateau_review"]["review_count"] == 1
    assert result["plateau_review"]["keep_count"] == 1
    assert (output_dir / "ride.png").exists()
    assert not (output_dir / "keep.png").exists()
