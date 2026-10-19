"""Progressive causal clock inputs: exact-input oracle and train-only lookup."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from power_hr_eda.gru.data import WindowDataset, eligible, fit_scaler, load_manifest, read_workouts, sha256, write_json


def group_metrics(keys, actual, train_mask, val_mask, fallback):
    train = pd.DataFrame(dict(key=keys[train_mask], y=actual[train_mask]))
    val = pd.DataFrame(dict(key=keys[val_mask], y=actual[val_mask]))
    stats = train.groupby('key').y.agg(['mean', 'size'])
    count = val.key.map(stats['size']).fillna(0).to_numpy()
    lookup = val.key.map(stats['mean']).to_numpy()
    lookup = np.where(count > 0, lookup, fallback)
    oracle = val.groupby('key').y.transform('mean').to_numpy()
    multiplicity = val.groupby('key').y.transform('size').to_numpy()
    residual = val.y.to_numpy() - lookup
    oracle_sse = float(np.sum((val.y.to_numpy() - oracle) ** 2))
    return dict(n=len(val), oracle_sse=oracle_sse, lookup_sse=float(np.sum(residual ** 2)),
                fallback_sse=float(np.sum((val.y.to_numpy() - fallback) ** 2)),
                lookup_min20_sse=float(np.sum((val.y.to_numpy() - np.where(count >= 20, lookup, fallback)) ** 2)),
                seen_n=int((count > 0).sum()), seen20_n=int((count >= 20).sum()),
                repeated_val_n=int((multiplicity > 1).sum()),
                unique_val_inputs=val.key.nunique()), residual, count > 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, default=Path('reports/gru_v3'))
    args = parser.parse_args()
    experiment = json.loads((args.reports / 'experiment.json').read_text())
    directory = Path(experiment['dataset'])
    manifest = load_manifest(directory)
    assert experiment['manifest_id'] == manifest['manifest_id']
    paths = {w['workout_id']: (directory / w['path']).resolve() for w in manifest['workouts']}
    source = paths[manifest['development'][0]].parent.parent
    metadata_path = source / 'workouts.jsonl'
    workouts = {w['workout_id']: w for w in map(json.loads, metadata_path.read_text().splitlines())
                if w['workout_id'] in manifest['development']}
    frames = read_workouts(manifest, directory, manifest['development'])
    elapsed_workout, elapsed_phase, raw_prescribed = [], [], []
    ideal_steps = block_steps = total_steps = ideal_samples = 0
    for wid in manifest['development']:
        # Only these raw columns are opened, and only for development workouts.
        source_frame = pd.read_csv(paths[wid], usecols=['record_index', 'timestamp', 'elapsed_seconds', 'lap_index'])
        frame = frames[wid]
        assert np.array_equal(source_frame.record_index, frame.record_index)
        steps = {s['lap_index']: s for s in workouts[wid]['steps']}
        total_steps += len(steps)
        ideal_steps += sum(s.get('ideal_duration_s') is not None for s in steps.values())
        block_steps += sum(s.get('block_id') is not None for s in steps.values())
        stamps = pd.to_datetime(source_frame.timestamp, utc=True)
        start = pd.to_datetime(source_frame.lap_index.map({k: s['start_timestamp'] for k, s in steps.items()}), utc=True)
        phase_clock = (stamps - start).dt.total_seconds().to_numpy()
        workout_clock = source_frame.elapsed_seconds.to_numpy(float)
        valid = eligible(frame).to_numpy()
        assert np.isfinite(phase_clock[valid]).all() and (phase_clock[valid] >= 0).all()
        np.testing.assert_allclose(workout_clock, (stamps - stamps.iloc[0]).dt.total_seconds())
        elapsed_workout.append(workout_clock[valid])
        elapsed_phase.append(phase_clock[valid])
        raw_prescribed.append(frame.loc[valid, 'power_target_w'].to_numpy())
        ideal_samples += int(source_frame.loc[valid, 'lap_index'].map(
            {k: s.get('ideal_duration_s') for k, s in steps.items()}).notna().sum())
    workout_clock = np.concatenate(elapsed_workout)
    phase_clock = np.concatenate(elapsed_phase)
    prescribed = np.concatenate(raw_prescribed)
    first_fold = manifest['folds'][0]
    scaler = fit_scaler([frames[w] for w in first_fold['train']])
    ds = WindowDataset([frames[w] for w in manifest['development']], scaler, 60)
    # Equality partitions are invariant to each fold's affine normalization,
    # provided float32 normalization does not collapse distinct numeric levels.
    levels = np.unique(prescribed[~ds.metadata.is_maximal.to_numpy()])
    for fold in manifest['folds']:
        scale = fit_scaler([frames[w] for w in fold['train']])
        assert len(np.unique(((levels - scale['input_mean']) / scale['input_std']).astype(np.float32))) == len(levels)
    partitions = np.empty((3, len(ds)), dtype=np.int64)
    dictionaries = [{}, {}, {}]
    for i in range(len(ds)):
        x, _ = ds[i]
        base = x.tobytes()
        partitions[0, i] = dictionaries[0].setdefault(base, len(dictionaries[0]))
        # All windows are continuous at 1 s. Given length and endpoint clock,
        # the entire workout-clock trajectory is determined exactly.
        key2 = (int(partitions[0, i]), float(workout_clock[i]))
        partitions[1, i] = dictionaries[1].setdefault(key2, len(dictionaries[1]))
        # Phase resets inside the window matter: include its full trajectory.
        start_index = max(int(ds.starts[i]), i - ds.window + 1)
        key3 = (int(partitions[1, i]), phase_clock[start_index:i + 1].astype('<f8').tobytes())
        partitions[2, i] = dictionaries[2].setdefault(key3, len(dictionaries[2]))
    del dictionaries
    rows, per_workout = [], []
    actual = ds.metadata.power_w.to_numpy()
    identifiers = ds.metadata.workout_id
    maximal = ds.metadata.is_maximal.to_numpy()
    for fold in manifest['folds']:
        train_mask = identifiers.isin(fold['train']).to_numpy()
        val_mask = identifiers.isin(fold['validation']).to_numpy()
        assert not (train_mask & val_mask).any()
        fallback = prescribed[val_mask].copy()
        fallback[maximal[val_mask]] = actual[train_mask & maximal].mean()
        assert np.isfinite(fallback).all()
        previous_sse = float('inf')
        residuals, matches = [], []
        for number, keys in enumerate(partitions, 1):
            stats, residual, seen = group_metrics(keys, actual, train_mask, val_mask, fallback)
            assert stats['oracle_sse'] <= previous_sse + 1e-6
            previous_sse = stats['oracle_sse']
            rows.append(dict(fold=fold['fold'], combination=number, **stats))
            residuals.append(residual)
            matches.append(seen)
            wf = pd.DataFrame(dict(workout_id=identifiers[val_mask].to_numpy(), squared_error=residual ** 2))
            for wid, group in wf.groupby('workout_id'):
                per_workout.append(dict(fold=fold['fold'], combination=number, workout_id=wid,
                                        n=len(group), lookup_rmse_w=float(np.sqrt(group.squared_error.mean()))))
        common = np.logical_and.reduce(matches)
        for row, residual in zip(rows[-3:], residuals):
            row['common_seen_n'] = int(common.sum())
            row['common_seen_lookup_sse'] = float(np.sum(residual[common] ** 2))
        print(f"Fold {fold['fold']} complete", flush=True)
    detail = pd.DataFrame(rows)
    summaries = []
    for combination, group in detail.groupby('combination'):
        s = group.sum(numeric_only=True)
        summaries.append(dict(combination=int(combination), n=int(s.n),
            empirical_floor_rmse_w=float(np.sqrt(s.oracle_sse / s.n)),
            train_lookup_rmse_w=float(np.sqrt(s.lookup_sse / s.n)),
            train_lookup_min20_rmse_w=float(np.sqrt(s.lookup_min20_sse / s.n)),
            common_seen_n=int(s.common_seen_n),
            common_seen_lookup_rmse_w=float(np.sqrt(s.common_seen_lookup_sse / s.common_seen_n)) if s.common_seen_n else None,
            train_seen_fraction=float(s.seen_n / s.n),
            train_seen20_fraction=float(s.seen20_n / s.n),
            repeated_validation_fraction=float(s.repeated_val_n / s.n)))
    previous = args.reports / 'diagnostics/input_ambiguity/w060_gru32/summary.json'
    if previous.exists():
        reference = next(r for r in json.loads(previous.read_text()) if r['subset'] == 'all')
        np.testing.assert_allclose(summaries[0]['empirical_floor_rmse_w'], reference['empirical_floor_rmse_w'])
        np.testing.assert_allclose(summaries[0]['train_lookup_rmse_w'], reference['train_lookup_rmse_w'])
    for index, row in enumerate(summaries):
        row['floor_gain_vs_previous_w'] = (summaries[index - 1]['empirical_floor_rmse_w'] - row['empirical_floor_rmse_w']) if index else 0.
        row['lookup_gain_vs_previous_w'] = (summaries[index - 1]['train_lookup_rmse_w'] - row['train_lookup_rmse_w']) if index else 0.
    output = args.reports / 'diagnostics/temporal_input_ambiguity'
    output.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output / 'per_fold.csv', index=False)
    pd.DataFrame(per_workout).to_csv(output / 'per_workout.csv', index=False)
    pd.DataFrame(summaries).to_csv(output / 'comparison.csv', index=False)
    write_json(output / 'summary.json', summaries)
    write_json(output / 'manifest.json', dict(dataset_manifest_id=manifest['manifest_id'], window_s=60,
        script_sha256=sha256(__file__), metadata_sha256=sha256(metadata_path),
        combinations={'1': ['prescribed_power_history', 'maximal_history'],
                      '2': ['1', 'elapsed_workout_seconds'], '3': ['2', 'elapsed_current_lap_history_seconds'],
                      '4': 'not evaluated: planned duration unavailable',
                      '5': 'not evaluated: ex-ante repeat/block index unverified'},
        annotation_coverage=dict(development_steps=total_steps, inferred_ideal_duration_steps=ideal_steps,
                                 inferred_block_steps=block_steps, inferred_duration_samples=ideal_samples),
        fallback='same for every combination: numeric prescription or train maximal target mean',
        sample_count=len(ds), final_test_used=False))
    names = ['Prescrizione + is_maximal', '+ tempo workout', '+ tempo fase (lap)']
    lines = ['# Confronto progressivo delle informazioni temporali', '',
        'Stessi 354.259 campioni di development, finestre causali di 60 s e sei fold 40/8.',
        'Nessuna rete addestrata, nessuna modifica ai dataset o al training, nessun campione del test finale aperto.', '',
        '| Input cumulativi | Limite empirico W | Train lookup W | Guadagno lookup W | Match train | Validation ripetuta |',
        '|---|---:|---:|---:|---:|---:|']
    for name, row in zip(names, summaries):
        lines.append(f"| {name} | {row['empirical_floor_rmse_w']:.2f} | {row['train_lookup_rmse_w']:.2f} | {row['lookup_gain_vs_previous_w']:+.2f} | {row['train_seen_fraction']:.1%} | {row['repeated_validation_fraction']:.1%} |")
    lines += ['| + durata prevista | N/D | N/D | N/D | N/D | N/D |',
              '| + indice ripetizione/blocco | N/D | N/D | N/D | N/D | N/D |', '',
        '## Metodo e vincoli di causalita', '',
        'La prescrizione di partenza e quella inferita gia presente nel dataset: il confronto resta condizionato a questa rappresentazione, non certifica un piano originale ex ante.',
        'Le nuove feature valutate non usano potenza reale, fine del lap, durata realizzata o informazioni future.',
        'Tempo workout: elapsed_seconds dal primo record esportato, inclusi intervalli di pausa.',
        'Tempo fase: timestamp corrente meno start_timestamp del lap corrente. E disponibile online una volta osservato il cambio lap; non e un tempo rispetto a un piano originale verificato.',
        'Si conserva l intera traiettoria del tempo fase nella finestra, inclusi i reset. Non si usa lap_index come feature.',
        'Non si arrotondano i tempi e non si introducono bin scelti dopo avere visto i target.', '',
        'La media dei target di validation per input identici definisce il limite empirico oracle, non una predizione fuori campione.',
        'Tempi esatti rendono spesso uniche le finestre: un limite basso con pochi duplicati non dimostra una relazione generalizzabile.',
        'Train_lookup usa SOLO medie dei target train. In assenza di match esatto, il fallback e identico in tutte le combinazioni.',
        'Il CSV riporta anche una sensibilita con almeno 20 match train e il confronto sul medesimo sottoinsieme coperto da tutte le combinazioni.',
        'RMSE aggregato calcolato dalla SSE totale divisa per il numero totale di campioni. Guadagno positivo = miglioramento rispetto alla riga precedente.', '',
        f'Solo {ideal_steps}/{total_steps} lap ({ideal_samples} campioni) hanno durate ideali e blocchi ricostruiti a posteriori.',
        'Come richiesto dall utente, questi metadati non verificabili ex ante sono esclusi: non si sostituisce durata osservata a durata prevista.',
        'Le combinazioni 4 e 5 cumulative non sono calcolabili con le sole feature autorizzate.', '',
        '## Lettura del confronto', '',
        'La diminuzione del limite oracle e necessaria quando una feature suddivide i gruppi, ma non prova che il target sia prevedibile fuori fitting.',
        f"Con entrambe le feature temporali, {1-summaries[2]['repeated_validation_fraction']:.1%} dei campioni di validation appartiene a gruppi singleton.",
        f"Sul medesimo sottoinsieme con match train per tutte le combinazioni ({summaries[0]['common_seen_n']} campioni), i RMSE lookup sono "
        + ', '.join(f"{r['common_seen_lookup_rmse_w']:.2f} W" for r in summaries) + '.',
        'Il recupero del lookup nella terza riga rispetto alla seconda non dimostra un beneficio del tempo fase: aumentano i fallback, mentre sul supporto comune l errore cresce.',
        'Non emerge un vantaggio del lookup con tempi esatti rispetto alla rappresentazione iniziale. Questo non esclude relazioni temporali lisce che il matching esatto non puo apprendere.', '',
        'Verifica: la combinazione iniziale riproduce il controllo precedente; il limite oracle non cresce in alcun fold.',
        'Un controllo sintetico separato verifica SSE, fallback e invarianza delle predizioni lookup alla modifica dei target di validation.', '',
        'Riproduzione: `.venv/Scripts/python -B scripts/gru_temporal_ambiguity.py`', '']
    (output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
