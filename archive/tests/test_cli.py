from __future__ import annotations

from pathlib import Path

from power_hr_eda.cli import main


GENERATED = Path(__file__).parent / "_generated" / "cli"


def test_cli_processes_directory_and_creates_no_split_outputs() -> None:
    input_dir = GENERATED / "input"
    output_dir = GENERATED / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "broken.fit").write_bytes(b"not-a-fit")
    output = output_dir / "report.pdf"

    code = main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output),
            "--images",
            str(output_dir / "images"),
            "--tables",
            str(output_dir / "tables"),
        ]
    )

    assert code == 0
    assert output.exists()
    assert (output_dir / "tables" / "activity_inventory.csv").exists()
    assert (output_dir / "run_manifest.json").exists()
    assert not list(output_dir.rglob("*split*"))
    assert not list(output_dir.rglob("*train*"))


def test_cli_refuses_output_inside_raw_input() -> None:
    input_dir = GENERATED / "protected-input"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "broken.fit").write_bytes(b"not-a-fit")

    code = main(["--input", str(input_dir), "--output", str(input_dir / "report.pdf")])

    assert code == 2
    assert not (input_dir / "report.pdf").exists()
