from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import matplotlib
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .dataset import DatasetSummary


NAVY = colors.HexColor("#123247")
BLUE = colors.HexColor("#176B87")
LIGHT = colors.HexColor("#EAF2F5")
GRAY = colors.HexColor("#5B6470")


def _register_fonts() -> tuple[str, str]:
    font_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    regular = font_dir / "DejaVuSans.ttf"
    bold = font_dir / "DejaVuSans-Bold.ttf"
    if "EdaSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("EdaSans", regular))
        pdfmetrics.registerFont(TTFont("EdaSans-Bold", bold))
    return "EdaSans", "EdaSans-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EdaTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=25,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "EdaSubtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=13,
            leading=19,
            textColor=GRAY,
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "EdaH1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=18,
            leading=23,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=9,
        ),
        "h2": ParagraphStyle(
            "EdaH2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=17,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "EdaBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.5,
            leading=14.2,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#23313A"),
            spaceAfter=7,
        ),
        "caption": ParagraphStyle(
            "EdaCaption",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8.2,
            leading=11.5,
            alignment=TA_JUSTIFY,
            textColor=GRAY,
            spaceBefore=5,
        ),
        "table": ParagraphStyle(
            "EdaTable",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.5,
            leading=9.5,
        ),
        "small_center": ParagraphStyle(
            "EdaSmallCenter",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=GRAY,
        ),
    }


def _footer(canvas, doc) -> None:
    canvas.saveState()
    regular, _ = _register_fonts()
    canvas.setFont(regular, 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(20 * mm, 12 * mm, "Fase 0 - Esplorazione descrittiva dei dati FIT")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("&", "&amp;"), style)


def _compact_table(frame: pd.DataFrame, columns: list[str], labels: list[str], styles) -> Table:
    data = [[_paragraph(label, styles["table"]) for label in labels]]
    for _, row in frame.loc[:, columns].iterrows():
        values = []
        for column in columns:
            value = row[column]
            if pd.isna(value):
                text = "n.d."
            elif isinstance(value, float):
                text = f"{value:.3g}"
            else:
                text = str(value)
            values.append(_paragraph(text, styles["table"]))
        data.append(values)
    table = Table(data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "EdaSans-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD8DE")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _figure_block(number: int, caption: str, path: Path, styles) -> list[object]:
    image = Image(str(path))
    max_width = A4[0] - 36 * mm
    max_height = A4[1] - 75 * mm
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return [
        Spacer(1, 4 * mm),
        image,
        _paragraph(f"<b>Figura {number}.</b> {caption}", styles["caption"]),
    ]


def _metric_availability_table(inventory: pd.DataFrame, styles) -> Table:
    definitions = [
        ("Durata osservata", "observed_span_s", "differenza primo-ultimo record", "s"),
        ("Distanza FIT", "fit_total_distance_m", "riepilogo sessione FIT", "m"),
        ("Dislivello positivo FIT", "fit_total_ascent_m", "riepilogo sessione FIT", "m"),
        ("Timer time FIT", "fit_total_timer_time_s", "riepilogo sessione FIT", "s"),
        ("Lavoro derivato", "derived_work_kj", "somma potenza per delta t positivo", "kJ"),
    ]
    rows = []
    for label, column, definition, unit in definitions:
        values = pd.to_numeric(inventory.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "metric": label,
                "definition": definition,
                "available": int(len(values)),
                "median": float(values.median()) if len(values) else None,
                "unit": unit,
            }
        )
    return _compact_table(
        pd.DataFrame(rows),
        ["metric", "definition", "available", "median", "unit"],
        ["Metrica", "Origine o formula", "Attività", "Mediana", "Unità"],
        styles,
    )


def _quality_indicator_table(summary: DatasetSummary, styles) -> Table:
    def total(frame: pd.DataFrame, column: str) -> int:
        return int(pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def signal_total(field: str, column: str) -> int:
        frame = summary.signal_quality
        if frame.empty or "field" not in frame:
            return 0
        return total(frame.loc[frame["field"] == field], column)

    def signal_max(field: str, column: str) -> int:
        frame = summary.signal_quality
        if frame.empty or "field" not in frame or column not in frame:
            return 0
        values = pd.to_numeric(frame.loc[frame["field"] == field, column], errors="coerce").dropna()
        return int(values.max()) if len(values) else 0

    rows = pd.DataFrame(
        [
            {"indicator": "Timestamp duplicati", "value": total(summary.timing, "dt_zero_count"), "denominator": "intervalli consecutivi"},
            {"indicator": "Intervalli temporali negativi", "value": total(summary.timing, "dt_negative_count"), "denominator": "intervalli consecutivi"},
            {"indicator": "Gap superiori a 5 s", "value": total(summary.timing, "dt_over_5s_count"), "denominator": "intervalli positivi"},
            {"indicator": "Potenza mancante", "value": signal_total("power", "missing_count"), "denominator": "record"},
            {"indicator": "Potenza uguale a zero", "value": signal_total("power", "zero_count"), "denominator": "record osservati"},
            {"indicator": "Run costante potenza massimo", "value": signal_max("power", "longest_constant_run_samples"), "denominator": "campioni consecutivi"},
            {"indicator": "HR mancante", "value": signal_total("heart_rate", "missing_count"), "denominator": "record"},
            {"indicator": "HR uguale a zero", "value": signal_total("heart_rate", "zero_count"), "denominator": "record osservati"},
            {"indicator": "Run costante HR massimo", "value": signal_max("heart_rate", "longest_constant_run_samples"), "denominator": "campioni consecutivi"},
        ]
    )
    return _compact_table(
        rows,
        ["indicator", "value", "denominator"],
        ["Indicatore", "Conteggio", "Riferimento"],
        styles,
    )


def _signal_stat(summary: DatasetSummary, field: str, column: str, reducer: str = "sum") -> float | None:
    frame = summary.signal_quality
    if frame.empty or "field" not in frame or column not in frame:
        return None
    values = pd.to_numeric(frame.loc[frame["field"] == field, column], errors="coerce").dropna()
    if values.empty:
        return None
    if reducer == "max":
        return float(values.max())
    return float(values.sum())


def build_pdf_report(
    summary: DatasetSummary,
    figures: Iterable[tuple[str, Path]],
    output_path: Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Fase 0 - Esplorazione descrittiva dei dati FIT",
        author="power_HR_model",
    )
    inventory = summary.inventory
    session_count = len(inventory)
    readable_count = int(inventory["parse_error"].isna().sum()) if "parse_error" in inventory else 0
    record_count = int(inventory["record_count"].sum()) if "record_count" in inventory else 0
    observed_hours = float(inventory["observed_span_s"].sum() / 3600) if "observed_span_s" in inventory else 0
    duration_values = pd.to_numeric(inventory.get("observed_span_s", pd.Series(dtype=float)), errors="coerce").dropna()
    median_duration_h = float(duration_values.median() / 3600) if len(duration_values) else None
    start_values = pd.to_datetime(inventory.get("start_time", pd.Series(dtype=object)), utc=True, errors="coerce").dropna()
    date_range = "non disponibile"
    if len(start_values):
        date_range = f"{start_values.min().strftime('%d/%m/%Y')} - {start_values.max().strftime('%d/%m/%Y')}"
    power_sessions = 0
    hr_sessions = 0
    if not summary.field_coverage.empty:
        coverage_by_field = summary.field_coverage.set_index("field")
        if "power" in coverage_by_field.index:
            power_sessions = int(coverage_by_field.loc["power", "session_observed_count"])
        if "heart_rate" in coverage_by_field.index:
            hr_sessions = int(coverage_by_field.loc["heart_rate", "session_observed_count"])
    joint_sessions = int((pd.to_numeric(inventory.get("joint_observed_count", pd.Series(dtype=float)), errors="coerce") > 0).sum())
    timing_medians = pd.to_numeric(summary.timing.get("dt_median_positive_s", pd.Series(dtype=float)), errors="coerce").dropna()
    gap_sessions = int((pd.to_numeric(summary.timing.get("dt_over_5s_count", pd.Series(dtype=float)), errors="coerce") > 0).sum())
    defined_lags = pd.to_numeric(summary.lag_summary.get("apparent_lag_s", pd.Series(dtype=float)), errors="coerce").dropna()
    altitude_pairs = int(pd.to_numeric(inventory.get("altitude_alias_pair_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    altitude_mismatches = int(pd.to_numeric(inventory.get("altitude_alias_mismatch_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    speed_pairs = int(pd.to_numeric(inventory.get("speed_alias_pair_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    speed_mismatches = int(pd.to_numeric(inventory.get("speed_alias_mismatch_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    no_power_ids = inventory.loc[
        pd.to_numeric(inventory.get("power_observed_count", pd.Series(0, index=inventory.index)), errors="coerce").fillna(0).eq(0),
        "activity_id",
    ].astype(str).tolist() if "activity_id" in inventory else []
    plateau_row = None
    if "heart_rate_longest_run_samples" in inventory:
        plateau_values = pd.to_numeric(inventory["heart_rate_longest_run_samples"], errors="coerce")
        eligible_plateaus = plateau_values.gt(0)
        if "heart_rate_longest_run_value" in inventory:
            eligible_plateaus &= pd.to_numeric(inventory["heart_rate_longest_run_value"], errors="coerce").notna()
        if eligible_plateaus.any():
            plateau_row = inventory.loc[plateau_values.where(eligible_plateaus).idxmax()]
    min_lag_row = None
    if not summary.lag_summary.empty and "max_correlation" in summary.lag_summary:
        lag_correlations = pd.to_numeric(summary.lag_summary["max_correlation"], errors="coerce")
        if lag_correlations.notna().any():
            min_lag_row = summary.lag_summary.loc[lag_correlations.idxmin()]
    unknown_observed = _signal_stat(summary, "unknown_66", "observed_count")
    unknown_zeros = _signal_stat(summary, "unknown_66", "zero_count")
    hr_zero_count = _signal_stat(summary, "heart_rate", "zero_count")
    temperature_run = _signal_stat(summary, "temperature", "longest_constant_run_samples", "max")
    story: list[object] = [
        Spacer(1, 35 * mm),
        _paragraph("Fase 0", styles["subtitle"]),
        _paragraph("Esplorazione descrittiva dei dati ciclistici FIT", styles["title"]),
        Spacer(1, 5 * mm),
        _paragraph(
            "Struttura, copertura, qualità, campionamento e sincronizzazione osservata dei segnali di potenza e frequenza cardiaca.",
            styles["subtitle"],
        ),
        Spacer(1, 18 * mm),
        Table(
            [["File FIT", str(session_count)], ["File leggibili", str(readable_count)], ["Record", f"{record_count:,}".replace(",", ".")], ["Ore osservate", f"{observed_hours:.1f}"]],
            colWidths=[62 * mm, 45 * mm],
            style=TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "EdaSans-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "EdaSans"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD8DE")),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 30 * mm),
        _paragraph(f"Report generato il {datetime.now().strftime('%d/%m/%Y')}", styles["small_center"]),
        PageBreak(),
        _paragraph("1. Guida alla lettura", styles["h1"]),
        _paragraph(
            "Il report descrive esclusivamente informazioni presenti nei file FIT o calcolate direttamente da tali informazioni. Non sono applicati filtri, interpolazioni, correzioni temporali o rimozioni automatiche. Le anomalie sono conteggiate e mostrate senza essere reinterpretate come condizioni fisiologiche.",
            styles["body"],
        ),
        _paragraph(
            "Le statistiche per record e per attività utilizzano denominatori distinti. Una distribuzione aggregata per record attribuisce più peso alle attività lunghe; una distribuzione tra attività attribuisce lo stesso peso a ciascun file. Questa distinzione è mantenuta nelle tabelle e nelle didascalie.",
            styles["body"],
        ),
        _paragraph(
            f"Sono stati inventariati {session_count} file nel periodo {date_range}; {readable_count} risultano leggibili. "
            + (f"La durata osservata mediana è {median_duration_h:.2f} ore." if median_duration_h is not None else "La durata osservata non è determinabile."),
            styles["body"],
        ),
        _paragraph("2. Struttura e copertura", styles["h1"]),
    ]
    if not summary.field_coverage.empty:
        coverage = summary.field_coverage.sort_values("session_fraction", ascending=False).head(15)
        story.append(
            _compact_table(
                coverage,
                ["field", "session_observed_count", "session_denominator", "record_observed_count", "record_denominator"],
                ["Campo", "Sessioni", "Den. sessioni", "Record", "Den. record"],
                styles,
            )
        )
    story.extend(
        [
            Spacer(1, 4 * mm),
            _paragraph(
                "La copertura indica dove un campo è effettivamente osservato. L'assenza di un campo non è convertita in zero e non viene imputata.",
                styles["body"],
            ),
            _paragraph("3. Campionamento e continuità temporale", styles["h1"]),
            _paragraph(
                "Gli intervalli tra timestamp consecutivi sono calcolati nell'ordine originale dei record. Intervalli nulli e negativi sono conteggiati separatamente; i percentili del campionamento usano soltanto intervalli positivi. I gap sono descritti a più soglie temporali e non vengono colmati.",
                styles["body"],
            ),
            _paragraph(
                (f"La mediana, tra attività, del delta t mediano è {timing_medians.median():.2f} s. " if len(timing_medians) else "Il delta t mediano non è disponibile. ")
                + f"Sono presenti gap superiori a 5 s in {gap_sessions} attività su {session_count}.",
                styles["body"],
            ),
            _paragraph("4. Qualità osservata di potenza e frequenza cardiaca", styles["h1"]),
            _paragraph(
                "Per ciascun segnale sono descritti valori osservati, assenze, zeri, distribuzioni e sequenze costanti. Gli zeri di potenza sono conservati: possono corrispondere a coasting oppure ad altre condizioni che i soli valori numerici non permettono di distinguere in modo univoco.",
                styles["body"],
            ),
            _paragraph(
                f"La potenza è osservata in {power_sessions} attività, la frequenza cardiaca in {hr_sessions} e almeno una coppia HR-power è disponibile in {joint_sessions} attività. I file privi di uno dei segnali restano nell'inventario.",
                styles["body"],
            ),
            _paragraph("Indicatori descrittivi di qualità", styles["h2"]),
            _quality_indicator_table(summary, styles),
            Spacer(1, 3 * mm),
            _paragraph(
                "I conteggi descrivono i valori registrati e la continuità delle sequenze. Non costituiscono automaticamente criteri di esclusione e non distinguono, da soli, tra comportamento reale del segnale e malfunzionamento del sensore.",
                styles["body"],
            ),
            _paragraph("5. Campi esclusi, ridondanti o non interpretabili", styles["h1"]),
            _paragraph(
                "<b>Campo escluso.</b> <font name='EdaSans'>left_right_balance</font> è escluso dalle tabelle, dalle distribuzioni e dalle figure analitiche perché il dato non è disponibile in forma utilizzabile. I file FIT originali non sono modificati.",
                styles["body"],
            ),
            _paragraph(
                f"<b>Campi ridondanti.</b> altitude ed enhanced_altitude coincidono in {altitude_pairs - altitude_mismatches} coppie su {altitude_pairs}; speed ed enhanced_speed coincidono in {speed_pairs - speed_mismatches} coppie su {speed_pairs}. Le coppie sono conservate nell'inventario raw ma rappresentano la stessa informazione nei dati osservati.",
                styles["body"],
            ),
            _paragraph(
                (f"<b>Campo non interpretabile.</b> unknown_66 contiene {int(unknown_zeros or 0)} zeri su {int(unknown_observed or 0)} valori osservati. Il nome non identifica una grandezza né un'unità, quindi il campo non viene interpretato scientificamente."),
                styles["body"],
            ),
            _paragraph(
                "<b>Sessioni senza potenza.</b> " + (", ".join(no_power_ids) if no_power_ids else "nessuna") + ". Queste attività restano descritte nell'EDA ma non forniscono coppie utilizzabili per una relazione HR-power.",
                styles["body"],
            ),
            _paragraph(
                (
                    f"<b>Plateau HR.</b> L'attività {plateau_row['activity_id']} contiene il run HR costante più lungo: "
                    f"{int(plateau_row['heart_rate_longest_run_samples'])} campioni al valore {plateau_row['heart_rate_longest_run_value']:.0f} bpm, "
                    f"da {pd.to_datetime(plateau_row['heart_rate_longest_run_start'], utc=True).strftime('%d/%m/%Y %H:%M:%S UTC')} "
                    f"a {pd.to_datetime(plateau_row['heart_rate_longest_run_end'], utc=True).strftime('%d/%m/%Y %H:%M:%S UTC')}. Il segmento è segnalato come plateau strumentale e non viene reinterpretato fisiologicamente."
                    if plateau_row is not None
                    else "<b>Plateau HR.</b> Non determinabile."
                ),
                styles["body"],
            ),
            _paragraph(
                f"Sono inoltre osservati {int(hr_zero_count or 0)} record HR uguali a zero. Il run costante massimo della temperatura è di {int(temperature_run or 0)} campioni; questa persistenza può riflettere la frequenza di aggiornamento del sensore e viene riportata senza attribuzione causale.",
                styles["body"],
            ),
            _paragraph(
                "La distanza nei record è cumulativa all'interno della sessione: la sua distribuzione pooled descrive la permanenza ai diversi valori cumulati, non la distribuzione delle distanze finali. Per confrontare le attività si usa la distanza finale del riepilogo FIT.",
                styles["body"],
            ),
            _paragraph("6. Sincronizzazione descrittiva HR-power", styles["h1"]),
            _paragraph(
                "La correlazione a lag usa esclusivamente coppie con timestamp esattamente corrispondenti. Un lag positivo indica che la frequenza cardiaca è osservata dopo la potenza. Il massimo della curva è riportato come lag apparente, non come correzione strumentale né come parametro fisiologico identificato.",
                styles["body"],
            ),
            _paragraph(
                (f"Il lag apparente è definibile in {len(defined_lags)} attività; la mediana osservata è {defined_lags.median():.1f} s." if len(defined_lags) else "Il lag apparente non è definibile nelle attività analizzate."),
                styles["body"],
            ),
            _paragraph(
                (
                    f"<b>Lag apparente non informativo.</b> Nell'attività {min_lag_row['activity_id']} il massimo della correlazione è {float(min_lag_row['max_correlation']):.3f} al lag di {int(min_lag_row['apparent_lag_s'])} s. La posizione del massimo viene conservata come risultato numerico, ma una correlazione prossima a zero non sostiene l'identificazione del lag."
                    if min_lag_row is not None
                    else "<b>Lag apparente non informativo.</b> Non determinabile."
                ),
                styles["body"],
            ),
            _paragraph("7. Parametri osservati e metriche direttamente derivate", styles["h1"]),
            _paragraph(
                "Le statistiche includono solo campi registrati e quantità deterministiche, come durate osservate e lavoro meccanico quando la potenza e il tempo sono disponibili. Non sono utilizzati valori personali, zone, soglie o metriche proprietarie.",
                styles["body"],
            ),
            KeepTogether(
                [
                    _paragraph("Metriche disponibili per attività", styles["h2"]),
                    _paragraph(
                        "Il lavoro derivato usa la potenza del record iniziale moltiplicata per il successivo delta t positivo. La misura è sensibile ai gap di registrazione ed è quindi riportata come quantità derivata, distinta dai riepiloghi memorizzati nel FIT.",
                        styles["body"],
                    ),
                    _metric_availability_table(inventory, styles),
                ]
            ),
            Spacer(1, 3 * mm),
            PageBreak(),
        ]
    )
    for number, (caption, path) in enumerate(figures, start=1):
        story.append(_paragraph(caption.split(".", 1)[0], styles["h2"]))
        story.extend(_figure_block(number, caption, Path(path), styles))
        story.append(PageBreak())
    if story and isinstance(story[-1], PageBreak):
        story.pop()
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
