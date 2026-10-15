"""CLI orchestration: diagnose -> fit/validation -> frozen selection -> test."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from .data import chronological_split, inventory, load_segments, sha256, verify_inputs
from .diagnostics import diagnose
from .fit import ARModel, fit_ar
from .validation import evaluate, macro_metrics

ROOT = Path(__file__).resolve().parents[3]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def provenance(command):
    import matplotlib
    return dict(command=command, utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                numpy=np.__version__, pandas=pd.__version__, matplotlib=matplotlib.__version__,
                code_sha256={p.name: sha256(p) for p in Path(__file__).parent.glob('*.py')})


def verify_dataset(manifest):
    verify_inputs(manifest['records'])
    for path, digest in manifest['dataset_sha256'].items():
        if sha256(path) != digest:
            raise ValueError(f'Dataset file changed: {path}')


def manifest_at(output):
    manifest = read_json(output/'manifest.json')
    verify_dataset(manifest)
    return manifest


def require_coverage(metrics, ids):
    evaluated = set(metrics.loc[metrics.horizon_s.eq(1), 'workout_id'])
    if evaluated != set(ids):
        raise ValueError(f'No one-step evaluation for workouts: {sorted(set(ids)-evaluated)}')


def run_diagnose(args, command):
    source, output = args.input.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        raise ValueError('Output must be outside the input dataset')
    if output.exists():
        raise ValueError('Output already exists; use a new output directory')
    if args.max_lag < 2 or args.max_order < 1:
        raise ValueError('Need max_lag >= 2 and max_order >= 1')
    records = inventory(source)
    split = chronological_split(records, args.train_count, args.validation_count)
    max_order = min(args.max_order, args.max_lag)
    manifest = dict(input=str(source), records=records, split=split,
                    configuration=dict(max_lag=args.max_lag, max_order=max_order, hold_back=max_order,
                                       horizons_s=[1, 10, 30], sampling_seconds=1,
                                       post_change_trim_seconds=0, interpolation=False, filtering=False),
                    dataset_sha256={str(p.resolve()): sha256(p) for p in sorted(source.rglob('*')) if p.is_file()},
                    created=provenance(command))
    output.mkdir(parents=True)
    write_json(output/'manifest.json', manifest)
    write_json(output/'split.json', split)
    membership = []
    for label, ids in split.items():
        for r in records:
            if r['workout_id'] in ids:
                membership.append(dict(split=label, workout_id=r['workout_id'], start_time=r['start_time']))
    pd.DataFrame(membership).to_csv(output/'split.csv', index=False)
    segments, coverage = load_segments(records, split['train'])
    coverage.to_csv(output/'train_coverage.csv', index=False)
    candidates = diagnose(segments, output/'diagnostics', args.max_lag, max_order)
    verify_dataset(manifest)
    print(json.dumps(dict(split_counts={k: len(v) for k, v in split.items()}, candidates=candidates), indent=2))


def save_evaluation(model, segments, ids, output, split):
    metrics = evaluate(model, segments)
    require_coverage(metrics, ids)
    metrics.to_csv(output/f'{split}_metrics_by_workout.csv', index=False)
    macro = macro_metrics(metrics)
    macro['split'], macro['p'], macro['aic'], macro['bic'] = split, model.p, model.aic, model.bic
    return metrics, macro


def run_fit(args, command):
    from .plots import comparison_plot, fit_analysis
    output = args.output.resolve()
    if (output/'test').exists():
        raise ValueError('Final test already opened: order selection is frozen')
    manifest = manifest_at(output)
    config, split = manifest['configuration'], manifest['split']
    orders = sorted(set(args.p or read_json(output/'diagnostics'/'candidates.json')['orders']))
    if not orders or min(orders) < 1 or max(orders) > config['hold_back']:
        raise ValueError(f"Require 1 <= p <= frozen hold_back={config['hold_back']}")
    for p in orders:
        if (output/f'ar_{p}').exists():
            raise ValueError(f'AR({p}) already fitted; use a new output to repeat')
    train, train_coverage = load_segments(manifest['records'], split['train'])
    validation, validation_coverage = load_segments(manifest['records'], split['validation'])
    validation_coverage.to_csv(output/'validation_coverage.csv', index=False)
    for p in orders:
        model = fit_ar(train, p, config['hold_back'])
        trial = output/f'ar_{p}'
        trial.mkdir()
        write_json(trial/'model.json', model.to_dict())
        train_metrics, train_macro = save_evaluation(model, train, split['train'], trial, 'train')
        validation_metrics, validation_macro = save_evaluation(model, validation, split['validation'], trial, 'validation')
        pd.concat([train_macro, validation_macro]).to_csv(trial/'summary.csv', index=False)
        write_json(trial/'manifest.json', dict(provenance=provenance(command), train_ids=split['train'],
                   validation_ids=split['validation'], analyzed=args.analyze, model_sha256=sha256(trial/'model.json')))
        if args.analyze:
            fit_analysis(model, train, validation, validation_metrics, trial/'figures')
        print(f'AR({p}): AIC={model.aic:.2f}, BIC={model.bic:.2f}, stable={model.stable}', flush=True)
    comparison = pd.concat([pd.read_csv(p) for p in sorted(output.glob('ar_*/summary.csv'))], ignore_index=True)
    comparison.sort_values(['p', 'split', 'horizon_s', 'model']).to_csv(output/'comparison.csv', index=False)
    eligible = comparison[(comparison.split == 'validation') & (comparison.horizon_s == 1) & (comparison.model == 'ar')]
    best = eligible.sort_values(['rmse_w', 'p']).iloc[0]
    p = int(best.p)
    selection = dict(p=p, criterion='validation_macro_rmse_h1', rmse_w=float(best.rmse_w),
                     candidate_orders=sorted(eligible.p.astype(int).tolist()),
                     selected_model_sha256=sha256(output/f'ar_{p}'/'model.json'),
                     comparison_sha256=sha256(output/'comparison.csv'),
                     refit_for_test='train_plus_validation_fixed_p_and_hold_back', provenance=provenance(command))
    write_json(output/'selection.json', selection)
    if args.analyze:
        comparison_plot(comparison, output/'order_comparison.png')
    verify_dataset(manifest)
    print(f'Selected AR({p}) by validation macro RMSE h=1: {best.rmse_w:.4f} W. Final test untouched.')


def run_test(args, command):
    from .plots import example_predictions, performance_plot
    output = args.output.resolve()
    if (output/'test').exists():
        raise ValueError('Final test already opened; refusing a repeated final test')
    manifest = manifest_at(output)
    selection = read_json(output/'selection.json')
    p = selection['p']
    if sha256(output/f'ar_{p}'/'model.json') != selection['selected_model_sha256']:
        raise ValueError('Selected model changed after selection')
    if sha256(output/'comparison.csv') != selection['comparison_sha256']:
        raise ValueError('Comparison changed after selection')
    split = manifest['split']
    development, _ = load_segments(manifest['records'], split['train']+split['validation'])
    model = fit_ar(development, p, manifest['configuration']['hold_back'])
    destination = output/'test'
    destination.mkdir()  # locks further selection before reading any test samples
    write_json(destination/'model.json', model.to_dict())
    write_json(destination/'manifest.json', dict(provenance=provenance(command),
               refit_ids=split['train']+split['validation'], test_ids=split['test'],
               selection_sha256=sha256(output/'selection.json')))
    segments, coverage = load_segments(manifest['records'], split['test'])
    coverage.to_csv(destination/'coverage.csv', index=False)
    metrics = evaluate(model, segments)
    require_coverage(metrics, split['test'])
    metrics.to_csv(destination/'metrics_by_workout.csv', index=False)
    macro = macro_metrics(metrics)
    macro.to_csv(destination/'summary.csv', index=False)
    if args.analyze:
        example_predictions(model, segments, destination/'prediction_examples.png')
        performance_plot(metrics, destination/'performance.png', f'AR({p}): test finale, refit su train + validation')
    verify_dataset(manifest)
    write_json(destination/'verification.json', dict(dataset_unchanged=True, selection_frozen=True))
    write_report(output, manifest, selection, model, macro)
    print(macro.to_string(index=False))


def write_report(output, manifest, selection, model, test_macro):
    split_table = pd.read_csv(output/'split.csv', dtype={'workout_id': str})
    lines = ['# Residuo di potenza: AR(p)', '',
             'Target inferito dai dati reali: valutazione condizionata al target ricostruito, non a un piano disponibile a priori.', '',
             '## Split cronologico congelato', '', '| Split | Workout | Primo UTC | Ultimo UTC |', '|---|---:|---|---|']
    for label in ['train', 'validation', 'test']:
        part = split_table[split_table.split == label]
        lines.append(f'| {label} | {len(part)} | {part.start_time.iloc[0]} | {part.start_time.iloc[-1]} |')
    lines += ['', 'Identificativi completi in `split.csv` e `split.json`.', '',
              '## Modello e selezione', '',
              f"AR({selection['p']}) selezionato con RMSE medio per workout di validation a un passo = {selection['rmse_w']:.4f} W.",
              f"Candidati: {selection['candidate_orders']}. Coefficienti ristimati su train + validation prima del test.",
              f'Raggio spettrale finale: {model.spectral_radius:.6f}; stabile: {model.stable}.', '',
              '| p | AIC train | BIC train | RMSE train h=1 [W] | MAE train [W] | RMSE validation [W] | MAE validation [W] |',
              '|---:|---:|---:|---:|---:|---:|---:|']
    comparison = pd.read_csv(output/'comparison.csv')
    for p in selection['candidate_orders']:
        part = comparison[(comparison.p == p) & (comparison.horizon_s == 1) & (comparison.model == 'ar')]
        tr, va = part[part.split == 'train'].iloc[0], part[part.split == 'validation'].iloc[0]
        lines.append(f'| {p} | {tr.aic:.2f} | {tr.bic:.2f} | {tr.rmse_w:.4f} | {tr.mae_w:.4f} | {va.rmse_w:.4f} | {va.mae_w:.4f} |')
    lines += ['', 'AIC/BIC sono del fit training, con likelihood gaussiana condizionale; non sono metriche del test.', '',
              '## Test finale', '', '| Orizzonte [s] | Modello | RMSE medio [W] | MAE medio [W] | Workout | Campioni |',
              '|---:|---|---:|---:|---:|---:|']
    for r in test_macro.itertuples():
        lines.append(f'| {r.horizon_s} | {r.model} | {r.rmse_w:.4f} | {r.mae_w:.4f} | {r.workouts} | {r.samples} |')
    test_rows = pd.read_csv(output/'test'/'metrics_by_workout.csv', dtype={'workout_id': str})
    by_workout = test_rows[test_rows.horizon_s.eq(1)].pivot(index='workout_id', columns='model', values='rmse_w')
    wins = int((by_workout.ar < by_workout.target).sum())
    lines += ['', '## Lettura dei risultati', '',
              f'AR({model.p}) migliora il RMSE a un passo in {wins}/{len(by_workout)} workout del test.',
              'Riduzione del RMSE medio rispetto al target, confrontando gli stessi endpoint a ogni orizzonte:']
    for horizon in sorted(test_macro.horizon_s.unique()):
        part = test_macro[test_macro.horizon_s.eq(horizon)].set_index('model')
        delta = float(part.loc['target', 'rmse_w']-part.loc['ar', 'rmse_w'])
        percentage = 100*delta/part.loc['target', 'rmse_w'] if part.loc['target', 'rmse_w'] else 0.
        lines.append(f'- h={horizon} s: {delta:.4f} W ({percentage:.2f}%; negativo = peggioramento).')
    rank = comparison[(comparison.split == 'validation') & (comparison.horizon_s == 1) & (comparison.model == 'ar')].sort_values('rmse_w')
    if len(rank) > 1:
        lines += ['', f"Distacco tra primo e secondo candidato in validation: {rank.iloc[1].rmse_w-rank.iloc[0].rmse_w:.4f} W di RMSE medio.",
                  'Questa differenza descrittiva non dimostra significativita statistica o superiorita pratica sostanziale.']
    diagnostic_path = output/'diagnostics'/'acf_pacf_summary.csv'
    innovation_path = output/f'ar_{model.p}'/'figures'/'innovation_acf_pacf.csv'
    if diagnostic_path.exists() and innovation_path.exists():
        raw = pd.read_csv(diagnostic_path).set_index('lag_s')
        innovation = pd.read_csv(innovation_path).set_index('lag_s')
        lines += ['', f"ACF mediana training del residuo al lag 1: {raw.loc[1, 'acf_median']:.4f}; delle innovazioni: {innovation.loc[1, 'acf_median']:.4f}.",
                  'Le due sintesi hanno supporti diversi per il margine iniziale del fit. Una ACF mediana piccola non prova che ogni tratto abbia innovazioni bianche.',
                  'Il risultato sostiene l\'uso dell\'AR come approssimazione della persistenza a breve termine; non dimostra che descriva completamente il processo.']
    lines += ['', '## Ipotesi e limiti', '',
              '- AR lineare con intercetta e coefficienti condivisi tra workout, passo nominale di 1 secondo.',
              '- Finestre separate su gap, pausa, invalidita, cambio target e lap; zero watt valido conservato.',
              '- Nessun filtro, interpolazione, detrending o rimozione del transitorio post-cambio.',
              '- ACF/PACF centrate entro tratto solo per diagnostica; fit sul residuo originale, senza usare medie future del tratto.',
              '- PACF Yule-Walker con autocovarianze a denominatore n. Bande nominali individuali 1.96/sqrt(n) solo euristiche.',
              '- Il target costante non garantisce stazionarieta. Innovazioni gaussiane iid omoschedastiche sono un riferimento per IC e errori standard, non un risultato verificato.',
              f"- Supporto comune: primi {model.hold_back} campioni di ogni tratto riservati alla storia per tutti gli ordini.",
              '- Predizioni a origini mobili: h=1 usa i residui osservati passati; h=10/30 ricorre per h passi senza leggere osservazioni future.',
              '- La previsione richiede una storia osservata nel workout nuovo; non simula un intero workout da zero.',
              '- Media delle metriche per workout a peso uguale; fit OLS a peso uguale per campione. Gli endpoint differiscono tra orizzonti, non tra modelli allo stesso orizzonte.',
              '- Ordine scelto solo su validation; test aperto dopo il congelamento. Test non riutilizzato per correzioni modellistiche.',
              '- I workout sono temporalmente distinti ma dello stesso atleta; il target inferito resta un limite alla validita prospettica.', '',
              '## Artefatti', '',
              '- `diagnostics/acf_pacf.png`, `diagnostics/by_workout/`: ACF/PACF training; ogni curva individuale corrisponde a un tratto.',
              '- `diagnostics/segment_curves.npz` e `segments.csv`: valori e corrispondenza delle righe, inclusi casi non analizzabili.',
              '- `ar_*/model.json`: coefficienti, errori standard OLS condizionali, IC e stabilita.',
              '- `ar_*/figures/`: diagnostica innovazioni training, prestazioni validation, esempi prefissati.',
              '- `test/metrics_by_workout.csv`, `test/performance.png`, `test/prediction_examples.png`: valutazione finale.',
              '- `manifest.json`: configurazione, hash dataset e codice, versioni e comando; dataset verificato invariato.', '',
              '## Riferimenti metodologici', '',
              '- https://www.statsmodels.org/stable/generated/statsmodels.tsa.ar_model.AutoReg.html (AR condizionale OLS e supporto comune).',
              '- https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.pacf.html (PACF Yule-Walker).', '']
    (output/'report.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    diagnostic = sub.add_parser('diagnose', help='Freeze split and compute training ACF/PACF')
    diagnostic.add_argument('--input', type=Path, default=ROOT/'data/processed/prescribed_workouts_final')
    diagnostic.add_argument('--train-count', type=int, default=36)
    diagnostic.add_argument('--validation-count', type=int, default=12)
    diagnostic.add_argument('--max-lag', type=int, default=60)
    diagnostic.add_argument('--max-order', type=int, default=20)
    fitting = sub.add_parser('fit', help='Fit AR(p) on train and evaluate validation; never read test values')
    fitting.add_argument('--p', type=int, nargs='+', help='One or more orders; default: diagnostic candidates')
    fitting.add_argument('--analyze', action='store_true', help='Save innovation diagnostics and prediction plots')
    testing = sub.add_parser('test', help='Refit selected p on train+validation; open final test once')
    testing.add_argument('--analyze', action='store_true')
    simulation = sub.add_parser('simulate', help='Fixed-order continuous refit and free stochastic whole-workout simulations')
    simulation.add_argument('--from-run', type=Path, default=ROOT/'reports/power_residual_ar')
    simulation.add_argument('--output', type=Path, default=ROOT/'reports/power_residual_ar_simulation')
    simulation.add_argument('--paths', type=int, default=100)
    simulation.add_argument('--seed', type=int, default=42)
    simulation.add_argument('--analyze', action='store_true', help='Save one full-workout figure per evaluation session')
    for child in [diagnostic, fitting, testing]:
        child.add_argument('--output', type=Path, default=ROOT/'reports/power_residual_ar')
    args = parser.parse_args(argv)
    command = list(sys.argv) if argv is None else list(argv)
    try:
        if args.command == 'simulate':
            from .simulation_run import run
            run(args, command)
        else:
            {'diagnose': run_diagnose, 'fit': run_fit, 'test': run_test}[args.command](args, command)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    return 0
