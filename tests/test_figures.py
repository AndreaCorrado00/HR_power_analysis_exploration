from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image

from power_hr_eda.dataset import build_dataset_summary
from power_hr_eda.figures import (
    generate_report_figures,
    save_duration_distribution,
    save_signal_distribution,
)
from power_hr_eda.fit_reader import FitActivity


GENERATED = Path(__file__).parent / "_generated" / "figures"


def test_duration_figure_has_print_readable_dimensions() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    inventory = pd.DataFrame({"observed_span_s": [1200, 2400, 3600, 7200]})

    path = save_duration_distribution(inventory, GENERATED)

    with Image.open(path) as image:
        width, height = image.size
    assert width >= 1800
    assert height >= 1000


def test_empty_optional_signal_produces_annotated_figure() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)

    path = save_signal_distribution(pd.Series(dtype=float), "temperature", "°C", GENERATED)

    assert path.exists()
    assert path.stat().st_size > 10_000


def test_report_figure_set_covers_core_diagnostics() -> None:
    records = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=80, freq="s", tz="UTC"),
            "power": list(range(80)),
            "heart_rate": list(range(100, 180)),
            "cadence": [85] * 80,
        }
    )
    summary = build_dataset_summary(
        [FitActivity(Path("ride.fit"), records, {}, {"record": 80})]
    )

    figures = generate_report_figures(summary, GENERATED / "complete")
    captions = " ".join(caption for caption, _ in figures)

    assert len(figures) >= 8
    generated_names = {path.name for _, path in figures}
    assert "campionamento" not in captions.lower()
    assert "sampling_quality.png" not in generated_names
    assert "field_coverage.png" not in generated_names
    assert "potenza" in captions.lower()
    assert "frequenza cardiaca" in captions.lower()
    assert all(path.exists() for _, path in figures)
