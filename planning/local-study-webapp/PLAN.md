# Webapp locale dello studio — piano d'implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: usare `superpowers:executing-plans`
> per eseguire il piano task per task nella sessione principale. Nessuna delega
> implicita. Le caselle indicano lavoro futuro, non autorizzazione a eseguirlo.

**Goal:** costruire la webapp locale richiesta, preservando lo studio precedente
e lasciando all'utente la prima identificazione su un dataset nuovo.

**Architecture:** Vue e API Python locali, dati separati per atleta, indice SQLite
e artefatti immutabili su filesystem. Nucleo numerico congelato estratto con
provenienza; job di fitting solo su comando esplicito dell'utente.

**Tech Stack:** stack già presente Vue 3, TypeScript, ECharts, Vite/Vitest,
Python, NumPy/SciPy/pandas, FastAPI/Uvicorn, fitdecode; SQLite standard library.
Versioni effettive bloccate nei manifest/lock prima dell'esecuzione.

**Spec:** [SPEC.md](SPEC.md). **Controllo:** [CONTROL.md](CONTROL.md).
Data: 18 ottobre 2026. Stato: autorizzato il 18 ottobre 2026, decisioni D1-D4 registrate in CONTROL.md.

## Vincoli globali

- Nessun fitting o ristima avviato dall'agente, neppure nei test.
- Nessun avvio automatico di fit all'importazione o all'avvio dell'app.
- Nessun dato reale copiato nel nuovo storage come demo.
- Nessuna alterazione di raw, artefatti storici o equazioni congelate.
- Nessuna interpolazione dei dati osservati, covariata o modello nuovi.
- Configurazioni, regole, split e versioni sono persistenti e immutabili nelle run.
- Prima dell'implementazione serve l'approvazione del piano; D1–D4 vanno risolte
  prima delle parti dipendenti. Le parti indipendenti possono avanzare.
- Ogni task termina con verifica e rendicontazione circoscritte. Nessun commit
  deve includere dati privati o artefatti ignorati. I commit sono locali.
- Non aggiungere altri componenti funzionali oltre quelli descritti; piccoli
  helper interni sono ammessi solo se necessari al task e senza nuove dipendenze.

## Review focus e test assegnati

1. FIT duplicati o ID identici con byte diversi: T3 prova deduplica/conflitto.
2. Cambio data, fuso e ora legale: T5 prova split per attività a confine UTC/local.
3. ZIP ostile e scrittura interrotta: T3 prova containment e recupero staging.
4. Gap, pause, HR mancante e modello fuori dominio: T4/T8/T9 provano maschere,
   assenza feedback, copertura e mancata interpolazione.
5. Import dopo l'evento e aggiornamento modello: T9/T10 provano che una sessione
   non diventi prospettica per effetto della sola data di importazione.

## Contratti comuni

In `study_app/backend/schemas.py`: ID UUID; timestamp timezone-aware UTC;
unità nei nomi (`duration_s`, `power_w`, `heart_rate_bpm`). JSON senza NaN/Infinity:
missing come null più maschera. Errori `{code,message,details}` con HTTP 422 per
input, 409 per conflitto/stato incompatibile, 404 per assenza. Ogni lookup atleta
verifica ownership delle risorse; nessun percorso filesystem accettato dalla UI.

Entità: Athlete, ImportBatch, DatasetRevision, Workout, RulesProfile,
Experiment, Preflight, Job, ModelVersion, PrescriptionRevision, Prediction,
Comparison. Tutti gli artefatti hanno `schema_version`, `id`, `created_at`,
`athlete_id`, hash del contenuto e riferimenti alle revisioni di origine.
Le chiavi di relazione sono ID, non nomi o percorsi assoluti. Il preflight
ha hash che comprende dati/config/regole; avvio con hash obsoleto = 409.

API base `/api`; elenco iniziale:

| Metodo/risorsa | Effetto |
|---|---|
| GET/POST `/athletes`; PATCH `/athletes/{id}` | Elenco, creazione, anagrafica |
| POST `/athletes/{id}/imports`; GET `/imports/{id}` | Import esplicito, esiti per file |
| GET `/athletes/{id}/workouts`; GET `/workouts/{id}/series` | Storico, segnali e qualità |
| POST `/athletes/{id}/experiments` | Congela revisione e split; non fitta |
| GET `/experiments/{id}/preflight` | Riepilogo e cause bloccanti |
| POST `/experiments/{id}/start` | Unico ingresso al fitting, con hash e chiave idempotente |
| GET `/jobs/{id}`; GET `/experiments/{id}/results` | Stato e risultati |
| GET `/athletes/{id}/models`; GET `/models/{id}` | Versioni complete |
| POST `/athletes/{id}/prescriptions` | Nuova revisione, anche da import |
| POST `/prescriptions/{id}/predictions` | Simula e salva nuova previsione, nessun fit |
| GET `/predictions/{id}` | Snapshot e serie immutabili |
| POST `/predictions/{id}/comparisons`; GET `/comparisons/{id}` | Associazione e diagnostica |
| GET `/athletes/{id}/evaluation` | Storico per versione |
| GET `/model-comparison?left=...&right=...` | Due versioni, proprietà e avvertenze |

La preview dell'editor è deterministica e locale; una simulazione genera sempre
un nuovo snapshot prima dell'eventuale confronto. Nessun endpoint di refit
automatico, cancellazione storico o modifica in-place di modello/previsione.

## Sequenza e punti di controllo

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11.
Milestone A: archivio e nucleo verificato; B: import e storico; C: workflow
identificazione verificato con stub; D: previsione/confronto; E: consegna.
Ogni milestone produce un risultato utile e ispezionabile. Non saltare alla
successiva per aggirare una decisione scientifica mancante.

### T1 — Archivio reversibile e congelamento

**File:** creare `planning/local-study-webapp/archive_manifest.local.json`,
`planning/local-study-webapp/ARCHIVE_REPORT.md`, `archive/README_ARCHIVE.md`;
modificare `.gitignore`; spostare soltanto l'elenco di SPEC §4. Il manifest
locale con percorsi/dati è ignorato, il report versionabile contiene riepiloghi.
**Input:** snapshot corrente e `results/frozen.json`. **Output:** archivio
verificato, mappa di rilocazione e istruzioni di rollback senza sovrascrittura.

- [ ] Verificare stato Git, file aperti/processi che scrivono nelle directory,
  volumi, junction e sorgenti esterne. Nessun arresto di processi non pertinenti.
- [ ] Creare inventario/hash pre-spostamento e confrontare gli hash congelati.
  Risultato atteso: modelli corrispondenti, ogni file assegnato a move/keep.
- [ ] Preparare ignore equivalenti per nuovi percorsi prima di qualsiasi staging.
- [ ] Verificare percorsi assoluti sorgente/destinazione entro workspace;
  spostare con PowerShell nativo e `-LiteralPath`, senza overwrite.
- [ ] Ricalcolare hash/file/byte; scrivere report e istruzioni di ripristino.
- [ ] Controllare `git status --short`, `git diff --stat`, `git check-ignore`
  su raw, dataset, vecchio storage, modelli locali e nuovo storage.
- [ ] Criterio: tutti i file previsti conservati, nessuna modifica scientifica,
  dipendenze fuori archive dichiarate; commit dei soli percorsi versionabili.

Non eseguire alcun comando storico `prepare`, `fit`, `hr`, `evaluate` per
dimostrare la migrazione. Non dichiarare avviabili i vecchi launcher senza prova.

### T2 — Nucleo numerico e provenienza

**File:** creare `study_app/scientific/{__init__,contracts,adapters}.py`,
`study_app/scientific/frozen/` (copia minima dei sorgenti sotto),
`study_app/scientific/{PROVENANCE.json,frozen_config.json}`,
`study_app/tests/test_scientific_forward.py`, `study_app/requirements.txt`.
Sorgenti: power_response_estimation/{ar,dynamics,model,data}.py;
backend storico models/{p1d,profile_search}.py e population.py;
prescribed_joint/simulation.py. Leggere solo dipendenze immediate per completare
la chiusura d'import. Registrare ogni file realmente estratto nel manifest.

**Interfacce:** `simulate_power(target_w, config, rng) -> PowerEnsemble`;
`simulate_hr(power_w, theta, intercept_bpm, hr0_bpm) -> ndarray`;
`load_frozen_config() -> FrozenConfig`. Shape ensemble `(paths,time)`.
Fitting esposto tramite `fit_models(request: FitRequest) -> FitResult`, invocabile
solo dal worker T6; importare il modulo non esegue lavoro.

- [ ] Risolvere D2, estrarre configurazione effettiva e provenienza senza fit.
- [ ] Scrivere test forward con parametri prefissati: risposta costante,
  gradino, ritardo frazionario, clipping solo uscita, nessun reset ai lap.
- [ ] Eseguire test prima dell'adattatore: fallimento per API assente, nessun fit.
- [ ] Copiare nucleo, adattare esclusivamente import e argomenti filesystem.
- [ ] Confrontare output con le stesse funzioni storiche e stessi input sintetici:
  `rtol=1e-10`, `atol=1e-10` per forward deterministico in stesso ambiente.
  Differenza oltre tolleranza richiede analisi, non aumento arbitrario soglia.
- [ ] Eseguire `python -B -m pytest study_app/tests/test_scientific_forward.py -q`;
  tutti pass, nessuna chiamata optimizer o scrittura in archive; commit circoscritto.

### T3 — App locale, storage, atleti e import

**File:** creare backend `{app,schemas,repository,storage,imports}.py`,
`study_app/backend/migrations/001_initial.sql`, frontend `package.json`, lock,
`vite.config.ts`, `tsconfig.json`, `index.html`, `src/{main.ts,App.vue,api.ts,style.css}`,
`src/pages/AthletesPage.vue`, `study_app/start.ps1`,
`study_app/tests/{test_storage,test_imports}.py`, frontend `src/pages/AthletesPage.test.ts`.
**Interfacce:** `create_athlete(input: AthleteInput) -> Athlete`;
`import_files(athlete_id, uploads) -> ImportBatch`; `commit_artifact(staging, metadata)`
con riconciliazione crash. L'import non chiama `fit_models`.

- [ ] Test: due atleti omonimi isolati; PATCH non riscrive snapshot esistenti;
  upload duplicato stesso hash non duplica attività; stesso ID/byte diversi = conflitto.
- [ ] Test ZIP: `../`, assoluti, link, annidati, cifrati, limiti e file corrotti;
  niente estrazione fuori staging. Simulare crash prima/dopo pubblicazione:
  nessun artefatto incompleto esposto come definitivo.
- [ ] Verificare fallimenti per servizio assente, implementare API/storage/import
  e schermata con esiti per file. Nessuna selezione scientifica in questo task.
- [ ] Avvio solo loopback, API stessa origine, rifiuto origini/Host estranei;
  nessun endpoint accetta comandi o percorsi arbitrari. Un solo writer/worker.
- [ ] Eseguire test T3, `npm.cmd test`, `npm.cmd run build` dal frontend;
  provare launcher e persistenza di un atleta sintetico dopo riavvio.
- [ ] Criterio: prima apertura senza atleti né modelli; import utilizzabile,
  nessun fitting chiamato (spy con conteggio zero); commit.

### T4 — Preparazione, eleggibilità e storico navigabile

**File:** backend `{preprocessing,eligibility,workouts}.py`, scientific
`frozen/` per fit_reader/prescriptions/prescription_segments/prescription_gaps
con provenienza; frontend `src/pages/AthleteHistoryPage.vue`,
`src/components/{WorkoutChart,QualitySummary}.vue`;
test `test_eligibility.py`, `src/components/WorkoutChart.test.ts`.
**Interfacce:** `prepare_workout(raw_id, rules_id) -> PreparedWorkout`;
`assess_eligibility(workout, rules) -> EligibilityReport` con motivi e conteggi;
`get_workout_series(workout_id) -> SeriesBundle` preserva tempi e missing.

- [ ] Risolvere D1: persistere profilo scientifico approvato prima di usarlo.
- [ ] Test: senza FTP/regole import disponibile, nessuna eleggibilità inventata;
  senza lap impossibile ricostruire automaticamente target; massimali categorici
  non numerici; zeri inclusi nelle medie; stessi algoritmi di rounding e ripetute.
- [ ] Test tratti: 300 campioni non bastano, 301 a 1 s sì; missing HR interrompe
  train ma non le traiettorie validation; pausa/gap rompe, cambio lap no.
- [ ] Implementare elaborazione versionata senza alterare raw e grafici a
  campioni originali; eventuale riduzione grafica non entra nelle metriche.
- [ ] Eseguire test T4 e UI; verificare zoom, pan, slider e interruzioni su gap.
- [ ] Criterio: tag spiegabili e riproducibili, segnali/unità corretti; commit.

### T5 — Split cronologico e preflight

**File:** backend `{experiments,preflight}.py`, frontend
`src/pages/ExperimentSetupPage.vue`, test `test_preflight.py` e
`src/pages/ExperimentSetupPage.test.ts`.
**Interfacce:** `create_experiment(athlete_id, dataset_revision_id, cutoff, timezone)`;
`preflight(experiment_id) -> Preflight` include `can_start`, `blocking_reasons`, hash.

- [ ] Risolvere D4; test con timestamp esattamente al taglio, ora legale,
  attività che attraversa mezzanotte, stesso timestamp/differenti ID.
- [ ] Test nessuna attività in due insiemi, dataset revisionato non cambia
  esperimento, train/validation vuoti bloccano, preflight non chiama fitting.
- [ ] Implementare snapshot, riepilogo scientifico e conteggi specifici P/HR.
- [ ] Eseguire test T5 e build UI; conteggi coerenti con maschere e manifest.
- [ ] Criterio: l'utente vede esattamente cosa sarebbe usato prima del fit; commit.

### T6 — Orchestrazione identificazione, senza eseguirla

**File:** backend `{jobs,worker,identification}.py`, frontend
`src/components/JobProgress.vue`; test `test_jobs.py`, `test_fit_boundary.py`.
**Interfacce:** `start_experiment(id, preflight_hash, idempotency_key) -> Job`;
`run_identification(request, fitter=fit_models) -> ExperimentResult`.
Solo endpoint start invoca la coda. Il worker riceve snapshot, non dati mutabili.

- [ ] Test usando esclusivamente stub del fitter: doppio click = un job;
  hash cambiato = 409; errore fit non pubblica versione; successo pubblica
  atomico; arresto = interrupted; riavvio non richiama fitter.
- [ ] Test con guardia che fa fallire immediatamente qualsiasi optimizer reale.
- [ ] Implementare orchestrazione delle chiamate congelate e salvataggio di
  fit, screening, popolazione, baseline, metriche e fallimenti; nessun fallback.
- [ ] Verificare staticamente passaggio dei soli ID train al fitter, dei soli
  input consentiti al simulatore e della configurazione congelata. Validation
  non seleziona ordine o HR mode. Stub controlla gli argomenti effettivi.
- [ ] Eseguire soltanto test stub T6. Non premere Avvia su dataset reale.
- [ ] Criterio: workflow provato, collegamento reale ispezionato ma non eseguito;
  dichiarare il limite nel report, commit.

### T7 — Risultati e registro modelli

**File:** backend `{results,model_registry}.py`, frontend
`src/pages/{ExperimentResultsPage,ModelsPage}.vue`,
`src/components/ParameterSummary.vue`, test `test_results.py`,
`src/pages/ExperimentResultsPage.test.ts`.
**Interfacce:** `summarize_result(result) -> ResultsSummary`;
`list_models(athlete_id) -> list[ModelSummary]`. Nessuna riscrittura degli artefatti.

- [ ] Test metriche su serie note, bias osservato-predetto, SD con N<2,
  missing/null, aggregazione per workout, copertura/larghezza e supporti diversi.
- [ ] Test versione incompleta non selezionabile, proprietà atleta obbligatoria,
  range/durate riferiti ai soli dati train; mostrare fit falliti/esclusi.
- [ ] Implementare pagine HR, residui, parametri e potenza ausiliaria nei grafici.
  Riepilogo globale distinto dalle metriche della finestra di zoom.
- [ ] Verificare UI con risultati sintetici, navigazione workout, zoom e assi;
  test T7 e build pass; commit.

### T8 — Prescrizioni e snapshot predittivi

**File:** backend `{prescriptions,predictions}.py`, frontend
`src/pages/WorkoutPlannerPage.vue`, `src/components/BlockEditor.vue`,
`study_app/examples/{prescription.csv,prescription.json,prescription-range.json}`,
test `test_prescriptions.py`, `test_predictions.py`,
`src/pages/WorkoutPlannerPage.test.ts`.
**Interfacce:** `parse_prescription(content, format) -> PrescriptionDraft`;
`resolve_targets(draft, choices) -> list[ResolvedScenario]`;
`predict(prescription_revision_id, model_version_id, mc_config) -> Prediction`.

- [ ] Test roundtrip JSON/CSV, ripetizioni/riordino, durata totale,
  range non risolto bloccante, valori invalidi, scenari completi senza combinazioni
  nascoste; profilo lineare diverso dalla gestione missing dei sensori.
- [ ] Test forward con modello sintetico fissato: stessi seed = stessi output,
  stato continuo tra blocchi, bande indipendenti nella UI, media dopo clipping,
  insufficienza draw ammissibili = errore, nessuna HR osservata in input.
- [ ] Implementare editor con esempi scaricabili, anteprima e controllo dominio;
  snapshot con prescrizione originale/risolta, parametri, MC, hash e timestamp.
- [ ] Test snapshot immodificabile dopo editing della prescrizione o creazione
  di altro modello. Niente import automatico dei modelli storici nel runtime.
- [ ] Eseguire test T8, UI e build; commit.

### T9 — Associazione e tre confronti distinti

**File:** backend `{alignment,comparisons,adherence}.py`, frontend
`src/pages/PostWorkoutPage.vue`, test `test_comparisons.py`,
`src/pages/PostWorkoutPage.test.ts`.
**Interfacce:** `align(prediction, workout, policy) -> ComparisonSupport`;
`compare(prediction_id, workout_id) -> Comparison`;
`adherence(support) -> AdherenceSummary`. Origine/politica nel manifest.

- [ ] Risolvere D3. Test nessun shift per migliorare HR, nessuna interpolazione,
  HR iniziale storica in diagnostica, pausa reinizializzata etichettata e
  previsione originale identica byte per byte dopo il confronto.
- [ ] Test workout più lungo/corto, blocchi saltati, potenza mancante, HR
  mancante, nessuna sovrapposizione, registrazione senza timer start.
- [ ] Test modello o attività di altro atleta rifiutati, sessione già vista
  non prospettica, previsione creata dopo inizio non prospettica.
- [ ] Implementare tre pannelli con metriche separate, aderenza senza soglia
  arbitraria, copertura e segmenti non confrontabili visibili.
- [ ] Eseguire test T9 e browser con pause/gap sintetici; commit.

### T10 — Storico prospettico e confronto tra due atleti

**File:** backend `{evaluation,athlete_comparison}.py`, frontend
`src/pages/{EvaluationPage,AthleteComparisonPage}.vue`, test `test_evaluation.py`,
`src/pages/AthleteComparisonPage.test.ts`.
**Interfacce:** `evaluation_history(athlete_id, model_version_id) -> EvaluationHistory`;
`compare_models(left_id, right_id) -> ModelComparison`.

- [ ] Test sessione prospettica di V1 che diventa train di V2: V1 immutata;
  import tardivo non conferisce prospettività; hash duplicato mantiene provenienza.
- [ ] Test due protocolli diversi segnalati, unità coerenti, Omega non presentata
  come CI della media, nessun ranking, nessun auto-refit al nuovo import.
- [ ] Implementare timeline, selettori versioni e guida ai parametri della SPEC.
- [ ] Eseguire test T10 e UI, controllare tutti i ruoli per versione; commit.

### T11 — Verifica integrata e consegna all'utente

**File:** `study_app/README.md`, `planning/local-study-webapp/VERIFICATION.md`,
`study_app/tests/test_workflow_stubbed.py`; aggiornare CONTROL e README radice
con ingresso alla nuova app e link all'archivio. Nessuna modifica ai dati reali.

- [ ] Scrivere workflow sintetico isolato: due atleti → import → preflight →
  job stub → modello sintetico → prescrizione → previsione → confronto →
  nuova versione sintetica; ownership e snapshot invarianti fino al riavvio.
- [ ] Eseguire suite nuova autorizzata con guardia anti-fit e storage temporaneo;
  frontend test/build. Nessuna discovery della suite legacy.
- [ ] Verificare nel browser tutte le sei sezioni, messaggi di errore, zoom,
  bande separate e stato vuoto. Non usare raw storici come dati di prova.
- [ ] Ricontrollare hash modelli archiviati, Git diff e assenza dati privati nello
  staging; registrare comandi, esiti e limite dei test stub.
- [ ] Documentare setup/avvio, layout, backup a servizio fermo, formati supportati,
  protocollo e limiti. Non aggiungere funzione backup cloud o packaging.
- [ ] Consegnare app con storage operativo vuoto e nessun job automatico pendente.
  L'utente importa il dataset nuovo e avvia il primo fitting. Registrare questa
  verifica come NON ESEGUITA dall'agente, non come test passato.

## Criterio complessivo di completamento

T1–T11 verificati entro il perimetro autorizzato, decisioni D1–D4 registrate,
sei sezioni disponibili e persistenza corretta, nessuna ristima dell'agente.
La consegna tecnica non implica che i parametri siano identificabili sul nuovo
atleta: tale risultato dipende dal primo esperimento avviato dall'utente.
Se tale esperimento fallisce, mostrare il risultato senza introdurre un nuovo
modello o ampliare le soglie per farlo riuscire.

## Copertura della richiesta

| Richiesta | Task |
|---|---|
| Branch e archivio completo dello studio | Branch già creata, T1 |
| Ultimi modelli congelati, nessuna ristima dell'agente | T1, T2, guardie T6/T11 |
| Atleta, modifica dati, nuovi import | T3 |
| Eleggibilità AR, P reale/ricostruita/HR, navigazione | T4 |
| Split per data, assunzioni e conteggi prima del fit | T5 |
| Identificazione esplicita e popolazione HR | T6 |
| Risultati validation e modelli versionati | T7 |
| Editor, import prescrizione, range e bande separate | T8 |
| Snapshot prima dell'esecuzione e tre confronti | T8, T9 |
| Aderenza, gap, origine temporale e qualità | T4, T9 |
| Valutazione nel tempo, confronto due atleti | T10 |
| Avvio locale e primo fit riservato all'utente | T3, T11 |

## Esito di esecuzione

Implementazione registrata in CONTROL.md; comandi ed esiti in VERIFICATION.md.
Le caselle originali restano una checklist progettuale e non attestano prove
non eseguite. Verifica visuale browser indisponibile; fitting reale riservato
all'utente. I moduli consolidati mantengono il perimetro scientifico approvato.
