"""Summarize saved milestone results without fitting or changing source data."""
from pathlib import Path
import hashlib
import json
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "webapp/model_identification_app/storage"
RUN_ID = "b4ac2e8208374c9fbf18a4009dc0e2fc"


def main():
    manifests = [p for p in (STORAGE / "runs").glob("*.json")
                 if json.loads(p.read_text(encoding="utf-8"))["id"] == RUN_ID]
    if len(manifests) != 1:
        raise ValueError("Expected the single saved seed-52 run manifest")
    manifest_path = manifests[0]
    analysis_path = STORAGE / "runs" / RUN_ID / "population/analysis.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if analysis["run_id"] != RUN_ID or analysis["config"]["prediction_mode"] != "local_B_180s":
        raise ValueError("Expected the saved seed-52 analysis with 180 s calibration")
    predicted = [row for row in analysis["test"] if row["status"] == "predicted"]
    if not predicted or any(row["evaluation_start_s"] != 180 for row in predicted):
        raise ValueError("Expected predictions evaluated from 180 s")
    fits = [json.loads(p.read_text(encoding="utf-8"))
            for p in (STORAGE / "runs" / RUN_ID).glob("*.json")]
    repeat_path = next((STORAGE / "runs").glob("*8dc6d46a.json"))
    repeat = json.loads(repeat_path.read_text(encoding="utf-8"))
    sources = [manifest_path, analysis_path, repeat_path]
    result = {
        "milestone_date": "2026-10-04",
        "run_id": RUN_ID,
        "analysis_id": analysis["id"],
        "sources": [{"path": p.relative_to(ROOT).as_posix(),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
        "split_unit": manifest["split"]["unit"],
        "split_seed": manifest["split"]["seed"],
        "split_counts": {k: len(v) for k, v in manifest["split"]["assignments"].items()},
        "dataset_summary": manifest["dataset"]["source_manifests"][0]["manifest"]["summary"],
        "run_status": manifest["status"],
        "repeat_run": {"id": repeat["id"], "split_seed": repeat["split"]["seed"],
                       "status": repeat["status"], "progress": repeat["progress"],
                       "finished_at": repeat.get("finished_at"),
                       "note": "Running in archived snapshot; latest persisted identification status here. No comparison inferred."},
        "fit_counts": {s: sum(row["status"] == s for row in fits) for s in ["fitted", "failed"]},
        "retained_vectors": analysis["retained_vectors"],
        "prediction_config": analysis["config"],
        "population_mean": dict(zip(analysis["model"]["keys"], analysis["model"]["mean"])),
        "population_units": {p["key"]: p["unit"] for p in analysis["parameters"]},
        "delay_fixed_s": manifest["config"]["lower"][1],
        "test_total": len(analysis["test"]),
        "test_predicted": len(predicted),
        "test_failed": sum(row["status"] == "failed" for row in analysis["test"]),
        "predicted_activity_count": len({row["activity_id"] for row in predicted}),
        "evaluation_start_s": 180,
        "aggregation": "Unweighted median across successfully predicted test segments; errors in bpm",
        "median_metrics": {key: median(row["metrics"][key] for row in predicted)
                           for key in ["RMSE", "MAE", "bias", "residual_sd", "constant_B_RMSE"]},
        "better_than_constant_B": sum(row["metrics"]["RMSE"] < row["metrics"]["constant_B_RMSE"]
                                      for row in predicted),
        "limitations": ["Calibration uses observed HR in [0,180 s).",
                        "Test inspected during protocol development; exploratory evidence.",
                        "Constant B baseline is not a static power-HR regression.",
                        "Seed 60 uses the same source dataset, not new independent data."],
    }
    target = ROOT / "reports/current_study/summary.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(f"Saved {target.relative_to(ROOT)}: {len(predicted)}/{len(analysis['test'])} predictions")


if __name__ == "__main__":
    main()
