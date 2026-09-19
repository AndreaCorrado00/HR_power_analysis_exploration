from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .dataset import DatasetSummary


BLUE = "#176B87"
ORANGE = "#D97706"
GRAY = "#5B6470"


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.labelsize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "figure.facecolor": "white",
        }
    )


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def save_duration_distribution(inventory: pd.DataFrame, output_dir: Path) -> Path:
    _style()
    values = pd.to_numeric(inventory.get("observed_span_s", pd.Series(dtype=float)), errors="coerce").dropna() / 3600
    fig, ax = plt.subplots(figsize=(11, 6.2))
    if values.empty:
        ax.text(0.5, 0.5, "Durata non disponibile", ha="center", va="center", transform=ax.transAxes)
    else:
        bins = min(25, max(5, int(len(values) ** 0.5) * 2))
        ax.hist(values, bins=bins, color=BLUE, edgecolor="white", linewidth=0.8)
        ax.axvline(values.median(), color=ORANGE, linewidth=2, label=f"Mediana: {values.median():.2f} h")
        ax.legend(frameon=False)
    ax.set_title("Distribuzione della durata osservata delle attività", loc="left")
    ax.set_xlabel("Durata tra primo e ultimo record (ore)")
    ax.set_ylabel("Numero di attività")
    return _save(fig, Path(output_dir) / "duration_distribution.png")


def save_signal_distribution(values: pd.Series, field: str, unit: str, output_dir: Path) -> Path:
    _style()
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    fig, ax = plt.subplots(figsize=(11, 6.2))
    if numeric.empty:
        ax.text(
            0.5,
            0.5,
            f"Nessun valore osservato per {field}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=GRAY,
            fontsize=14,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        bins = min(60, max(10, int(len(numeric) ** 0.5)))
        ax.hist(numeric, bins=bins, color=BLUE, edgecolor="white", linewidth=0.35)
        ax.axvline(numeric.median(), color=ORANGE, linewidth=2, label=f"Mediana: {numeric.median():.1f}")
        ax.legend(frameon=False)
    ax.set_title(f"Distribuzione osservata: {field}", loc="left")
    ax.set_xlabel(f"{field} ({unit})" if unit else field)
    ax.set_ylabel("Numero di record")
    return _save(fig, Path(output_dir) / f"distribution_{field}.png")


def _all_records(summary: DatasetSummary) -> pd.DataFrame:
    frames = []
    for activity in summary.activities:
        if activity.records.empty:
            continue
        frame = activity.records.copy()
        frame["activity_id"] = activity.path.stem
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _save_monthly_volume(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(11, 6.2))
    data = summary.monthly_volume
    if data.empty:
        ax.text(0.5, 0.5, "Copertura mensile non disponibile", ha="center", va="center", transform=ax.transAxes)
    else:
        x = np.arange(len(data))
        ax.bar(x, data["observed_span_s"] / 3600, color=BLUE, label="Ore osservate")
        ax.set_xticks(x, data["month"], rotation=45, ha="right")
        ax2 = ax.twinx()
        ax2.plot(x, data["activity_count"], color=ORANGE, marker="o", linewidth=2, label="Attività")
        ax2.set_ylabel("Numero di attività")
        ax2.grid(False)
    ax.set_title("Copertura temporale mensile", loc="left")
    ax.set_xlabel("Mese")
    ax.set_ylabel("Ore tra primo e ultimo record")
    fig.tight_layout()
    return _save(fig, Path(output_dir) / "monthly_volume.png")


def _save_field_coverage(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    data = summary.field_coverage.sort_values("session_fraction").tail(25)
    fig, ax = plt.subplots(figsize=(11, 8.2))
    if data.empty:
        ax.text(0.5, 0.5, "Campi record non disponibili", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.barh(data["field"], data["session_fraction"] * 100, color=BLUE)
        ax.set_xlim(0, 105)
    ax.set_title("Copertura dei campi nei file FIT", loc="left")
    ax.set_xlabel("Attività con almeno un valore osservato (%)")
    ax.set_ylabel("Campo record")
    fig.tight_layout()
    return _save(fig, Path(output_dir) / "field_coverage.png")


def _save_sampling(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.8))
    data = summary.timing
    medians = pd.to_numeric(data.get("dt_median_positive_s", pd.Series(dtype=float)), errors="coerce").dropna()
    gaps = pd.to_numeric(data.get("dt_over_5s_count", pd.Series(dtype=float)), errors="coerce").dropna()
    if medians.empty:
        axes[0].text(0.5, 0.5, "Non disponibile", ha="center", va="center", transform=axes[0].transAxes)
    else:
        axes[0].hist(medians, bins=min(25, max(5, int(len(medians) ** 0.5) * 2)), color=BLUE)
    axes[0].set_title("Mediana di delta t per attività")
    axes[0].set_xlabel("Secondi")
    axes[0].set_ylabel("Attività")
    if gaps.empty:
        axes[1].text(0.5, 0.5, "Non disponibile", ha="center", va="center", transform=axes[1].transAxes)
    else:
        axes[1].hist(gaps, bins=min(25, max(5, int(len(gaps) ** 0.5) * 2)), color=ORANGE)
    axes[1].set_title("Gap superiori a 5 s per attività")
    axes[1].set_xlabel("Numero di gap")
    axes[1].set_ylabel("Attività")
    fig.suptitle("Regolarità del campionamento", x=0.07, ha="left", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, Path(output_dir) / "sampling_quality.png")


def _save_joint_coverage(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    values = pd.to_numeric(summary.inventory.get("joint_observed_fraction", pd.Series(dtype=float)), errors="coerce").dropna() * 100
    fig, ax = plt.subplots(figsize=(11, 6.2))
    if values.empty:
        ax.text(0.5, 0.5, "Copertura congiunta non disponibile", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.hist(values, bins=min(25, max(5, int(len(values) ** 0.5) * 2)), color=BLUE)
        ax.axvline(values.median(), color=ORANGE, linewidth=2, label=f"Mediana: {values.median():.1f}%")
        ax.legend(frameon=False)
    ax.set_title("Copertura congiunta di potenza e frequenza cardiaca", loc="left")
    ax.set_xlabel("Record con entrambi i segnali (%)")
    ax.set_ylabel("Attività")
    return _save(fig, Path(output_dir) / "joint_coverage.png")


def _save_power_hr_relation(records: pd.DataFrame, output_dir: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(11, 6.5))
    if {"power", "heart_rate"}.issubset(records.columns):
        paired = records[["power", "heart_rate"]].apply(pd.to_numeric, errors="coerce").dropna()
    else:
        paired = pd.DataFrame()
    if paired.empty:
        ax.text(0.5, 0.5, "Coppie HR-power non disponibili", ha="center", va="center", transform=ax.transAxes)
    else:
        if len(paired) > 200_000:
            indices = np.linspace(0, len(paired) - 1, 200_000, dtype=int)
            paired = paired.iloc[indices]
        image = ax.hexbin(paired["power"], paired["heart_rate"], gridsize=65, mincnt=1, cmap="viridis")
        fig.colorbar(image, ax=ax, label="Numero di record per esagono")
    ax.set_title("Distribuzione congiunta HR-power", loc="left")
    ax.set_xlabel("Potenza (W)")
    ax.set_ylabel("Frequenza cardiaca (bpm)")
    return _save(fig, Path(output_dir) / "power_hr_relation.png")


def _save_lag_summary(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.8))
    lag = pd.to_numeric(summary.lag_summary.get("apparent_lag_s", pd.Series(dtype=float)), errors="coerce").dropna()
    corr = pd.to_numeric(summary.lag_summary.get("max_correlation", pd.Series(dtype=float)), errors="coerce").dropna()
    if lag.empty:
        axes[0].text(0.5, 0.5, "Lag non identificabile", ha="center", va="center", transform=axes[0].transAxes)
    else:
        axes[0].hist(lag, bins=min(30, max(7, int(len(lag) ** 0.5) * 2)), color=BLUE)
    axes[0].set_title("Lag apparente al massimo")
    axes[0].set_xlabel("Secondi; positivo = HR successiva")
    axes[0].set_ylabel("Attività")
    if corr.empty:
        axes[1].text(0.5, 0.5, "Correlazione non disponibile", ha="center", va="center", transform=axes[1].transAxes)
    else:
        axes[1].hist(corr, bins=min(25, max(7, int(len(corr) ** 0.5) * 2)), color=ORANGE)
    axes[1].set_title("Correlazione al lag apparente")
    axes[1].set_xlabel("Correlazione")
    axes[1].set_ylabel("Attività")
    fig.suptitle("Sincronizzazione descrittiva HR-power", x=0.07, ha="left", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, Path(output_dir) / "lag_summary.png")


def _save_representative_trace(summary: DatasetSummary, output_dir: Path) -> Path:
    _style()
    eligible = []
    for activity in summary.activities:
        if {"timestamp", "power", "heart_rate"}.issubset(activity.records.columns):
            joint = activity.records[["timestamp", "power", "heart_rate"]].dropna()
            if len(joint) >= 60:
                eligible.append((len(joint), activity))
    fig, ax = plt.subplots(figsize=(11, 6.2))
    if not eligible:
        ax.text(0.5, 0.5, "Traccia congiunta non disponibile", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Esempio di traccia HR-power", loc="left")
        return _save(fig, Path(output_dir) / "representative_trace.png")
    activity = sorted(eligible, key=lambda item: item[0])[len(eligible) // 2][1]
    data = activity.records.copy()
    time = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    elapsed = (time - time.dropna().iloc[0]).dt.total_seconds() / 3600
    power = pd.to_numeric(data["power"], errors="coerce")
    hr = pd.to_numeric(data["heart_rate"], errors="coerce")
    ax.plot(elapsed, power, color=BLUE, linewidth=0.75, alpha=0.8, label="Potenza")
    ax.set_xlabel("Tempo trascorso (ore)")
    ax.set_ylabel("Potenza (W)", color=BLUE)
    ax2 = ax.twinx()
    ax2.plot(elapsed, hr, color=ORANGE, linewidth=1.0, alpha=0.9, label="Frequenza cardiaca")
    ax2.set_ylabel("Frequenza cardiaca (bpm)", color=ORANGE)
    ax2.grid(False)
    ax.set_title(f"Traccia congiunta rappresentativa: {activity.path.stem}", loc="left")
    fig.tight_layout()
    return _save(fig, Path(output_dir) / "representative_trace.png")


def _save_numeric_overviews(summary: DatasetSummary, output_dir: Path) -> list[tuple[str, Path]]:
    records = _all_records(summary)
    fields = summary.signal_distributions.get("field", pd.Series(dtype=str)).tolist()
    pages: list[tuple[str, Path]] = []
    for page_index, start in enumerate(range(0, len(fields), 6), start=1):
        page_fields = fields[start : start + 6]
        _style()
        fig, axes = plt.subplots(3, 2, figsize=(11, 12.5))
        for ax, field in zip(axes.flat, page_fields):
            values = pd.to_numeric(records.get(field, pd.Series(dtype=float)), errors="coerce").dropna()
            if values.empty:
                ax.text(0.5, 0.5, "Non disponibile", ha="center", va="center", transform=ax.transAxes)
            else:
                lower, upper = values.quantile([0.001, 0.999])
                display = values[(values >= lower) & (values <= upper)]
                ax.hist(display, bins=45, color=BLUE, alpha=0.9)
                ax.axvline(values.median(), color=ORANGE, linewidth=1.5)
            ax.set_title(field)
            ax.set_ylabel("Record")
        for ax in axes.flat[len(page_fields) :]:
            ax.axis("off")
        fig.suptitle("Distribuzioni dei parametri numerici osservati", x=0.07, ha="left", fontsize=16)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        path = _save(fig, Path(output_dir) / f"numeric_fields_{page_index:02d}.png")
        caption = (
            "Distribuzioni dei parametri numerici osservati. Per rendere leggibili gli istogrammi, "
            "la visualizzazione è limitata tra i percentili 0,1 e 99,9; le statistiche tabellari conservano tutti i valori."
        )
        pages.append((caption, path))
    return pages


def generate_report_figures(summary: DatasetSummary, output_dir: Path) -> list[tuple[str, Path]]:
    output_dir = Path(output_dir)
    records = _all_records(summary)
    figures: list[tuple[str, Path]] = [
        ("Durata osservata delle attività. La durata è la differenza tra primo e ultimo timestamp record valido.", save_duration_distribution(summary.inventory, output_dir)),
        ("Volume mensile osservato. Le barre mostrano le ore tra primo e ultimo record; la linea mostra il numero di file.", _save_monthly_volume(summary, output_dir)),
        ("Copertura dei campi record. Il denominatore è il numero complessivo di file FIT inventariati.", _save_field_coverage(summary, output_dir)),
        ("Regolarità del campionamento. Sono mostrati la mediana degli intervalli positivi e i gap superiori a cinque secondi.", _save_sampling(summary, output_dir)),
        ("Copertura congiunta di potenza e frequenza cardiaca. Ogni attività contribuisce con una percentuale.", _save_joint_coverage(summary, output_dir)),
        ("Distribuzione della potenza osservata, senza filtraggio o sostituzione degli zeri.", save_signal_distribution(records.get("power", pd.Series(dtype=float)), "power", "W", output_dir)),
        ("Distribuzione della frequenza cardiaca osservata, senza imputazione dei campioni assenti.", save_signal_distribution(records.get("heart_rate", pd.Series(dtype=float)), "heart_rate", "bpm", output_dir)),
        ("Distribuzione congiunta di potenza e frequenza cardiaca sui record in cui entrambi i segnali sono presenti.", _save_power_hr_relation(records, output_dir)),
        ("Sincronizzazione descrittiva HR-power. Il lag apparente massimizza la correlazione su coppie con timestamp esatto e non comporta uno spostamento dei segnali.", _save_lag_summary(summary, output_dir)),
        ("Traccia congiunta di un'attività con numerosità mediana tra quelle dotate di entrambi i segnali.", _save_representative_trace(summary, output_dir)),
    ]
    figures.extend(_save_numeric_overviews(summary, output_dir))
    return figures
