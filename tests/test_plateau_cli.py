from pathlib import Path

from power_hr_eda.plateau_cli import main


def test_plateau_cli_rejects_missing_inputs() -> None:
    missing = Path(__file__).parent / "_generated" / "does-not-exist"

    code = main(
        [
            "--input",
            str(missing),
            "--decisions",
            str(missing / "decisions.csv"),
            "--tables",
            "unused-tables",
            "--images",
            "unused-images",
            "--manifest",
            "unused.json",
        ]
    )

    assert code == 2
