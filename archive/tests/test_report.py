from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image as PILImage
from pypdf import PdfReader

from power_hr_eda.dataset import DatasetSummary
from power_hr_eda.report import build_pdf_report


GENERATED = Path(__file__).parent / "_generated" / "report"


def example_summary() -> DatasetSummary:
    return DatasetSummary(
        activities=(),
        inventory=pd.DataFrame(
            {
                "activity_id": ["a", "b"],
                "record_count": [100, 200],
                "observed_span_s": [3600.0, 7200.0],
                "parse_error": [None, None],
                "joint_observed_fraction": [0.9, 0.8],
                "power_observed_count": [100, 0],
                "heart_rate_observed_count": [100, 200],
                "heart_rate_longest_run_samples": [4, 120],
                "heart_rate_longest_run_value": [130, 93],
                "heart_rate_longest_run_start": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
                "heart_rate_longest_run_end": ["2026-01-01T00:00:03Z", "2026-01-02T00:01:59Z"],
                "altitude_alias_mismatch_count": [0, 0],
                "altitude_alias_pair_count": [100, 200],
                "speed_alias_mismatch_count": [0, 0],
                "speed_alias_pair_count": [100, 200],
            }
        ),
        field_coverage=pd.DataFrame(
            {"field": ["power", "heart_rate"], "session_observed_count": [2, 2], "session_denominator": [2, 2], "session_fraction": [1.0, 1.0], "record_observed_count": [300, 300], "record_denominator": [300, 300], "record_fraction": [1.0, 1.0]}
        ),
        timing=pd.DataFrame({"activity_id": ["a", "b"], "dt_median_positive_s": [1.0, 1.0], "dt_over_5s_count": [0, 1]}),
        signal_quality=pd.DataFrame({"activity_id": ["a", "b"], "field": ["power", "heart_rate"], "observed_count": [100, 200]}),
        monthly_volume=pd.DataFrame({"month": ["2026-01"], "activity_count": [2], "observed_span_s": [10800.0]}),
        signal_distributions=pd.DataFrame({"field": ["power", "heart_rate"], "observed_count": [300, 300], "median": [180.0, 145.0]}),
        lag_summary=pd.DataFrame({"activity_id": ["a", "b"], "apparent_lag_s": [20, 25], "max_correlation": [0.7, 0.6]}),
        lag_curves={},
        message_types=pd.DataFrame({"activity_id": ["a"], "message_type": ["record"], "message_count": [100]}),
    )


def example_figure() -> Path:
    GENERATED.mkdir(parents=True, exist_ok=True)
    path = GENERATED / "figure.png"
    PILImage.new("RGB", (1800, 1000), "white").save(path)
    return path


def test_report_has_required_sections_and_no_conclusions() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    output = GENERATED / "report.pdf"

    build_pdf_report(example_summary(), [("Figura di prova", example_figure())], output)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)

    assert "Campionamento e continuità temporale" in text
    assert "Sincronizzazione descrittiva HR-power" in text
    assert "Metriche disponibili per attività" in text
    assert "Lavoro derivato" in text
    assert "Indicatori descrittivi di qualità" in text
    assert "Timestamp duplicati" in text
    assert "5. Campi esclusi" in text
    assert "interpretabili" in text
    assert "left_right_balance" in text
    assert "Lag apparente non informativo" in text
    assert "Conclusioni" not in text
    assert "training split" not in text.lower()
    assert "validation split" not in text.lower()
    assert "test split" not in text.lower()


def test_pdf_contains_image_and_page_numbers() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    output = GENERATED / "report-structure.pdf"

    build_pdf_report(example_summary(), [("Figura di prova", example_figure())], output)
    reader = PdfReader(output)
    extracted = [page.extract_text() or "" for page in reader.pages]

    assert len(reader.pages) >= 3
    assert sum(len(page.images) for page in reader.pages) >= 1
    assert any("Pagina 2" in text for text in extracted)
