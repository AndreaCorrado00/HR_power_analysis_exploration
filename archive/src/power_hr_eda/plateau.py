from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .fit_reader import FitActivity


RUN_COLUMNS = [
    "activity_id",
    "source_file",
    "heart_rate_bpm",
    "start_time",
    "end_time",
    "sample_count",
    "duration_s",
    "max_internal_gap_s",
]

PLATEAU_REVIEW_THRESHOLD_S = 21.5
CANDIDATE_THRESHOLDS_S = (21.5, 31.5, 39.0)


def extract_plateau_runs(activity: FitActivity) -> pd.DataFrame:
    records = activity.records
    if "heart_rate" not in records or records.empty:
        return pd.DataFrame(columns=RUN_COLUMNS)
    heart_rate = pd.to_numeric(records["heart_rate"], errors="coerce")
    timestamps = pd.to_datetime(
        records.get("timestamp", pd.Series(index=records.index, dtype=object)),
        utc=True,
        errors="coerce",
    )
    groups = (heart_rate.ne(heart_rate.shift()) | heart_rate.isna()).cumsum()
    rows: list[dict[str, object]] = []
    for _, indices in records.loc[heart_rate.notna()].groupby(groups[heart_rate.notna()]).groups.items():
        index = list(indices)
        times = timestamps.loc[index]
        deltas = times.diff().dt.total_seconds().dropna()
        start = times.iloc[0]
        end = times.iloc[-1]
        duration = (end - start).total_seconds() if pd.notna(start) and pd.notna(end) else None
        rows.append(
            {
                "activity_id": activity.path.stem,
                "source_file": activity.path.name,
                "heart_rate_bpm": float(heart_rate.loc[index[0]]),
                "start_time": start,
                "end_time": end,
                "sample_count": len(index),
                "duration_s": float(duration) if duration is not None else None,
                "max_internal_gap_s": float(deltas.max()) if not deltas.empty else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=RUN_COLUMNS)


def _line_sse(x: np.ndarray, y: np.ndarray) -> float:
    design = np.column_stack([x, np.ones(len(x))])
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coefficients
    return float(residuals @ residuals)


def estimate_survival_breakpoint(durations: pd.Series) -> dict[str, object]:
    values = pd.to_numeric(durations, errors="coerce").dropna()
    values = np.sort(values[values >= 0].to_numpy(dtype=float))
    unique = np.unique(values)
    if len(unique) < 6:
        raise ValueError("At least six distinct non-negative durations are required")
    survival = np.array([(values >= value).mean() for value in unique], dtype=float)
    x = unique
    y = np.log(survival)
    candidates: list[tuple[float, int]] = []
    for split in range(3, len(unique) - 2):
        score = _line_sse(x[:split], y[:split]) + _line_sse(x[split:], y[split:])
        candidates.append((score, split))
    score, split = min(candidates, key=lambda item: item[0])
    threshold = float((unique[split - 1] + unique[split]) / 2)
    return {
        "method": "two_segment_log_survival_least_squares",
        "threshold_s": threshold,
        "left_observed_duration_s": float(unique[split - 1]),
        "right_observed_duration_s": float(unique[split]),
        "sum_squared_error": score,
        "distinct_duration_count": int(len(unique)),
    }


def build_exclusion_manifest(
    decisions: pd.DataFrame,
    proposed_threshold_s: float,
    *,
    plateau_details: dict[str, object] | None = None,
) -> dict[str, object]:
    excluded = []
    drops = decisions.loc[decisions["decision"].eq("DROP")]
    for row in drops.to_dict("records"):
        criteria = str(row.get("triggered_criteria") or "")
        excluded.append(
            {
                "source_file": row["source_file"],
                "triggered_criteria": [item for item in criteria.split(";") if item],
                "flagged_record_count": int(row.get("flagged_record_count", 0)),
            }
        )
    plateau = {
        "status": "threshold_research_only",
        "proposed_threshold_s": float(proposed_threshold_s),
        "files_labeled_from_plateau_analysis": 0,
    }
    if plateau_details:
        plateau.update(plateau_details)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_level": "entire FIT file",
        "previous_phase_excluded_count": len(excluded),
        "previous_phase_excluded_files": excluded,
        "plateau_analysis": plateau,
    }


def classify_plateau_files(
    runs: pd.DataFrame,
    keep_files: list[str] | set[str] | tuple[str, ...],
    threshold_s: float = PLATEAU_REVIEW_THRESHOLD_S,
) -> pd.DataFrame:
    durations = runs.copy()
    durations["duration_s"] = pd.to_numeric(durations["duration_s"], errors="coerce")
    maxima = durations.groupby("source_file")["duration_s"].max()
    suspicious = durations.loc[durations["duration_s"].gt(threshold_s)].groupby("source_file").size()
    rows = []
    for source_file in sorted(keep_files):
        maximum = float(maxima[source_file]) if source_file in maxima and pd.notna(maxima[source_file]) else None
        surviving = [value for value in CANDIDATE_THRESHOLDS_S if maximum is None or maximum <= value]
        rows.append(
            {
                "source_file": source_file,
                "automatic_decision": "REVIEW" if maximum is not None and maximum > threshold_s else "KEEP",
                "max_plateau_duration_s": maximum,
                "suspicious_plateau_count": int(suspicious.get(source_file, 0)),
                "highest_candidate_threshold_that_keeps_file_s": max(surviving) if surviving else None,
            }
        )
    return pd.DataFrame(rows)


def merge_plateau_review_into_manifest(
    manifest: dict[str, object],
    classifications: pd.DataFrame,
    plot_paths: dict[str, str],
) -> dict[str, object]:
    previous = manifest.get("plateau_review", {})
    previous_files = previous.get("files", []) if isinstance(previous, dict) else []
    manual = {
        item.get("source_file"): item.get("manual_decision")
        for item in previous_files
        if isinstance(item, dict) and item.get("manual_decision") in {"KEEP", "DROP"}
    }
    files = []
    for row in classifications.to_dict("records"):
        source_file = str(row["source_file"])
        maximum = row.get("max_plateau_duration_s")
        candidate = row.get("highest_candidate_threshold_that_keeps_file_s")
        files.append(
            {
                "source_file": source_file,
                "automatic_decision": row["automatic_decision"],
                "manual_decision": manual.get(source_file),
                "max_plateau_duration_s": None if pd.isna(maximum) else float(maximum),
                "suspicious_plateau_count": int(row["suspicious_plateau_count"]),
                "highest_candidate_threshold_that_keeps_file_s": None
                if pd.isna(candidate)
                else float(candidate),
                "review_plot": plot_paths.get(source_file),
            }
        )
    manifest["plateau_review"] = {
        "rule": "REVIEW if at least one plateau has duration_s > 21.5; otherwise KEEP.",
        "threshold_s": PLATEAU_REVIEW_THRESHOLD_S,
        "comparison": "strictly_greater_than",
        "candidate_thresholds_s": list(CANDIDATE_THRESHOLDS_S),
        "manual_decision_field": "manual_decision",
        "manual_decision_allowed_values": ["KEEP", "DROP"],
        "review_count": int(classifications["automatic_decision"].eq("REVIEW").sum()),
        "keep_count": int(classifications["automatic_decision"].eq("KEEP").sum()),
        "files": files,
    }
    return manifest


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def save_plateau_review_plot(
    activity: FitActivity,
    suspicious_runs: pd.DataFrame,
    output_path: Path,
) -> Path:
    records = activity.records
    timestamps = pd.to_datetime(records["timestamp"], utc=True, errors="coerce")
    heart_rate = pd.to_numeric(records.get("heart_rate"), errors="coerce")
    power = pd.to_numeric(records.get("power"), errors="coerce")
    longest = suspicious_runs.loc[suspicious_runs["duration_s"].idxmax()]
    maximum = float(longest["duration_s"])
    surviving = [value for value in CANDIDATE_THRESHOLDS_S if maximum <= value]
    survival_text = (
        f"Soglia massima candidata che manterrebbe il file: {max(surviving):g} s"
        if surviving
        else "Nessuna soglia candidata (21.5, 31.5, 39 s) manterrebbe il file"
    )

    fig = plt.figure(figsize=(15, 10))
    grid = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1.15], hspace=0.28)
    hr_ax = fig.add_subplot(grid[0])
    power_ax = fig.add_subplot(grid[1], sharex=hr_ax)
    zoom_ax = fig.add_subplot(grid[2])
    hr_ax.plot(timestamps, heart_rate, color="#D97706", linewidth=0.9, label="HR")
    power_ax.plot(timestamps, power, color="#176B87", linewidth=0.8, label="Potenza")
    for run in suspicious_runs.itertuples(index=False):
        start = pd.to_datetime(run.start_time, utc=True)
        end = pd.to_datetime(run.end_time, utc=True)
        hr_ax.axvspan(start, end, color="#C62828", alpha=0.23)
        power_ax.axvspan(start, end, color="#C62828", alpha=0.23)
    hr_ax.set_ylabel("HR (bpm)")
    power_ax.set_ylabel("Potenza (W)")
    power_ax.set_xlabel("Timestamp")
    hr_ax.set_title(f"Attività completa: {activity.path.name} — plateau > {PLATEAU_REVIEW_THRESHOLD_S:g} s in rosso", loc="left")
    hr_ax.grid(alpha=0.2)
    power_ax.grid(alpha=0.2)

    start = pd.to_datetime(longest["start_time"], utc=True)
    end = pd.to_datetime(longest["end_time"], utc=True)
    margin = pd.Timedelta(seconds=max(30.0, maximum * 0.1))
    zoom_ax.plot(timestamps, heart_rate, color="#D97706", linewidth=1.2, label="HR")
    zoom_ax.set_xlim(start - margin, end + margin)
    zoom_ax.axvspan(start, end, color="#C62828", alpha=0.25, label=f"Plateau {maximum:g} s")
    zoom_ax.set_ylabel("HR (bpm)", color="#D97706")
    zoom_power = zoom_ax.twinx()
    zoom_power.plot(timestamps, power, color="#176B87", linewidth=0.9, alpha=0.8, label="Potenza")
    zoom_power.set_ylabel("Potenza (W)", color="#176B87")
    zoom_power.grid(False)
    zoom_ax.set_xlabel("Timestamp")
    zoom_ax.set_title(f"Zoom sul plateau più lungo: HR={float(longest['heart_rate_bpm']):g} bpm", loc="left")
    zoom_ax.legend(frameon=False, loc="upper left")
    zoom_ax.grid(alpha=0.2)
    fig.suptitle(survival_text, fontsize=14, y=0.99)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def apply_plateau_review(
    activities: dict[str, FitActivity],
    runs: pd.DataFrame,
    keep_files: list[str] | set[str] | tuple[str, ...],
    manifest: dict[str, object],
    output_dir: Path,
) -> dict[str, object]:
    classifications = classify_plateau_files(runs, keep_files)
    review_files = set(
        classifications.loc[
            classifications["automatic_decision"].eq("REVIEW"), "source_file"
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = {f"{Path(name).stem}.png" for name in review_files}
    for existing in output_dir.glob("*.png"):
        if existing.name not in expected:
            existing.unlink()
    plot_paths: dict[str, str] = {}
    for source_file in sorted(review_files):
        suspicious = runs.loc[
            runs["source_file"].eq(source_file)
            & pd.to_numeric(runs["duration_s"], errors="coerce").gt(PLATEAU_REVIEW_THRESHOLD_S)
        ]
        path = output_dir / f"{Path(source_file).stem}.png"
        save_plateau_review_plot(activities[source_file], suspicious, path)
        plot_paths[source_file] = str(path)
    return merge_plateau_review_into_manifest(manifest, classifications, plot_paths)


def _plot_plateau_distributions(runs: pd.DataFrame, threshold_s: float, output_dir: Path) -> list[Path]:
    durations = pd.to_numeric(runs["duration_s"], errors="coerce").dropna()
    positive = durations[durations > 0]
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    fig, ax = plt.subplots(figsize=(11, 6.2))
    if positive.empty:
        ax.text(0.5, 0.5, "Nessuna durata positiva", ha="center", va="center", transform=ax.transAxes)
    else:
        bins = np.geomspace(max(1.0, positive.min()), positive.max() + 1, 60)
        ax.hist(positive, bins=bins, color="#176B87", edgecolor="white")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.axvline(threshold_s, color="#C62828", linestyle="--", label=f"T* proposto: {threshold_s:g} s")
        ax.legend(frameon=False)
    ax.set(title="Distribuzione completa delle durate dei plateau HR", xlabel="Durata (s, scala log)", ylabel="Numero di run (scala log)")
    paths.append(_save_figure(fig, output_dir / "plateau_duration_full_log.png"))

    fig, ax = plt.subplots(figsize=(11, 6.2))
    upper = float(durations.quantile(0.995)) if not durations.empty else 1.0
    body = durations[durations <= upper]
    ax.hist(body, bins=max(10, min(80, int(upper) + 1)), color="#176B87", edgecolor="white")
    ax.axvline(threshold_s, color="#C62828", linestyle="--", label=f"T* proposto: {threshold_s:g} s")
    ax.legend(frameon=False)
    ax.set(title="Corpo principale della distribuzione", xlabel="Durata (s)", ylabel="Numero di run")
    paths.append(_save_figure(fig, output_dir / "plateau_duration_body.png"))

    fig, ax = plt.subplots(figsize=(11, 6.2))
    unique = np.unique(durations.to_numpy(dtype=float))
    survival = np.array([(durations >= value).mean() for value in unique])
    ax.plot(unique, survival, color="#176B87", linewidth=1.5)
    ax.axvline(threshold_s, color="#C62828", linestyle="--", label=f"Breakpoint T*: {threshold_s:g} s")
    ax.set_yscale("log")
    ax.legend(frameon=False)
    ax.set(title="Funzione di sopravvivenza empirica delle durate", xlabel="Durata (s)", ylabel="P(durata >= t), scala log")
    paths.append(_save_figure(fig, output_dir / "plateau_survival_breakpoint.png"))

    fig, ax = plt.subplots(figsize=(11, 7))
    maxima = runs.groupby("source_file")["duration_s"].max().sort_values(ascending=False)
    shown = maxima.head(40).sort_values()
    ax.barh(shown.index, shown.values, color="#176B87")
    ax.axvline(threshold_s, color="#C62828", linestyle="--", label=f"T* proposto: {threshold_s:g} s")
    ax.legend(frameon=False)
    ax.set(title="Massima durata osservata per file (primi 40)", xlabel="Durata massima (s)", ylabel="File FIT")
    paths.append(_save_figure(fig, output_dir / "plateau_max_duration_by_file.png"))
    return paths


def export_plateau_study(
    runs: pd.DataFrame,
    decisions: pd.DataFrame,
    tables_dir: Path,
    images_dir: Path,
    manifest_path: Path,
) -> dict[str, object]:
    breakpoint = estimate_survival_breakpoint(runs["duration_s"])
    tables_dir.mkdir(parents=True, exist_ok=True)
    runs.to_csv(tables_dir / "plateau_runs.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    plot_paths = _plot_plateau_distributions(runs, float(breakpoint["threshold_s"]), images_dir)
    durations = pd.to_numeric(runs["duration_s"], errors="coerce").dropna()

    def sensitivity_threshold(values: pd.Series) -> float | None:
        try:
            return float(estimate_survival_breakpoint(values)["threshold_s"])
        except ValueError:
            return None

    longest_index = durations.idxmax()
    longest_file = runs.loc[longest_index, "source_file"]
    sensitivity = {
        "all_runs_s": float(breakpoint["threshold_s"]),
        "without_single_longest_run_s": sensitivity_threshold(durations.drop(index=longest_index)),
        "at_or_below_empirical_p999_s": sensitivity_threshold(
            durations[durations <= durations.quantile(0.999)]
        ),
        "without_file_containing_longest_run_s": sensitivity_threshold(
            pd.to_numeric(
                runs.loc[runs["source_file"].ne(longest_file), "duration_s"], errors="coerce"
            ).dropna()
        ),
        "longest_run_source_file": str(longest_file),
    }
    details = {
        "threshold_status": "proposed_not_fixed_a_priori",
        "method": breakpoint["method"],
        "breakpoint_details": breakpoint,
        "threshold_sensitivity": sensitivity,
        "run_definition": "Consecutive records with identical numeric heart_rate; missing or changed values break the run.",
        "duration_definition": "Elapsed seconds between first and last timestamp; no interpolation or gap filling.",
        "analyzed_file_count": int(runs["source_file"].nunique()),
        "run_count": int(len(runs)),
        "duration_quantiles_s": {
            str(q): float(durations.quantile(q)) for q in (0.5, 0.9, 0.95, 0.99, 0.995, 0.999, 1.0)
        },
        "outputs": {
            "runs_table": str(tables_dir / "plateau_runs.csv"),
            "plots": [str(path) for path in plot_paths],
        },
    }
    manifest = build_exclusion_manifest(
        decisions,
        proposed_threshold_s=float(breakpoint["threshold_s"]),
        plateau_details=details,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
