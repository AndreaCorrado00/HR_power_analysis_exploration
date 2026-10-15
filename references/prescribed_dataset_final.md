# Dataset finale: 60 allenamenti prescritti inferiti

## Artefatti correnti

- Dataset: `data/processed/prescribed_workouts_final/`.
- Grafici: `reports/prescribed_workouts_final_plots/` (PDF 60 pagine e 60 PNG).
- Diagnostica essenziale: `reports/prescription_diagnostics/`.
- Selezione congelata: `references/prescribed_workouts_selection.json`.
- Regole di prescrizione: `references/prescription_rules_v3.json`.
- Evidenza sull'interpolazione: `references/power_gap_interpolation_evidence.md`.

I vecchi dataset generati, i PDF/PNG duplicati e le finestre simulate del benchmark
sono rimossi dopo verifica del nuovo export. L'archivio diagnostico conserva i
manifest e i riepiloghi necessari a interpretare le decisioni. I manifest storici
descrivono le esecuzioni originarie: gli output esplorativi elencati al loro
interno non sono piu' tutti presenti. Il registro di pulizia elenca i percorsi
rimossi. FIT raw, selezione sorgente e altri dataset del progetto restano intatti.

## Decisioni applicate

1. Stessi 60 FIT della selezione precedente, verificati tramite SHA256. Non si
   reincludono gli esclusi: ad esempio `250906154316` resta fuori da questi 60.
2. FTP 325 W, soglie e sottozone definite dall'utente. Media ricalcolata dai
   campioni validi di ciascun lap, inclusi gli zeri; target arrotondato a 5 W.
   Durata usata per plausibilita' e riconoscimento delle ripetute, non per
   aumentare/diminuire la potenza prescritta tramite una curva durata-potenza.
3. Per ripetute compatibili: mediana delle medie dei lap, arrotondata a 5 W,
   condivisa per fase e famiglia nella sessione. Tutti i membri numerici devono
   essere entro il 5% dal valore comune; il 10% resta un confronto esplorativo.
   Durate ideali annotate separatamente, senza deformare i tempi misurati.
4. Media del lap >488 W: massimale categorico, senza inventare un target in watt.
   E' una convenzione del dataset, non prova di massimalita' fisiologica.
5. Tutti i campioni originali mantenuti, anche missing e zeri. Nessuna
   interpolazione, nessun filtro, nessun riempimento temporale o taglio in base
   alla durata. Nessun artefatto sospetto eliminato automaticamente.
6. Segmenti separati di potenza, HR e potenza+HR, interrotti quando il segnale
   richiesto non e' valido, il passo temporale differisce da 1 s, oppure cambia
   lo stato del timer per una pausa con arresto e ripartenza documentati nel FIT.
   Le pause hanno intervallo [stop,start); i campioni presenti durante una pausa
   sono preservati e marcati, in segmenti separati. Nessuna assunzione di zero W
   nel tempo non registrato. Gli stop finali senza ripartenza non definiscono
   un intervallo di pausa delimitato.
7. Tutti i segmenti e frammenti di lap sono conservati; nessuna concatenazione.
   Un frammento non diventa un nuovo lap o una nuova ripetuta. Conservare il
   contesto della sessione e usare split per sessione/tempo nelle analisi future.

La diagnostica precedente contava 355 tratti continui di potenza in base alle
sole assenze del segnale. Il dataset finale separa anche i campioni al cambio
di stato del timer: puo' quindi avere piu' segmenti senza perdere campioni.
I conteggi effettivi sono in `manifest.json`, sezione `summary.segment_counts`.

## Struttura e significato dei campi

- `samples/*.csv.gz`: una tabella per workout, con tutte le colonne osservate
  originali e la prescrizione allineata ai tempi reali. Nessuna riga artificiale.
- `power_observed`: potenza finita e >=0; `hr_observed`: HR finita e >0.
  Sono controlli di disponibilita', non garanzie di plausibilita' fisiologica.
- `power_target_valid`: potenza osservata con prescrizione numerica o massimale.
  `dynamics_target_valid`: richiede anche HR osservata. La maschera non esclude
  automaticamente misure sospette o campioni presenti durante una pausa.
- `timer_paused`: campione compreso in una pausa documentata [stop,start).
- `power_segment_id`, `hr_segment_id`, `dynamics_segment_id`: ID locali alla
  coppia workout/segnale, con 0 riservato ai campioni invalidi per quel segnale.
- `segments.csv`: indice dei segmenti con tempi, indici originali e conteggi.
- `lap_fragments.csv`: relazione segmento-lap e copertura delle righe del lap.
  `all_exported_lap_samples_present` non significa assenza di buchi nella
  registrazione: significa soltanto che tutte le righe esportate sono presenti.
- `timer_pauses.csv`, `power_gaps.csv`: pause e buchi per diagnostica.
- `laps.csv`, `activities.csv`, `workouts.jsonl`: prescrizioni, provenienza e
  struttura; `manifest.json`: regole, hash, riepilogo e metadati di elaborazione.

La scelta di ricostruire le prescrizioni dalla traccia reale non consente di
verificare l'aderenza al piano originale, che non e' disponibile. Medie osservate
e diagnostica non sono ingressi conosciuti prima di un allenamento futuro.

## Diagnostica conservata

La verifica controllata dell'interpolazione ha usato 139.096 finestre e 20
allenamenti successivi separati dai primi 40. Nei buchi reali delimitati, il
96,50% dei secondi mancanti coincide con pause del timer. Queste evidenze
motivano il mantenimento di tratti distinti senza interpolazione; dettagli,
limiti e metriche sono nel documento sull'interpolazione.

Controllo mirato della potenza originale sui 60 FIT: 12 rampe esatte di soli
5 campioni, nessuna piu' lunga; nessuna finestra di 10/20/30 campioni con
ampiezza >=30 W e residuo massimo dalla retta <=2 W. Nessun plateau positivo
di almeno 15 campioni. Rilevati 8 brevi decadimenti vicini al fattore 0,9 per
campione, seguiti da zero, da marcare come sospetti senza attribuzione causale.
Due sequenze controllate erano gia' nel FIT sorgente. Nessuna eliminazione.

Il FIT escluso `250906154316` ha un salto da 41:41 (HR117, potenza0) a 56:03
(HR98, potenza mancante): pausa registrata, non discesa HR misurata per 14 minuti.
La regola grafica finale interrompe le linee sui buchi e sui confini dei segmenti.
Una discesa HR effettivamente campionata con potenza zero non e' esclusa per
la sola forma della curva.

## Riproduzione

Il builder legge direttamente i FIT selezionati e rifiuta output gia' esistenti.
Per ripetere l'export usare una directory nuova, per esempio:

```powershell
.venv/Scripts/python -B scripts/build_prescribed_dataset.py --output data/processed/prescribed_workouts_rebuilt
.venv/Scripts/python -B scripts/plot_prescribed_workouts.py --input data/processed/prescribed_workouts_rebuilt --output reports/prescribed_workouts_rebuilt_plots
.venv/Scripts/python -B -m pytest tests --ignore=tests/_generated -q -p no:cacheprovider
```

Il codice e le configurazioni dei precedenti esperimenti sono conservati per
riproducibilita'; le loro vecchie directory di output non sono dataset correnti.
