"""Offline, empirical duration and power/HR segment grouping; no raw writes."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


def classify(t, p, h):
    x = (t - t[0]) / (t[-1] - t[0])
    start, end = x <= .2, x >= .8
    p0, p1 = np.mean(p[start]), np.mean(p[end])
    h0, h1 = np.median(h[start]), np.median(h[end])
    dp, dh = p1 - p0, h1 - h0
    threshold = max(20., .1 * max(p0, p1))
    # Ten time bins describe shape only; original curves are plotted unchanged.
    bins = np.minimum((x * 10).astype(int), 9)
    med = np.array([np.median(h[bins == i]) if np.any(bins == i) else np.nan
                    for i in range(10)])
    peak = int(np.nanargmax(med))
    bell = 1 <= peak <= 7 and med[peak] - h0 >= 3 and med[peak] - h1 >= 3
    label, reason = 'Ambiguo', 'Potenza senza direzione netta'
    if dp < -threshold:
        if dh <= -3 or bell:
            label, reason = 'UtD', 'HR a campana' if bell else 'HR in discesa'
        else:
            reason = 'Potenza in calo; HR piatta o crescente'
    elif dp > threshold:
        if dh >= 3 and not bell:
            label, reason = 'DtU', 'HR in salita'
        else:
            reason = 'Potenza in salita; HR non concorde'
    return dict(label=label, reason=reason, delta_power_w=float(dp),
                delta_hr_bpm=float(dh), hr_bell=bool(bell))


def draw_segment(ax, seg, xmax):
    t, p, h = seg['t'], seg['p'], seg['h']
    gaps = np.r_[False, np.diff(t) > 1.5 * np.median(np.diff(t))]
    # Insert NaN separators, preserving every measured sample.
    cut = np.flatnonzero(gaps)
    tt, pp, hh = [np.insert(a, cut, np.nan) for a in (t, p, h)]
    ax.plot(tt, pp, color='#2878a6', lw=.8, alpha=.8)
    ax.set_ylim(0, max(500, np.max(p) * 1.08))
    ax.set_xlim(0, xmax)
    ax.set_ylabel('W', color='#2878a6', fontsize=8)
    right = ax.twinx()
    right.plot(tt, hh, color='#c34739', lw=1.5)
    right.set_ylim(80, 200)
    right.set_ylabel('bpm', color='#c34739', fontsize=8)
    ax.set_title(f"{seg['id']}  |  {seg['duration_s']:.0f} s", loc='left', fontsize=9, fontweight='bold')
    ax.text(.02, .94, f"{seg['reason']} | ΔP {seg['delta_power_w']:+.0f} W · ΔHR {seg['delta_hr_bpm']:+.1f} bpm",
            transform=ax.transAxes, va='top', fontsize=7,
            bbox=dict(facecolor='white', alpha=.8, edgecolor='none'))
    ax.grid(alpha=.15)
    ax.tick_params(labelsize=8)
    right.tick_params(labelsize=8)
    ax.set_xlabel('Tempo nel segmento (s)', fontsize=8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('dataset/dataset_segments.zip'))
    parser.add_argument('--output', type=Path, default=Path('reports/segment_groups'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    segments = []
    with zipfile.ZipFile(args.input) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.csv'):
                continue
            rows = list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
            arrays = [np.array([float(r[k]) for r in rows]) for k in
                      ('elapsed_seconds', 'power_w', 'heart_rate_bpm')]
            t, p, h = arrays
            if len(t) < 2 or not all(np.isfinite(a).all() for a in arrays) or np.any(np.diff(t) <= 0):
                raise ValueError(f'Invalid data: {name}; no silent exclusion allowed')
            t = t - t[0]
            segments.append(dict(id=Path(name).stem, t=t, p=p, h=h,
                                 duration_s=float(t[-1]), **classify(t, p, h)))
    durations = np.array([s['duration_s'] for s in segments])
    unique = np.unique(durations)
    # Empty ranges only: both an absolute and a relative separation required.
    split = (np.diff(unique) >= 30) & (unique[1:] / unique[:-1] >= 1.2)
    cuts = ((unique[1:] + unique[:-1]) / 2)[split]
    for seg in segments:
        seg['group'] = int(np.searchsorted(cuts, seg['duration_s'])) + 1
    colors = plt.get_cmap('tab10').colors
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'axes.spines.top': False})
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), layout='constrained')
    for group in range(1, len(cuts) + 2):
        vals = sorted(s['duration_s'] for s in segments if s['group'] == group)
        offset = sum(durations < min(vals))
        axes[0].scatter(np.arange(offset + 1, offset + len(vals) + 1), vals,
                        s=18, color=colors[group-1], label=f'G{group}: {min(vals):.0f}–{max(vals):.0f} s (n={len(vals)})')
    axes[0].set(xlabel='Segmenti ordinati per durata', ylabel='Durata (s)', title='Gruppi esplorativi delle durate')
    axes[0].legend(loc='upper left')
    axes[1].hist(durations, bins=np.arange(0, max(durations) + 21, 20), color='#2878a6', edgecolor='white')
    axes[1].set(xlabel='Durata (s) · intervalli da 20 s', ylabel='Numero di segmenti', title='Distribuzione e soglie candidate')
    for cut in cuts:
        axes[0].axhline(cut, ls='--', color='gray', lw=.8)
        axes[1].axvline(cut, ls='--', color='#c34739', lw=1)
        axes[1].text(cut+5, axes[1].get_ylim()[1]*.8, f'{cut:g} s', rotation=90, color='#c34739')
    for ax in axes:
        ax.grid(alpha=.15)
    fig.suptitle(f'{len(segments)} segmenti | durata = ultimo − primo timestamp', fontsize=15)
    fig.savefig(args.output / 'durate.png', dpi=160)
    plt.close(fig)
    coverage = []
    for group in range(1, len(cuts)+2):
        subset = sorted([s for s in segments if s['group'] == group], key=lambda s: (s['duration_s'], s['id']))
        xmax = max(s['duration_s'] for s in subset)
        for ambiguous in (False, True):
            if ambiguous:
                items = [s for s in subset if s['label'] == 'Ambiguo']
                columns = [items[::2], items[1::2]]
            else:
                columns = [[s for s in subset if s['label'] == label] for label in ('UtD', 'DtU')]
            pages = (max(map(len, columns)) + 4) // 5
            for page in range(pages):
                fig, axes = plt.subplots(5, 2, figsize=(16, 17))
                fig.subplots_adjust(top=.91, bottom=.05, left=.055, right=.94, hspace=.65, wspace=.3)
                kind = 'ambigui' if ambiguous else 'UtD_DtU'
                filename = f'G{group}_{kind}_{page+1:02}.png'
                for col in range(2):
                    for row in range(5):
                        index = page*5+row
                        ax = axes[row, col]
                        if index >= len(columns[col]):
                            ax.axis('off')
                            continue
                        seg = columns[col][index]
                        draw_segment(ax, seg, xmax)
                        coverage.append(dict(id=seg['id'], image=filename))
                fig.suptitle(f'G{group} · {min(s["duration_s"] for s in subset):.0f}–{xmax:.0f} s | '
                             f'{"CASI AMBIGUI" if ambiguous else "DIREZIONE POTENZA / RISPOSTA HR"} | tavola {page+1}/{pages}', fontsize=16)
                for col, title in enumerate(('Da rivedere', 'Da rivedere') if ambiguous else ('UtD · alta → bassa', 'DtU · bassa → alta')):
                    fig.text(.27 if col == 0 else .74, .943, f'{title} (n={len(columns[col])})', ha='center', fontsize=13)
                fig.legend(handles=[Line2D([0], [0], color='#2878a6', label='Potenza · asse sinistro (scala locale)'),
                                    Line2D([0], [0], color='#c34739', label='HR · asse destro (80–200 bpm)')],
                           loc='lower center', ncol=2, frameon=False)
                fig.savefig(args.output / filename, dpi=130)
                plt.close(fig)
    assert len(coverage) == len(segments) == len({c['id'] for c in coverage})
    image_lookup = {c['id']: c['image'] for c in coverage}
    records = [{k: v for k, v in s.items() if k not in ('t', 'p', 'h')} | {'image': image_lookup[s['id']]} for s in segments]
    with (args.output / 'classificazioni.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = dict(input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
                   segments=len(segments), thresholds_seconds=cuts.tolist(),
                   counts={label: sum(s['label'] == label for s in segments) for label in ('UtD','DtU','Ambiguo')},
                   groups=[dict(group=g, count=sum(s['group']==g for s in segments)) for g in range(1,len(cuts)+2)],
                   images=sorted({c['image'] for c in coverage}),
                   numpy=np.__version__, matplotlib=matplotlib.__version__)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    notes = f'''# Raggruppamenti empirici dei segmenti

[Distribuzione delle durate](durate.png) · [Classificazioni e tavola di ciascun segmento](classificazioni.csv)

## Riproduzione e criteri

Eseguire dalla radice: `.venv/Scripts/python scripts/plot_segment_groups.py --input "{args.input.as_posix()}" --output "{args.output.as_posix()}"`.
Fonte: `{args.input.as_posix()}`, letto senza estrazione o modifica.
Hash e versioni delle librerie sono registrati in `summary.json`.

Durata = ultimo meno primo tempo registrato, inclusi eventuali gap.
Un confine è proposto tra durate consecutive distinte se il vuoto è almeno
30 s e il rapporto tra durata maggiore e minore è almeno 1,2. La soglia è
il punto medio del vuoto. Sono raggruppamenti descrittivi, non cluster
statisticamente validati: le soglie dipendono dal campione e dalla regola.
Eventuali gruppi con pochissimi elementi non dimostrano popolazioni distinte.

Direzione della potenza: differenza tra media dell'ultimo e del primo 20%
del tempo del segmento. Una direzione è netta solo oltre il massimo tra
20 W e il 10% della maggiore delle due medie. HR: differenza tra mediane
delle stesse finestre; variazioni inferiori a 3 bpm non sono direzionali.
Campana: mediane HR in 10 intervalli temporali uguali; massimo nei bin
2–8 e almeno 3 bpm sopra entrambe le mediane iniziale/finale.
UtD: potenza in calo e HR in calo o a campana. DtU: potenza in aumento e
HR in aumento senza campana. Tutti gli altri casi sono ambigui.
Le soglie sono euristiche esplorative, non stimate o validate fisiologicamente.
Il confronto tra estremi non identifica ogni transizione interna: segmenti
con più inversioni o risposte ritardate richiedono revisione visiva.

Curve originali senza smoothing, normalizzazione o interpolazione.
Le mediane in bin servono esclusivamente alla classificazione.
I gap superiori a 1,5 volte il passo mediano interrompono le linee.
Asse temporale comune nel gruppo; HR comune 80–200 bpm (range osservato
87–192); potenza su scala locale, esplicitata nei singoli pannelli.
Le colonne vuote indicano assenza di segmenti di quella classe.
Nelle tavole degli ambigui entrambe le colonne contengono casi da rivedere.
Ogni segmento compare esattamente una volta nelle tavole.

## Risultati

'''
    notes += f"Totale: {len(segments)}. UtD: {summary['counts']['UtD']}; DtU: {summary['counts']['DtU']}; ambigui: {summary['counts']['Ambiguo']}.\n\n"
    notes += 'Soglie candidate (s): ' + ', '.join(map(str, cuts)) + '.\n\n'
    notes += '\n'.join(f'- [{name}]({name})' for name in summary['images']) + '\n'
    (args.output / 'README.md').write_text(notes, encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
