# Esperimento congiunto prescribed 42/9/9

Aprire [index.html](index.html) in Edge o Chrome, anche senza server.
La pagina legge `results/results.js`; il report è `results/report.md`.
Gli output sono locali e ignorati da Git. Il codice e il protocollo sono versionabili.
Sintesi persistente dell'esperimento: [RESULTS.md](RESULTS.md).

## Riproduzione dalla radice

```powershell
.venv/Scripts/python -B -m experiments.prescribed_joint.run prepare
.venv/Scripts/python -B -m power_response_estimation fit --output experiments/prescribed_joint/results/power --split-file experiments/prescribed_joint/results/split.json --paths 1000
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.venv/Scripts/python -B -m experiments.prescribed_joint.run hr --workers 3
.venv/Scripts/python -B -m experiments.prescribed_joint.run evaluate --split validation
.venv/Scripts/python -B -m experiments.prescribed_joint.run evaluate --split test
.venv/Scripts/python -B -m pytest tests/test_prescribed_joint.py -q -p no:cacheprovider
```

Il fitting potenza rifiuta di sovrascrivere un modello esistente. HR riprende
solo fit di questo esperimento con hash dati/config/codice identici. Lo storage
della web app e il modello storico power_response non vengono modificati.
Il test richiede la validation e il congelamento dei modelli; i relativi hash
devono coincidere. Per un nuovo esperimento utilizzare una copia separata degli
output e una nuova configurazione esplicita; non cancellare risultati storici.
Per riprendere fit interrotti usare lo stesso ambiente numerico: le versioni sono
registrate nel modello finale, ma non entrano nella firma di ogni fit in cache.

`manifest.json`: split, hash sorgenti, tratti e qualità. `hr_fits/`: fitting e
diagnostica di ogni tratto train, inclusi i fallimenti. `hr_model.json`: screening,
REML, riferimenti iniziali e baseline statica. `power/`: modello e selezione.
`validation.json` / `test.json`: serie complete, metriche per workout e aggregate,
fallimenti e diagnostica Monte Carlo. `*_metrics.csv`: metriche esportabili.
`results.js` arrotonda soltanto le serie visualizzate a quattro decimali;
metriche e artefatti JSON mantengono la precisione numerica originale.

Perimetro, equazioni, fitting, assunzioni e limiti: [PROTOCOL.md](PROTOCOL.md).
Non è un test vergine: i target sono ricostruiti e i dati già esaminati storicamente.
