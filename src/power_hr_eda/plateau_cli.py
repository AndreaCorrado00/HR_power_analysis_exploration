from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

import pandas as pd

from .fit_reader import read_fit_activity
from .plateau import (
    RUN_COLUMNS,
    apply_plateau_review,
    export_plateau_study,
    extract_plateau_runs,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Empirical study of constant heart-rate runs")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--tables", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.input.is_dir() or not args.decisions.is_file():
        return 2
    decisions = pd.read_csv(args.decisions)
    existing_manifest = (
        json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {}
    )
    keep_files = set(decisions.loc[decisions["decision"].eq("KEEP"), "source_file"])
    all_paths = sorted(args.input.glob("*.fit"))
    selected = [path for path in all_paths if path.name in keep_files]
    activities = {path.name: read_fit_activity(path) for path in selected}
    frames = [extract_plateau_runs(activities[path.name]) for path in selected]
    runs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RUN_COLUMNS)
    manifest = export_plateau_study(
        runs, decisions, args.tables, args.images / "plateau_analysis", args.manifest
    )
    if "plateau_review" in existing_manifest:
        manifest["plateau_review"] = existing_manifest["plateau_review"]
    manifest = apply_plateau_review(activities, runs, keep_files, manifest, args.images)
    manifest["inputs"] = {
        "fit_directory": str(args.input),
        "decision_table": str(args.decisions),
        "decision_table_sha256": _sha256(args.decisions),
        "fit_file_count": len(all_paths),
        "analyzed_keep_file_count": len(selected),
        "fit_files": [
            {"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in all_paths
        ],
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
