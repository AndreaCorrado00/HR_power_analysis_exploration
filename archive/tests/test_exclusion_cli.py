from pathlib import Path

from power_hr_eda.exclusion_cli import main


def test_exclusion_cli_rejects_missing_input_directory() -> None:
    root = Path(__file__).parent / "_generated" / "missing-fit-input"

    code = main(
        [
            "--input",
            str(root),
            "--tables",
            "unused-tables",
            "--images",
            "unused-images",
            "--cleaned",
            "unused-cleaned",
        ]
    )

    assert code == 2
