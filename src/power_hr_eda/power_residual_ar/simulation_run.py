"""Fixed-order continuous refit and descriptive free-simulation experiment."""
from pathlib import Path

import pandas as pd

from .data import load_segments, sha256
from .fit import fit_ar
from .simulation import plot_workout, simulate_workout, stationary_state, summarize_workout


def run(args, command):
    from .cli import manifest_at, provenance, read_json, verify_dataset, write_json
    source, output = args.from_run.resolve(), args.output.resolve()
    manifest = manifest_at(source)
    verification_path = source/'test'/'verification.json'
    if not verification_path.exists():
        raise ValueError('Free-simulation follow-up requires a completed original final test; unopened test remains protected')
    verification = read_json(verification_path)
    if not verification.get('dataset_unchanged') or not verification.get('selection_frozen'):
        raise ValueError('Original final test verification is incomplete')
    if read_json(source/'test'/'manifest.json')['selection_sha256'] != sha256(source/'selection.json'):
        raise ValueError('Original selection changed after final test')
    dataset = Path(manifest['input']).resolve()
    if output.exists() or dataset == output or dataset in output.parents or source in output.parents:
        raise ValueError('Simulation output must be a new directory outside input data and original run')
    if args.paths < 2 or args.seed < 0:
        raise ValueError('Require paths >= 2 and seed >= 0')
    selection = read_json(source/'selection.json')
    if sha256(source/'comparison.csv') != selection['comparison_sha256']:
        raise ValueError('Original selection comparison changed')
    order = int(selection['p'])
    split = manifest['split']
    training, train_coverage = load_segments(manifest['records'], split['train'], split_at_prescription=False)
    train_model = fit_ar(training, order, hold_back=order)
    stationary_state(train_model)  # refuse unstable fits before creating artifacts
    output.mkdir(parents=True)
    train_coverage.to_csv(output/'train_coverage.csv', index=False)
    write_json(output/'train_model.json', train_model.to_dict())
    run_manifest = dict(source_run=str(source), source_manifest_sha256=sha256(source/'manifest.json'),
        source_selection_sha256=sha256(source/'selection.json'), provenance=provenance(command), split=split,
        configuration=dict(p=order, p_selection='Inherited from previous validation; not retuned',
            split_at_prescription=False, transient_model=False, transient_samples_removed=False,
            fit_hold_back=order, seed=args.seed, paths=args.paths, example_path_index=0,
            innovations='iid Gaussian, zero mean, fitted conditional variance',
            initialization='Exact stationary Gaussian state at start of each valid continuous segment',
            observed_residual_feedback=False, clip_negative_power=False),
        interpretation='Test already examined in previous experiment; descriptive follow-up, not a fresh final test')
    write_json(output/'manifest.json', run_manifest)
    summaries = []
    for phase, ids in [('validation', split['validation']), ('test_descriptive', split['test'])]:
        if phase == 'validation':
            model = train_model
        else:
            development, _ = load_segments(manifest['records'], split['train']+split['validation'], split_at_prescription=False)
            model = fit_ar(development, order, hold_back=order)
            stationary_state(model)
            write_json(output/'final_model.json', model.to_dict())
        dest = output/phase
        dest.mkdir()
        segments, coverage = load_segments(manifest['records'], ids, split_at_prescription=False)
        coverage.to_csv(dest/'coverage.csv', index=False)
        rows = []
        mean, _ = stationary_state(model)
        for wid in ids:
            parts = [s for s in segments if s.workout_id == wid]
            if not parts:
                raise ValueError(f'No eligible continuous segment in {wid}')
            generated = simulate_workout(model, parts, seed=args.seed, paths=args.paths)
            table, metrics = summarize_workout(parts, generated, float(mean[0]))
            table.to_csv(dest/f'{wid}.csv.gz', index=False)
            rows.append(metrics)
            if args.analyze:
                plot_workout(table, dest/f'{wid}.png', wid, args.paths)
        frame = pd.DataFrame(rows)
        frame.to_csv(dest/'metrics_by_workout.csv', index=False)
        macro = frame.drop(columns=['workout_id']).mean().to_dict()
        macro.update(phase=phase, workouts=len(ids), total_samples=int(frame.n_samples.sum()))
        summaries.append(macro)
        print(f'{phase}: {len(ids)} entire workouts simulated, {int(frame.n_samples.sum())} valid samples; p={order}', flush=True)
    pd.DataFrame(summaries).to_csv(output/'summary.csv', index=False)
    verify_dataset(manifest)
    write_json(output/'verification.json', dict(dataset_unchanged=True, original_run_unchanged=True,
        selection_unchanged=sha256(source/'selection.json') == run_manifest['source_selection_sha256']))
    write_report(output, run_manifest, summaries)


def write_report(output, manifest, summaries):
    config = manifest['configuration']
    lines = ['# Simulazione libera del residuo sull\'intero workout', '',
        f"AR({config['p']}) con ordine ereditato dalla precedente validation, senza nuova ricerca di p.",
        'Fit sul residuo e = P_reale - P_prescritta; ricostruzione P_simulata = P_prescritta + e_simulato.', '',
        '## Protocollo', '',
        '- Coefficienti ristimati sui tratti continui attraversando cambi di target e lap.',
        '- Nessun termine per il transitorio e nessun campione rimosso perche vicino a un cambio: tali campioni contribuiscono al fit.',
        '- ACF/PACF originarie per la scelta esplorativa restano separate ai cambi; non sono ricalcolate per scegliere un nuovo ordine.',
        f"- Hold-back del fit ridotto a p={config['p']}, soltanto dopo vere interruzioni. Ogni campione valido e simulato, incluso l'inizio.",
        '- Nessun residuo osservato inizializza o aggiorna le traiettorie. Stato iniziale estratto dalla distribuzione stazionaria gaussiana del modello.',
        '- Innovazioni iid gaussiane a media zero e varianza stimata nel fit. Coefficienti e varianza invarianti durante il workout.',
        f"- {config['paths']} traiettorie, seed {config['seed']}; nei grafici sempre la prima, senza selezione per somiglianza.",
        '- Nessun clipping o smoothing. Potenze negative generate sono conservate e quantificate come limite del modello.',
        '- Reset solo ai gap, pause, potenza/target non validi; target non numerici non simulabili. La maschera di disponibilita viene dal dataset osservato.',
        f"- Split cronologico invariato: training {len(manifest['split']['train'])}, validation {len(manifest['split']['validation'])}, test {len(manifest['split']['test'])} (ID nel manifest).",
        '- Validation: modello stimato solo sul training. Test descrittivo: refit su training+validation, a ordine fisso.',
        '- Il test e gia stato osservato: questi risultati non costituiscono un nuovo test indipendente.', '',
        '## Interpretazione delle metriche', '',
        'Una traiettoria casuale non deve allinearsi ai picchi della traccia osservata. RMSE/MAE della prima simulazione sono esportati per trasparenza, non usati per scegliere il seed o giudicare da soli la dinamica.',
        'La previsione media libera vale target + media stazionaria del residuo. Si riportano anche deviazione standard e ACF entro tratti, e copertura delle bande P10-P90 puntuali.',
        'Le bande non includono incertezza sui coefficienti, non sono simultanee per tutto il workout e presuppongono il modello gaussiano.', '',
        '| Fase | RMSE medio libero [W] | RMSE target [W] | SD residuo osservato [W] | SD simulata mediana [W] | Potenze simulate negative |',
        '|---|---:|---:|---:|---:|---:|']
    for row in summaries:
        lines.append(f"| {row['phase']} | {row['mean_prediction_rmse_w']:.3f} | {row['baseline_rmse_w']:.3f} | {row['observed_residual_sd_w']:.3f} | {row['simulated_sd_median_w']:.3f} | {100*row['simulated_negative_power_fraction']:.2f}% |")
    lines += ['', 'Medie a peso uguale per workout. CSV con MAE, bias, ACF a lag 1/5/10/30 e risultati per singola sessione.', '',
        '## Limiti', '',
        'Il target e ricostruito dalla potenza reale. La simulazione e quindi condizionata a tale ricostruzione, non a un piano realmente conosciuto prima della partenza.',
        'Un residuo stazionario condiviso puo non rappresentare differenze di dispersione tra sessioni, intensita o fasi. I transitori non modellati restano nei dati e possono contribuire alla varianza stimata.',
        '## Artefatti', '',
        '- `validation/` e `test_descriptive/`: una figura dell\'intero workout e un CSV compresso per sessione.',
        '- `train_model.json`, `final_model.json`: coefficienti, varianza, stabilita e IC del nuovo fit continuo.',
        '- `manifest.json`: split, modello, inizializzazione, seed, versioni e provenienza.', '']
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
