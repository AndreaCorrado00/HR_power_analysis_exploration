from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .exclusion import CRITERIA, run_exclusion_analysis
from .fit_reader import read_fit_activity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="File-level physiological exclusion of FIT activities")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tables", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--cleaned", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.input.is_dir():
        return 2
    fit_paths = sorted(args.input.glob("*.fit"))
    activities = [read_fit_activity(path) for path in fit_paths]
    results = run_exclusion_analysis(activities, args.tables, args.images, args.cleaned)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(args.input.resolve()),
        "input_file_count": len(fit_paths),
        "keep_count": int(results["decision"].eq("KEEP").sum()),
        "drop_count": int(results["decision"].eq("DROP").sum()),
        "criteria": list(CRITERIA),
        "rules": {
            "decision_level": "entire FIT file",
            "any_violation_means_drop": True,
            "correction": False,
            "interpolation": False,
            "imputation": False,
            "segment_removal": False,
            "severity_scores": False,
        },
        "inputs": [
            {"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in fit_paths
        ],
    }
    args.tables.mkdir(parents=True, exist_ok=True)
    (args.tables / "exclusion_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
