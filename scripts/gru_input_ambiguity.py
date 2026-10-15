"""Descriptive exact-input error bounds; no model fitting on final test data."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from power_hr_eda.gru.data import WindowDataset, eligible, fit_scaler, load_manifest, read_workouts, sha256, write_json


def summarize(frame, subset, fold):
    groups = frame.groupby('key')
    mean = groups.power_w.transform('mean')
    count = groups.power_w.transform('size')
    numeric = frame[~frame.is_maximal]
    return dict(fold=fold, subset=subset, n=len(frame), unique_histories=frame.key.nunique(),
                repeated_n=int(count.gt(1).sum()), train_seen_n=int(frame.train_count.gt(0).sum()),
                oracle_sse=float(((frame.power_w - mean) ** 2).sum()),
                gru_sse=float(((frame.power_w - frame.predicted_w) ** 2).sum()),
                train_lookup_sse=float(((frame.power_w - frame.lookup_prediction) ** 2).sum()),
                baseline_sse=float(((numeric.power_w - numeric.prescribed_w) ** 2).sum()),
                numeric_n=len(numeric))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, default=Path('reports/gru_v3'))
    parser.add_argument('--configuration', default='w060_gru32')
    args = parser.parse_args()
    experiment = json.loads((args.reports / 'experiment.json').read_text())
    directory = Path(experiment['dataset'])
    manifest = load_manifest(directory)
    assert manifest['manifest_id'] == experiment['manifest_id']
    frames = read_workouts(manifest, directory, manifest['development'])
    output = args.reports / 'diagnostics' / 'input_ambiguity' / args.configuration
    output.mkdir(parents=True, exist_ok=True)
    rows, examples, sources, coverage = [], [], [], []
    for fold in manifest['folds']:
        run_dir = args.reports / 'configurations' / args.configuration / f"fold_{fold['fold']:02d}"
        run = json.loads((run_dir / 'run.json').read_text())
        result = json.loads((run_dir / 'result.json').read_text())
        assert result['complete'] and run['split'] == fold
        assert run['manifest_id'] == manifest['manifest_id']
        assert not set(fold['train']) & set(fold['validation'])
        assert fit_scaler([frames[w] for w in fold['train']]) == run['scaler']
        assert sha256(Path('src/power_hr_eda/gru/data.py')) == run['environment']['code']['data.py']
        window = run['config']['window']
        ds = WindowDataset([frames[w] for w in manifest['development']], run['scaler'], window)
        keys = {}
        ids, constant = [], []
        for i in range(len(ds)):
            x, _ = ds[i]
            # Byte length encodes context length; both normalized float32 input
            # channels and their full causal ordering participate in equality.
            ids.append(keys.setdefault(x.tobytes(), len(keys)))
            constant.append(len(x) == window and np.all(x == x[0]))
        meta = ds.metadata.copy()
        meta['key'] = ids
        meta['constant'] = constant
        meta['prescribed_w'] = np.concatenate([
            frames[w].loc[eligible(frames[w]), 'power_target_w'].to_numpy()
            for w in manifest['development']])
        meta.loc[meta.is_maximal, 'prescribed_w'] = np.nan
        train = meta[meta.workout_id.isin(fold['train'])]
        val = meta[meta.workout_id.isin(fold['validation'])]
        prediction_path = run_dir / 'predictions/validation_predictions.csv.gz'
        saved = pd.read_csv(prediction_path, dtype={'workout_id': str})
        assert set(saved.workout_id) == set(fold['validation'])
        val = val.merge(saved[['workout_id', 'record_index', 'power_w', 'predicted_w']],
                        on=['workout_id', 'record_index'], validate='one_to_one', suffixes=('', '_saved'))
        assert len(val) == len(saved) == int(meta.workout_id.isin(fold['validation']).sum())
        np.testing.assert_allclose(val.power_w, val.power_w_saved)
        report = json.loads((run_dir / 'metrics/validation_metrics.json').read_text())
        np.testing.assert_allclose(np.sqrt(np.mean((val.power_w - val.predicted_w) ** 2)), report['global']['rmse_w'])
        means = train.groupby('key').power_w.mean()
        val['train_count'] = val.key.map(train.groupby('key').size()).fillna(0)
        val['lookup_prediction'] = val.key.map(means).fillna(val.prescribed_w).fillna(
            train.loc[train.is_maximal, 'power_w'].mean())
        assert np.isfinite(val.lookup_prediction).all()
        spread = val.groupby('key').predicted_w.agg(lambda x: x.max() - x.min()).max()
        assert spread < .001, 'Identical inputs should give identical predictions within numerical tolerance'
        for name, mask in [('all', np.ones(len(val), bool)), ('constant_full_window', val.constant),
                           ('varying_or_short', ~val.constant), ('numeric', ~val.is_maximal),
                           ('maximal', val.is_maximal)]:
            rows.append(summarize(val.loc[mask], name, fold['fold']))
        groups = val[val.constant & ~val.is_maximal].groupby('key')
        table = groups.agg(n=('power_w', 'size'), workouts=('workout_id', 'nunique'),
                          prescribed_w=('prescribed_w', 'first'), real_mean_w=('power_w', 'mean'),
                          real_sd_w=('power_w', lambda x: x.std(ddof=0)),
                          real_p05_w=('power_w', lambda x: x.quantile(.05)),
                          real_p95_w=('power_w', lambda x: x.quantile(.95)),
                          prediction_w=('predicted_w', 'mean'),
                          prediction_sd_w=('predicted_w', lambda x: x.std(ddof=0)))
        table['fold'] = fold['fold']
        examples.append(table.reset_index())
        sources.append(dict(path=str(prediction_path), sha256=sha256(prediction_path),
                            best_epoch=result['best_epoch'], max_prediction_spread_w=float(spread)))
        coverage.extend(zip(val.workout_id, val.record_index))
        print(f"Fold {fold['fold']}: {len(val)} validation samples, {len(keys)} unique development histories", flush=True)
    assert len(coverage) == len(set(coverage))
    assert {w for w, _ in coverage} == set(manifest['development'])
    detail = pd.DataFrame(rows)
    detail.to_csv(output / 'per_fold.csv', index=False)
    pd.concat(examples).sort_values(['fold', 'n'], ascending=[True, False]).to_csv(output / 'constant_input_groups.csv', index=False)
    summary = []
    for name, group in detail.groupby('subset', sort=False):
        s = group.sum(numeric_only=True)
        summary.append(dict(subset=name, n=int(s.n), repeated_fraction=float(s.repeated_n / s.n),
            train_seen_fraction=float(s.train_seen_n / s.n),
            empirical_floor_rmse_w=float(np.sqrt(s.oracle_sse / s.n)),
            gru_rmse_w=float(np.sqrt(s.gru_sse / s.n)),
            floor_fraction_of_gru_sse=float(s.oracle_sse / s.gru_sse),
            train_lookup_rmse_w=float(np.sqrt(s.train_lookup_sse / s.n)),
            baseline_numeric_rmse_w=float(np.sqrt(s.baseline_sse / s.numeric_n)) if s.numeric_n else None))
    write_json(output / 'summary.json', summary)
    write_json(output / 'manifest.json', dict(configuration=args.configuration, window_s=window,
        dataset_manifest_id=manifest['manifest_id'], sources=sources, script_sha256=sha256(__file__),
        oracle_grouping='exact normalized float32 input windows, including length; separately within each validation fold',
        selection='all six completed folds; all development workouts; no final test samples'))
    lines = ['# Variabilita del target a ingressi identici', '',
        'Si confrontano tutte le finestre effettive della rete, inclusi ordine, lunghezza e flag maximal.',
        'La costanza e verificata sulla finestra intera: include anche i tratti iniziali senza una transizione precedente.', '',
        '| Sottoinsieme | Campioni | Limite empirico RMSE W | GRU RMSE W | Quota SSE del limite |',
        '|---|---:|---:|---:|---:|']
    for row in summary:
        lines.append(f"| {row['subset']} | {row['n']} | {row['empirical_floor_rmse_w']:.2f} | {row['gru_rmse_w']:.2f} | {row['floor_fraction_of_gru_sse']:.2%} |")
    lines += ['', '## Interpretazione e limiti', '',
        'Il limite usa, per ogni gruppo di input identici, la media dei target della validation stessa.',
        'Minimizza la SSE su questi campioni per qualunque funzione deterministica degli stessi input.',
        'E un oracle descrittivo a posteriori, NON una previsione fuori campione o una stima del rumore fisiologico.',
        'I gruppi sono separati per fold: le predizioni di modelli diversi non vengono confuse.',
        'I gruppi singleton hanno errore oracle nullo: il limite e particolarmente ottimistico per storie rare/dinamiche.',
        'La quota SSE non e una percentuale di RMSE. La selezione delle epoche ha gia usato questi fold.', '',
        'Come controllo fuori fitting dei target di validation, train_lookup usa medie apprese SOLO sui gruppi del train.',
        'Per input mai visti usa la prescrizione numerica, oppure la media dei target massimali del train.',
        'I massimali non ricevono mai un target numerico di prescrizione. Tutte le metriche sono in watt.',
        'Non vengono introdotte covariate, modificati dati o riaddestrati modelli. Il test finale non viene valutato.', '',
        'Riproduzione: `.venv/Scripts/python -B scripts/gru_input_ambiguity.py`', '']
    (output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
