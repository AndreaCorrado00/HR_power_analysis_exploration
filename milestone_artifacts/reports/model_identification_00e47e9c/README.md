# Analisi esperimento P1D 00e47e9c

Report tecnico in italiano sui 34 fit train dell'esperimento
`Up_to_Down_under60s`, senza rifitting o uso di validation/test.

- [Report PDF](report_analisi_P1D_00e47e9c.pdf)
- [Metriche per segmento](segment_metrics.csv)
- [Diagnostica delle 272 inizializzazioni](multistart_metrics.csv)
- [Statistiche per attività](activity_metrics.csv)
- [Criteri, statistiche e hash delle sorgenti](summary.json)
- [Hash degli script, figure e PDF](report_build.json)

## Riproduzione

Dalla radice del repository:

```powershell
.\.venv\Scripts\python scripts/report_model_identification.py
```

Il report è specifico della run `00e47e9c0e2b41b0911e978afd611905`.
Sono necessari manifest, risultati e blob originali nello storage dell'app.
I due script sono `scripts/report_model_identification.py` (analisi e figure)
e `scripts/report_model_identification_pdf.py` (composizione del documento).
`--analysis-only` rigenera CSV, statistiche e figure senza il PDF.
Versioni delle librerie registrate in summary.json. Nessuna casualità aggiunta.

## Convenzioni

Segnali originali senza smoothing, HR rossa, potenza blu e previsione verde;
unità e scale esplicite, gap visibili. I grafici di fit usano scale HR locali
per rendere leggibili le differenze; non confrontare le altezze delle curve
fra schede senza leggere gli assi. Le classificazioni sono euristiche post-hoc,
con soglie in summary.json e sensibilità documentata nel report. Nessuna
esclusione automatica; ogni segmento compare in una scheda dell'appendice.

RSE non definito vicino a zero e intervalli che attraversano zero sono conservati.
Le statistiche sono descrittive e condizionate al campione. I 34 segmenti
provengono da cinque attività e non sono repliche indipendenti.
I record ripetuti fra segmenti non vengono eliminati; i conteggi sono espliciti.

## Verifiche

SHA256 delle sorgenti, corrispondenza CSV-serie, ricalcolo metriche e SE,
ricostruzione indipendente ZOH/ritardo per tutte le previsioni e tutti gli start.
Copertura delle 34 schede e controllo del testo PDF; rendering e revisione
visiva delle pagine prima della consegna. Gli intermedi di rendering sono
sotto tmp/pdfs, fuori dagli artefatti finali.
