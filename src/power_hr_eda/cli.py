from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .dataset import build_dataset_summary, export_summary_tables
from .figures import generate_report_figures
from .fit_reader import read_fit_activity
from .report import build_pdf_report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descriptive EDA of cycling FIT files")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--tables", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    input_dir = args.input
    output_path = args.output
    images_dir = args.images or output_path.parent / "images"
    tables_dir = args.tables or output_path.parent / "tables"

    if not input_dir.is_dir():
        return 2
    protected = [output_path, images_dir, tables_dir]
    if any(_inside(path, input_dir) for path in protected):
        return 2

    fit_paths = sorted(input_dir.glob("*.fit"))
    activities = [read_fit_activity(path) for path in fit_paths]
    summary = build_dataset_summary(activities)
    table_paths = export_summary_tables(summary, tables_dir)
    figures = generate_report_figures(summary, images_dir)
    build_pdf_report(summary, figures, output_path)

    manifest_path = output_path.parent / "run_manifest.json"
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "input_file_count": len(fit_paths),
        "inputs": [
            {"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in fit_paths
        ],
        "outputs": {
            "report": str(output_path),
            "tables": [str(path) for path in table_paths],
            "images": [str(path) for _, path in figures],
        },
        "analysis_rules": {
            "interpolation": False,
            "resampling": False,
            "automatic_lag_correction": False,
            "externally_parameterized_metrics": False,
            "dataset_partitioning": False,
        },
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
