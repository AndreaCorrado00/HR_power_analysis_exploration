"""Compact plots with deterministic examples and explicit prediction horizons."""
from pathlib import Path
import os
import json

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[3]/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .diagnostics import curves_for_segments, quantile, summarize_curves
from .data import Segment
from .validation import forecast_segment


def save(fig, path, caption):
    for ax in fig.axes:
        ax.grid(alpha=.2)
        ax.spines[['top', 'right']].set_visible(False)
    fig.text(.02, .015, caption, fontsize=8, color='#425568')
    fig.tight_layout(rect=(0, .07, 1, .94))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def acf_summary_plot(summary, path, title):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    fig.suptitle(title)
    lag = summary.lag_s.to_numpy()[1:]
    for ax, name in zip(axes, ['acf', 'pacf']):
        ax.fill_between(lag, summary[name+'_p10'].to_numpy()[1:], summary[name+'_p90'].to_numpy()[1:],
                        color='#257c9e', alpha=.18, label='P10-P90 tra workout')
        ax.plot(lag, summary[name+'_median'].to_numpy()[1:], color='#257c9e', label='Mediana tra workout')
        ax.axhline(0, color='black', lw=.7)
        ax.set(xlabel='Lag [s]', ylabel=name.upper())
        ax.legend(fontsize=8)
    save(fig, path, 'ACF/PACF calcolate separatamente e centrate per tratto; poi mediana entro workout e tra workout.\nBande di dispersione, non intervalli di confidenza. Nessuna concatenazione, nessun taglio post-cambio.')


def workout_acf_plots(meta, acfs, pacfs, output):
    """Each line is one individual continuous segment, exported also as NPZ."""
    output.mkdir(parents=True)
    for wid in meta.workout_id.unique():
        mask = meta.workout_id.eq(wid).to_numpy() & meta.status.eq('ok').to_numpy()
        if not mask.any():
            continue
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
        fig.suptitle(f'{wid}: {mask.sum()} tratti analizzabili')
        for ax, curves, label in zip(axes, [acfs[mask], pacfs[mask]], ['ACF', 'PACF']):
            lag = np.arange(1, curves.shape[1])
            ax.plot(lag, curves[:, 1:].T, color='#82959f', alpha=.22, lw=.7)
            ax.plot(lag, quantile(curves, .5)[1:], color='#006b8f', lw=2, label='Mediana dei tratti')
            ax.axhline(0, color='black', lw=.6)
            ax.set(xlabel='Lag [s]', ylabel=label)
            ax.legend(fontsize=8)
        save(fig, output/f'{wid}.png', 'Una linea grigia per tratto, senza collegare gap, pause, cambi target o lap.\nTratti brevi: lag fino a floor(n/2)-1. Costanti e tratti <4 campioni registrati in segments.csv.')


def fit_analysis(model, train_segments, validation_segments, metrics, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    innovations = []
    for s in train_segments:
        prediction = forecast_segment(model, s)
        ix = prediction['index']
        if len(ix):
            innovations.append(Segment(s.workout_id, s.segment_id, s.time[ix],
                                       prediction['observed_residual']-prediction['predicted_residual'], s.target[ix]))
    meta, acfs, pacfs = curves_for_segments(innovations, 60)
    available = bool(meta.status.eq('ok').any())
    meta.to_csv(output/'innovation_segments.csv', index=False)
    (output/'innovation_status.json').write_text(json.dumps(dict(
        available=available, reason=None if available else 'All innovation segments are short or constant')),
        encoding='utf-8')
    if available:
        summary, _ = summarize_curves(meta, acfs, pacfs, min(20, model.hold_back))
        summary.to_csv(output/'innovation_acf_pacf.csv', index=False)
        acf_summary_plot(summary, output/'innovations.png', f'AR({model.p}): innovazioni sul training')
    example_predictions(model, validation_segments, output/'prediction_examples.png')
    performance_plot(metrics, output/'performance.png', f'AR({model.p}): validation')


def example_predictions(model, segments, path):
    # First/middle/last eligible workout in chronological input order, longest tract.
    ids = list(dict.fromkeys(s.workout_id for s in segments if len(s.residual) > model.hold_back+30))
    if not ids:
        return
    chosen = [ids[i] for i in sorted(set([0, len(ids)//2, len(ids)-1]))]
    fig, axes = plt.subplots(len(chosen), 1, figsize=(12, 3*len(chosen)), squeeze=False)
    for ax, wid in zip(axes.ravel(), chosen):
        s = max((s for s in segments if s.workout_id == wid), key=lambda s: len(s.residual))
        limit = min(len(s.residual), model.hold_back+240)
        xx = s.time[:limit]-s.time[0]
        ax.plot(xx, (s.residual+s.target)[:limit], color='#40474c', lw=1, label='P reale')
        ax.plot(xx, s.target[:limit], color='#b27822', ls='--', label='Target / baseline')
        for horizon, color in [(1, '#007da3'), (30, '#be4661')]:
            pred = forecast_segment(model, s, horizon)
            keep = pred['index'] < limit
            ix = pred['index'][keep]
            ax.plot(s.time[ix]-s.time[0], s.target[ix]+pred['predicted_residual'][keep],
                    color=color, lw=1, label=f'AR({model.p}), h={horizon} s')
        ax.set(title=f'Workout {wid}, tratto {s.segment_id}, inizio {s.time[0]:.0f} s',
               xlabel='Secondi dall\'inizio del tratto', ylabel='Potenza [W]')
        ax.legend(ncol=4, fontsize=8)
    save(fig, path, 'Esempi prefissati: primo, centrale e ultimo workout eleggibile; tratto piu lungo, primi 240 s valutabili.\nOrigini mobili: h=1 usa il passato osservato; h=30 ricorre senza osservazioni future. Target inferito dalla traccia reale.')


def performance_plot(metrics, path, title):
    one = metrics[metrics.horizon_s.eq(1)]
    pivot = one.pivot(index='workout_id', columns='model', values='rmse_w')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    fig.suptitle(title)
    axes[0].scatter(pivot.target, pivot.ar, color='#257c9e')
    top = float(pivot.max().max())*1.05
    axes[0].plot([0, top], [0, top], color='grey', ls='--')
    axes[0].set(xlabel='RMSE baseline target [W]', ylabel='RMSE AR, h=1 [W]')
    macro = metrics.groupby(['horizon_s', 'model']).rmse_w.mean().unstack('model')
    for label, color in [('ar', '#257c9e'), ('target', '#b27822')]:
        axes[1].plot(macro.index, macro[label], marker='o', color=color, label=label)
    axes[1].set(xlabel='Orizzonte [s]', ylabel='RMSE medio tra workout [W]')
    axes[1].legend()
    save(fig, path, 'Confronti sugli stessi endpoint per AR e baseline. Ogni workout pesa ugualmente nella media.\nGli endpoint disponibili possono diminuire con l\'orizzonte; conteggi nel CSV.')


def comparison_plot(comparison, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    for ax, metric in zip(axes, ['rmse_w', 'mae_w']):
        for split, color in [('train', '#82959f'), ('validation', '#257c9e')]:
            part = comparison[(comparison.split == split) & (comparison.horizon_s == 1)]
            ar = part[part.model == 'ar']
            baseline = part[part.model == 'target']
            ax.plot(ar.p, ar[metric], 'o-', color=color, label=split+' AR')
            ax.plot(baseline.p, baseline[metric], '--', color=color, label=split+' target')
        ax.set(xlabel='Ordine p', ylabel=metric.replace('_w', '').upper()+' medio per workout [W]')
        ax.legend(fontsize=8)
    save(fig, path, 'Selezione: minimo RMSE medio di validation a un passo; parita esatta risolta con p minore.\nTraining e validation separati; nessun risultato del test usato in questa figura.')
