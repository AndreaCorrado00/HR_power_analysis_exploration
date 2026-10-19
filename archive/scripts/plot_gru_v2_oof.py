"""Reproduce two descriptive OOF examples from completed GRU fold artifacts."""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from power_hr_eda.gru.data import eligible, fit_scaler, load_manifest, read_workouts, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, default=Path('reports/gru_v2'))
    parser.add_argument('--configuration', default='w030_gru32')
    args = parser.parse_args()
    experiment = json.loads((args.reports / 'experiment.json').read_text())
    dataset = Path(experiment['dataset'])
    manifest = load_manifest(dataset)
    assert manifest['manifest_id'] == experiment['manifest_id']
    frames = read_workouts(manifest, dataset, manifest['development'])
    output = args.reports / 'diagnostics' / args.configuration
    output.mkdir(parents=True, exist_ok=True)
    predictions, fold_rows, sources = [], [], []
    for fold in manifest['folds']:
        directory = args.reports / 'configurations' / args.configuration / f"fold_{fold['fold']:02d}"
        run = json.loads((directory / 'run.json').read_text())
        result = json.loads((directory / 'result.json').read_text())
        assert result['complete'], 'Only completed folds are supported'
        assert run['manifest_id'] == manifest['manifest_id']
        assert run['split'] == fold
        assert not set(fold['train']) & set(fold['validation'])
        assert fit_scaler([frames[w] for w in fold['train']]) == run['scaler']
        history = json.loads((directory / 'metrics/history.json').read_text())
        best = next(h for h in history if h['epoch'] == result['best_epoch'])
        path = directory / 'predictions/validation_predictions.csv.gz'
        p = pd.read_csv(path, dtype={'workout_id': str})
        assert set(p.workout_id) == set(fold['validation'])
        original = pd.concat([frames[w].loc[eligible(frames[w])] for w in fold['validation']])
        assert not p.duplicated(['workout_id', 'record_index']).any()
        p = p.merge(original[['workout_id', 'record_index', 'power_w', 'power_target_w', 'prescription_kind']],
                    on=['workout_id', 'record_index'], validate='one_to_one', suffixes=('', '_source'))
        assert len(p) == len(original)
        np.testing.assert_allclose(p.power_w, p.power_w_source)
        assert np.array_equal(p.is_maximal, p.prescription_kind.eq('maximal'))
        np.testing.assert_allclose(p.residual_w, p.predicted_w - p.power_w, atol=1e-10)
        np.testing.assert_allclose(np.sqrt(np.mean(p.residual_w ** 2)), best['validation']['global']['rmse_w'])
        p.loc[p.is_maximal, 'power_target_w'] = np.nan
        p['fold'] = fold['fold']
        p['best_epoch'] = result['best_epoch']
        predictions.append(p)
        sources.append(dict(path=str(path), sha256=sha256(path), best_epoch=result['best_epoch']))
        row = dict(fold=fold['fold'], best_epoch=result['best_epoch'], completed_epochs=len(history))
        for split in ['train', 'validation']:
            frame = pd.concat([frames[w].loc[eligible(frames[w])] for w in fold[split]])
            numeric = frame[frame.prescription_kind.eq('power')]
            row[f'{split}_n'] = len(frame)
            row[f'{split}_numeric_n'] = len(numeric)
            row[f'{split}_baseline_rmse_w'] = float(np.sqrt(np.mean((numeric.power_w - numeric.power_target_w) ** 2)))
            row[f'{split}_gru_numeric_rmse_w'] = best[split]['nonmaximal']['rmse_w']
            row[f'{split}_gru_all_rmse_w'] = best[split]['global']['rmse_w']
        fold_rows.append(row)
    all_predictions = pd.concat(predictions, ignore_index=True)
    assert not all_predictions.duplicated(['workout_id', 'record_index']).any()
    scores = all_predictions.groupby('workout_id').agg(
        fold=('fold', 'first'), best_epoch=('best_epoch', 'first'), n=('power_w', 'size'),
        rmse_w=('residual_w', lambda s: float(np.sqrt(np.mean(s ** 2)))))
    assert len(scores) == len(manifest['development'])
    scores.to_csv(output / 'oof_workout_metrics.csv')
    pd.DataFrame(fold_rows).to_csv(output / 'fold_diagnostics.csv', index=False)
    selected = [('median', (scores.rmse_w - scores.rmse_w.median()).abs().sort_values(kind='stable').index[0]),
                ('worst', scores.rmse_w.idxmax())]
    artifacts = []
    for label, wid in selected:
        sub = all_predictions[all_predictions.workout_id.eq(wid)].copy()
        sub['timestamp'] = pd.to_datetime(sub.timestamp, utc=True)
        sub = sub.sort_values('timestamp')
        sub['minutes'] = (sub.timestamp - sub.timestamp.iloc[0]).dt.total_seconds() / 60
        # Never connect samples across gaps. Zoom is the central five minutes of
        # the longest continuous segment, independent of the residual magnitude.
        sub['plot_segment'] = (sub.timestamp.diff().dt.total_seconds().ne(1)
                               | sub.segment_start_index.ne(sub.segment_start_index.shift())).cumsum()
        longest = max((g for _, g in sub.groupby('plot_segment')), key=len)
        middle = (longest.minutes.iloc[0] + longest.minutes.iloc[-1]) / 2
        lo, hi = max(longest.minutes.iloc[0], middle - 2.5), min(longest.minutes.iloc[-1], middle + 2.5)
        fig, axes = plt.subplots(3, 1, figsize=(15, 10), gridspec_kw={'height_ratios': [1.2, 1, .7]})
        for axis in axes[:2]:
            for number, (_, segment) in enumerate(sub.groupby('plot_segment')):
                axis.plot(segment.minutes, segment.power_w, color='0.55', lw=.65, alpha=.8,
                          label='Potenza reale' if number == 0 else None)
                axis.plot(segment.minutes, segment.power_target_w, color='#d97706', lw=1.5, ls='--',
                          label='Prescrizione numerica' if number == 0 else None)
                axis.plot(segment.minutes, segment.predicted_w, color='#0369a1', lw=1.2,
                          label='Predizione OOF' if number == 0 else None)
            axis.set_ylabel('Potenza (W)')
            axis.grid(alpha=.2)
            axis.legend(loc='upper right', ncol=3, fontsize=9)
        axes[0].axvspan(lo, hi, color='#0369a1', alpha=.10, label='Zoom')
        axes[0].set_title('Workout completo; area azzurra = dettaglio sotto', loc='left', fontsize=10)
        axes[1].set_xlim(lo, hi)
        axes[1].set_title('Dettaglio centrale di 5 minuti del segmento continuo piu lungo', loc='left', fontsize=10)
        for _, segment in sub.groupby('plot_segment'):
            axes[2].plot(segment.minutes, segment.residual_w, color='#0369a1', lw=.8)
        axes[2].axhline(0, color='black', lw=.7)
        axes[2].set(xlim=(lo, hi), ylabel='Residuo (W)')
        axes[2].grid(alpha=.2)
        for axis in axes:
            axis.set_xlabel('Minuti dal primo campione valutato')
        # Shade maximal stretches without assigning any numeric prescription.
        maximal_runs = sub.is_maximal.ne(sub.is_maximal.shift()).cumsum()
        for _, segment in sub.groupby(maximal_runs):
            if segment.is_maximal.iloc[0]:
                for axis in axes:
                    axis.axvspan(segment.minutes.iloc[0], segment.minutes.iloc[-1] + 1/60,
                                 color='#9333ea', alpha=.12)
        score = scores.loc[wid]
        title = 'Caso vicino alla mediana' if label == 'median' else 'Caso con RMSE maggiore'
        fig.suptitle(f"{title}: {wid} | {args.configuration} | fold {int(score.fold):02d} | "
                     f"epoca {int(score.best_epoch)} | RMSE {score.rmse_w:.2f} W", fontsize=13)
        fig.text(.01, .012, 'Campioni a 1 s, senza smoothing. Viola: massimali, prescrizione numerica assente. '
                 'OOF di development: questi fold hanno anche selezionato la migliore epoca.', fontsize=9)
        fig.tight_layout(rect=(0, .04, 1, .95))
        image_path = output / f'oof_{label}_{wid}.png'
        fig.savefig(image_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        artifacts.append(dict(selection=label, workout_id=wid, fold=int(score.fold),
                              best_epoch=int(score.best_epoch), rmse_w=float(score.rmse_w),
                              zoom_minutes=[float(lo), float(hi)], image=str(image_path)))
    write_json(output / 'manifest.json', dict(configuration=args.configuration,
        dataset_manifest_id=manifest['manifest_id'], script_sha256=sha256(__file__),
        selection='closest to median workout RMSE and largest workout RMSE; ties follow workout ID',
        sources=sources, examples=artifacts))
    numeric = all_predictions[~all_predictions.is_maximal]
    baseline = np.sqrt(np.mean((numeric.power_w - numeric.power_target_w) ** 2))
    gru = np.sqrt(np.mean(numeric.residual_w ** 2))
    (output / 'README.md').write_text(
        '# Esempi OOF e diagnosi dei fold\n\n'
        f'Configurazione: {args.configuration}. Copertura: {len(scores)} workout di development, '
        f'{len(all_predictions)} campioni. Test finale non usato.\n\n'
        f'RMSE sui medesimi campioni non massimali: baseline {baseline:.2f} W, GRU {gru:.2f} W. '
        'Le differenze tra fold sono confrontabili in fold_diagnostics.csv. '
        'La baseline non e definita sui massimali.\n\n'
        'I grafici usano le predizioni originali salvate dalla migliore epoca di ogni fold. '
        'Sono OOF rispetto al fitting dei pesi; la validation ha anche selezionato la migliore epoca, '
        'quindi non costituiscono una stima indipendente dopo la selezione. '
        'Il caso peggiore e scelto per RMSE per workout, non per contributo totale alla SSE. '
        'Nessun smoothing, ricampionamento o riaddestramento.\n\n'
        'Verificati hash dei dati, scaler fit sul solo train, split disgiunti, copertura OOF unica, '
        'corrispondenza dei target e riproduzione delle metriche salvate.\n\n'
        'Riproduzione dalla root: `.venv/Scripts/python -B scripts/plot_gru_v2_oof.py`\n', encoding='utf-8')
    print(json.dumps(artifacts, indent=2))


if __name__ == '__main__':
    main()
