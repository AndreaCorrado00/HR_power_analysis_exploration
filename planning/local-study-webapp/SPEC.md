# Webapp locale dello studio — specifica proposta

Data: 18 ottobre 2026. Branch: `feature/local-study-webapp`.
Stato: implementazione autorizzata il 18 ottobre 2026; D1-D4 approvate in CONTROL.md.
Documento operativo collegato: [PLAN.md](PLAN.md). Registro di perimetro: [CONTROL.md](CONTROL.md).

## 1. Obiettivo e vincoli 

Una sola webapp locale Vue per gestire atleti, dati, identificazioni, versioni,
prescrizioni, previsioni salvate e confronti successivi. Il successo è completare
il percorso con un dataset nuovo, mantenendo verificabile cosa fosse noto prima
dell'esecuzione reale. Nessun servizio cloud e nessuna interpretazione medica.

- NON eseguire fitting o ristime durante lo sviluppo, neppure tramite test o script.
- Il primo fitting sul nuovo dataset sarà avviato dall'utente nella nuova app.
- Il software deve implementare il fitting, ma importazione, avvio, navigazione,
  migrazione e verifica automatica non devono attivarlo.
- Nessun caricamento automatico del vecchio atleta nella nuova app.
- Conservare dati e modelli storici senza modificarli; riusare il nucleo numerico.
- Nessun modello nuovo, nuova covariata, ricerca automatica di architetture,
  allentamento delle soglie o aggiornamento automatico dopo un workout.
- Preservare tutti i campioni originali. Niente interpolazione, filtraggio,
  concatenazione dei gap o correzione dei sensori impliciti.
- Il ruolo di un'attività appartiene a una versione/esperimento, non all'attività
  globalmente. Aggiornare un modello non riscrive le valutazioni precedenti.
- Confrontare atleti descrittivamente; nessun modello di popolazione tra atleti.

## 2. Fonti locali e significato di congelamento

Snapshot iniziale: commit `0e0b365`. Riferimento più recente:
`experiments/prescribed_joint/{PROTOCOL.md,RESULTS.md,results/frozen.json}`.
Non usare il precedente ordine 4 come riferimento corrente.

Artefatti da conservare integralmente:

| Artefatto | SHA256 dichiarato in frozen.json |
|---|---|
| `results/power/model.json` | `13a0b2096eabe2816d943f4886ffa7ff6e4928de06471397aef56f20eaca39c2` |
| `results/hr_model.json` | `d4c694952215e7b5c87d14f7b7833a438646a70a7a5374a09a1f7c4f95cfc2db` |

Questi hash sono letti dal registro storico: verificarli sui file prima
dell'archiviazione. Un disaccordo interrompe il congelamento, senza rigenerazioni.
Congelamento significa preservare artefatti storici, equazioni, configurazioni,
screening, inizializzazione e convenzioni numeriche. I coefficienti di un nuovo
atleta saranno stimati soltanto su comando esplicito dell'utente.

### Potenza ausiliaria

`P(t) = max(0, target(t) + G_2(q^-1) delta(target(t)) + e(t))`;
`e(t) = c + phi1 e(t-1) + phi2 e(t-2) + epsilon(t)`.

Dinamica di ordine 2 e AR(2) a varianza costante, tempo in secondi, potenza in W.
Clipping solo all'uscita: non alterare lo stato AR latente. Proposta: fissare
l'ordine 2 risultante dall'ultimo esperimento, senza ripetere la selezione 2/3/4
sulla validation. Questo punto è esplicito nella decisione D2 di CONTROL.md.
LS in simulazione libera, peso uguale per workout, 6 start, 250 valutazioni;
AR OLS sul residuo train, peso per campione. Stato dinamico nullo e AR
stazionario ai confini dichiarati, mai ai semplici cambi di blocco.

### HR

`tau dx/dt + x = K(P(t-L)-P0)`; `HR = B+x`.
P1D completo con ritardo, fit indipendente per tratto train; K in bpm/W,
L e tau in s, B in bpm. HR iniziale osservata usata solo nel fitting train.
Configurazione da estrarre dall'artefatto effettivo, non dai default dell'interfaccia:
bounds K `[1e-6,5]`, L `[0,30]`, tau `[.01,1800]`, B `[60,200]`;
profile_multistart 301x141, 8 raffinamenti + 8 start, 500 valutazioni,
seed 42, LS TRF. Screening RSE 100%, correlazione .98, esclusione bound/ambiguità;
popolazione REML multivariata con covarianze locali dei fit. Conservare tutti i
fit e motivi di esclusione. Se la popolazione non è stimabile, mostrare fallimento
senza fallback a parametri storici, di un altro atleta o a soglie meno severe.

Predizione a priori: `population_B_P0_mean_HR0`;
`A=media_train(B-K_pop P0)`, `B=A+K P0`, HR0 media delle HR iniziali train.
Nessun campione HR della validation/test entra nella predizione.
Baseline statica OLS HR=beta0+beta1 P sugli stessi campioni HR train, soltanto
nel job richiesto dall'utente. Resta un confronto scientifico, non un modello
selezionabile per sostituire silenziosamente il modello congelato.

Sono adattamenti già presenti nel progetto, non nuove repliche bibliografiche.
La dipendenza tra tratti dello stesso workout è un limite della REML attuale.
Non associare i parametri a fatica, forma fisica o biomarcatori.

### Monte Carlo

Default congelato: 1000 traiettorie, seed 42, stream distinti per componente,
parametri HR congiunti dalla normale multivariata REML entro bounds,
massimo 20*N candidati; errore esplicito se insufficienti. Parametri HR costanti
nel tratto. Rumore potenza e parametri HR indipendenti. Centro = media delle
simulazioni, anche per la potenza dopo clipping. Fasce puntuali 2.5–97.5%.
Non includono rumore residuo HR né incertezza delle medie, A, HR0 o coefficienti
potenza. Mostrare questa descrizione e copertura/larghezza senza chiamarle
intervalli predittivi completi. N e seed salvati; nessun campionamento dei range
prescritti in assenza di scelta esplicita dell'utente.

## 3. Architettura proposta e alternative

Scelta proposta: frontend Vue 3 + TypeScript + ECharts; backend Python FastAPI,
servito da Uvicorn su loopback. Riutilizzare dipendenze e versioni del repository
ove compatibili, registrare lock/versioni effettive senza aggiornamenti gratuiti.
SQLite per indice, relazioni e job; file per raw, serie e artefatti. Un processo
worker locale esegue un job alla volta; la UI resta utilizzabile. Nessun Redis,
servizio esterno, account o server LAN. Un launcher PowerShell avvia l'app e apre
il browser; setup dipendenze separato dall'avvio, nessun fitting nel setup.

Alternative considerate: estendere direttamente la vecchia webapp riduce il
lavoro iniziale ma mantiene il flusso per singolo clone e assunzioni obsolete;
un contenitore desktop introduce packaging e aggiornamenti non richiesti.
La nuova app con nucleo Python riusato mantiene separati studio storico e nuovo uso.

Struttura nuova, da creare solo dopo approvazione:

```text
archive/                        # snapshot del vecchio studio, struttura conservata
planning/local-study-webapp/     # specifica, piano e controllo di perimetro
study_app/
  backend/                      # API, archivio locale, job e servizi applicativi
  frontend/                     # Vue, pagine e grafici
  scientific/                   # adattatori + sorgenti congelate con provenienza
  tests/                        # fixture sintetiche, test numerici senza fit e UI
  examples/                     # prescrizioni sintetiche importabili
  requirements.txt
  start.ps1
storage/                        # escluso da Git, vuoto alla prima esecuzione
  study.sqlite3
  athletes/<uuid>/
    athlete.json
    raw/<sha256>/               # originali immutabili
    interim/<import_id>/
    processed/<dataset_revision>/
    experiments/<experiment_id>/
    models/<model_version_id>/
    prescriptions/<revision_id>/
    predictions/<prediction_id>/
    comparisons/<comparison_id>/
```

I file raw non cambiano. Le revisioni processate e gli artefatti completati sono
immutabili; l'anagrafica è modificabile con registro delle revisioni. SQLite è
l'indice, i manifest conservano provenienza e relazioni per la riproducibilità.
Scritture in staging, pubblicazione atomica, gestione esplicita degli orfani
file/DB dopo crash; nessuna versione parziale visibile come completata.
UUID indipendenti da nome/cognome; percorsi risolti sotto lo storage dell'atleta.

## 4. Archivio e riuso senza alterazione dello studio

Archiviare sotto `archive/` data, dataset, experiments, power_response_estimation,
references, reports, scripts, src, tests, webapp, history.md, README.md,
requirements*.txt, pytest.ini e start-athlete.ps1. Includere contenuti ignorati
scientificamente necessari, modelli e storage delle vecchie app.
Conservare fuori `.git`, `.worktrees`, `.venv`, AGENTS.md, `.gitignore`, planning
e cache operative. Nessuna cancellazione di cache o dipendenze in questo passaggio.
File nuovi o inattesi: inventariarli e chiedere estensione prima di spostarli.

Manifest con percorsi originali/finali, dimensione, SHA256, stato tracked/ignored,
versione Git e link esterni. Non seguire junction/symlink fuori dal perimetro.
Il builder storico usa FIT dentro `.worktrees`: inventariare e verificare questi
riferimenti senza spostare il checkout. Documentare nell'archivio le dipendenze
esterne rimaste; non dichiarare lo snapshot autosufficiente se non lo è.
Non modificare percorsi dentro i vecchi artefatti per farli apparire nuovi.
Per la riproduzione usare la radice archive e documentare i comandi compatibili;
eventuali percorsi assoluti originari restano nel manifest con mappa di rilocazione.

Controllare hash prima/dopo, numero file, byte, assenza di perdite e ignorati Git.
Adattare `.gitignore` preservando l'esclusione dei dati privati e dei pesanti
artefatti locali dopo lo spostamento. Niente `git add -A` indiscriminato.
Gli spostamenti valgono anche per file ignorati: cambiare branch non li ripristina.
Preparare un rollback basato sul manifest che rifiuti collisioni e sovrascritture.

Il nucleo riusato sarà una copia tracciata minima in `study_app/scientific/`, con
mappa sorgente/destinazione/hash/licenza. Cambiare solo import e dipendenze da
percorsi/configurazione, con diff documentato; nessuna riscrittura delle equazioni.
Nessuna dipendenza runtime dalle vecchie app o dal loro storage. Se l'estrazione
richiede un refactoring scientifico materiale, arrestarsi e concordarlo.

## 5. Flussi e schermate

Navigazione: Atleti; dentro atleta, Storico, Esperimenti, Modelli, Allenamenti,
Verifiche. Confronta atleti accessibile dalla lista. Etichette e messaggi in italiano.
Grafici con tempo hh:mm:ss, unità W/bpm, zoom, pan, slider e reset; assi separati
per HR e P. Selezione workout e tratti senza perdere il contesto della sessione.
Linee interrotte sui gap. Metriche dell'intera sessione sempre disponibili;
metriche della finestra visibile chiaramente etichettate e mai sostitutive.

### 5.1 Atleti, import e storico

Pulsante «Aggiungi atleta»: nome, cognome, età in anni, FTP opzionale in W;
età associata alla data di inserimento, non aggiornata inventando una nascita.
Prima versione: FIT singolo, selezione multipla e ZIP di FIT anche in sottocartelle.
Altri formati restituiscono elenco dei supportati; niente TCX/GPX impliciti.
ZIP con percorsi assoluti, traversal, symlink, archivi annidati o cifrati rifiutati.
Limiti proposti: 2 GiB upload, 10 GiB espansi, 20000 file; errori espliciti e
nessuna importazione parziale spacciata per completa. Ogni file ha un esito.

Deduplica per hash all'interno dell'atleta; stesso ID FIT con contenuto diverso
diventa conflitto da risolvere, non sovrascrittura. Nuovo import produce revisione
del dataset, non altera esperimenti. Originale e provenienza sempre recuperabili.
Anagrafica modificabile; modificare FTP non ricalcola retroattivamente selezioni.

Storico: data, durata, qualità, lap, tag eleggibile potenza/eleggibile HR,
parzialmente utilizzabile, escluso, regole da configurare. Ogni tag espone
motivi, campioni utilizzabili e versione delle regole, non solo colore.
Grafico: potenza reale, target ricostruito dal metodo storico e HR. Chiamare
il target «prescrizione ricostruita», mai «prescrizione originale».

Eleggibilità storica: `prescription_rules_v3.json`, `prescriptions.py`,
`prescription_segments.py`, `power_response_estimation/data.py`,
`experiments/prescribed_joint/data.py`. Tutti i lap assegnati secondo regole,
medie comprendenti zeri, arrotondamento target a 5 W; ripetute compatibili
con target comune e tolleranza 5%; massimali categorici senza watt inventati.
Non copiare la lista manuale dei 60 workout come selettore dei nuovi atleti.
D1 approvata: soglie di zona parametrizzate con FTP atleta / 325; durate, rounding 5 W e tolleranze restano congelati. FTP necessaria alla ricostruzione, opzionale per anagrafica/import.
In assenza della FTP dell'atleta, import e ispezione funzionano,
il fitting resta bloccato con spiegazione; non inventare target.

Potenza: tratti con campioni validi a 1 s, target numerico, lap valido, timer non
in pausa; gap e invalidità interrompono. Nessun reset ai cambi target/lap.
HR train: ulteriori interruzioni per HR mancante, almeno 301 campioni a 1 s
(300 s). HR validation non condiziona i tratti predetti: serve solo alle metriche.
Mostrare campionamento, gap, pause, missing, zeri, salti HR e copertura; anomalie
solo segnalate. Nessuna sincronizzazione automatica HR/P per migliorare il fit.

### 5.2 Identificazione e validation

L'utente sceglie atleta, revisione dataset e data di taglio. Convenzione proposta:
inizio attività precedente alle 00:00 della data scelta = train; dalla data
compresa = validation. Fuso selezionato e salvato, default Europe/Rome;
timestamp persistiti in UTC. Attività intere, nessuno split di campioni.
Non creare una partizione test interna al dataset di identificazione.

Prima di «Avvia identificazione», mostrare equazioni/configurazione congelata,
inizializzazione, periodo, attività/tratti/campioni utilizzabili per ciascun modello,
esclusioni e fonti di variabilità. Il preflight è read-only e non chiama fit.
Train o validation senza supporto utile, regole mancanti, artefatti incompatibili
bloccano il job. Mai proseguire automaticamente con una sola componente.

Unico comando esplicito crea job, congela manifest e avvia stima potenza, fit HR,
screening, REML, baseline e valutazione validation. Idempotenza contro doppio click.
Stati queued/running/succeeded/failed/interrupted; log e progressi persistenti.
All'arresto non riprendere né rifittare automaticamente. Riprova esplicita crea
un nuovo tentativo; conserva i fallimenti. Nessuna promessa di ripresa parziale
dei fit in questa prima versione.

Risultati centrati su HR: MAE, RMSE, bias osservato-predetto, SD residui,
copertura e larghezza fasce; intero tratto e primi 180 s/coda, senza calibrazione.
Aggregati per workout con peso uguale e supporto comune dichiarato; conteggi dei
fallimenti inclusi. Grafici HR misurata/predetta, residui, parametri e potenza.
Potenza ausiliaria nei grafici, configurazione/provenienza nei dettagli tecnici;
nessuna pagina principale di ottimizzazione del modello potenza.
La catena su target ricostruiti della validation è retrospettiva, non prospettica.

### 5.3 Versioni del modello

Una versione completa riferisce un esperimento riuscito e include HR, potenza,
popolazione, fit individuali, screening, baseline, hash, versioni software,
configurazione, periodo e attività. Riepilogo range min/max e quantili della
potenza train, durate dei tratti e workout, numero di campioni. Fuori dominio
nelle previsioni segnalato, senza clipping aggiuntivi o nuovi modelli.
Nessuna versione incompleta selezionabile per previsione; nessun default
silenzioso a coefficienti di un altro atleta. Nuova identificazione sempre esplicita.

### 5.4 Editor e previsione prima dell'allenamento

Editor con aggiunta, duplicazione, rimozione e riordino blocchi; ripetizioni
di gruppi, riepilogo durata e grafico. Durata intera positiva in secondi,
potenza finita non negativa in W. Target in watt; conversione da %FTP e import
ZWO/FIT workout fuori dalla prima versione. Import JSON v1 e CSV espliciti.
Validazione con riga/campo, nessuna correzione tacita dei valori.

CSV semplice: `duration_s,target_w`, una riga per blocco (ripetizioni già espanse).
JSON: `schema_version:1`, `name`, `blocks`; nodo blocco
`{duration_s:300,target:{kind:"constant",watts:150}}`; nodo ripetizione
`{repeat:4,blocks:[...]}`. Profondità massima 2, durata totale massima 24 ore.
Un esempio completo per formato sarà scaricabile dall'editor.

Target range `{kind:"range",low_w:180,high_w:220}`: impedire la simulazione
finché l'utente non sceglie centro, profilo esplicito a punti o scenari nominati.
Profilo: punti `(time_s,watts)` comprendenti 0 e durata, interpolazione lineare
dichiarata del target (non dei dati misurati). Scenari: valori deterministici
entro il range, salvati separatamente; niente distribuzione uniforme implicita.
Più range richiedono scenari completi nominati, non un prodotto cartesiano nascosto.

Mostrare prescrizione, media P simulata, media HR, bande P e HR con interruttori
indipendenti. Lo spegnimento di una banda non cambia modello né simulazioni.
Niente HR osservata per inizializzare la previsione primaria. Un campo HR alla
partenza potrà essere registrato nel confronto, senza correggere la previsione.
Non implementare la calibrazione successiva in questa prima versione.

Salvare prima dell'esecuzione uno snapshot immutabile: prescrizione originale e
risolta, scenari, modello, MC, seed/stream, versione software, origine temporale,
regole pause/gap, HR0/A, data UTC, hash e serie risultanti. Modificare una
prescrizione crea revisione e nuova previsione, non riscrive quella salvata.

### 5.5 Confronto dopo l'allenamento

Associazione esplicita previsione-attività dello stesso atleta. Conservare l'ID
raw, timestamp, revisione dati, origine allineamento e regole usate. Default
proposto: primo timer start documentato, altrimenti primo campione, senza
ottimizzazione del lag. Un'origine manuale richiede motivazione ed è una nuova
revisione diagnostica, non la valutazione primaria. Ritardo HR rimane nel modello.

Tre pannelli separati: esecuzione (target/P prevista/P reale); previsione a priori
(HR salvata/HR reale); diagnostica (HR simulata da P reale/HR reale).
La diagnostica non aggiorna né sostituisce la previsione salvata.
Asse principale tempo trascorso, non compressed moving time. Sessione intera
sempre visibile, inclusi extra, mancanti, interruzioni e parti non confrontabili.
Metriche solo su coppie valide con denominatore e copertura espliciti; niente
giudizio di riuscita basato sulla sola porzione favorevole.

Regola pause/gap approvata (D3): la previsione salvata prosegue sul suo tempo
originario senza deformazioni. Nella diagnostica P reale i gap/stop interrompono
il tratto; nessuna potenza imputata. Ripartenza del tratto con convenzioni
congelate A/HR0 da train, marcata come reinizializzazione diagnostica. Nessun
reset ai cambi blocco. La possibile discontinuità è visibile e documentata.

Aderenza: MAE e bias P reale-target, lavoro prescritto/osservato sul supporto
comune, durata registrata/prescritta, copertura temporale e scostamento per blocco.
Non assegnare un tag aderente/non aderente con una soglia inventata. Nessuna
analisi primaria limitata ai blocchi aderenti. Dati meteo/contesto disponibili
registrati come metadati, mai nuovi ingressi automatici del modello.

### 5.6 Valutazione nel tempo e confronto atleti

Ogni attività rispetto a ogni modello può essere training, validation,
non vista retrospettiva o verifica prospettica. Una sessione è prospettica solo
se previsione e modello precedono il suo inizio e i suoi dati non hanno contribuito
a fitting/selezione/calibrazione di quella versione. Data import da sola non basta.
Duplicati rilevati anche per hash; conservare revisione di provenienza.
Il fatto che lo sviluppatore abbia esaminato i vecchi dati impedisce di
promuoverli a test vergine della ricerca attraverso una semplice reimportazione.

Timeline per versione: errori, aderenza, copertura/larghezza, qualità e quantità
di dati; nessun aggiornamento automatico. Nuove sessioni possono divenire train
di una nuova versione conservando la verifica prospettica della precedente.
Confronto di esattamente due atleti/versioni: K, L, tau, A/HR0, unità, media,
dispersione e incertezza disponibile, periodi, supporto e configurazioni.
Guida: K sensibilità matematica HR/P, L ritardo, tau tempo caratteristico;
Omega variabilità tra tratti, non incertezza della media. Segnalare
incomparabilità dei protocolli; nessun ranking di forma o significatività inventata.

## 6. Verifica e limite della consegna

Verifiche autorizzabili nello sviluppo: test unitari di parsing/isolamento,
integrazione con job di fitting sostituito da stub, fixture sintetiche e
simulazione forward con parametri prefissati; equivalenza numerica con nucleo
storico in sola lettura. Nessun test che chiami un ottimizzatore o ristimi parametri. I fit storici possono essere letti localmente come riferimenti, senza copiarne i risultati nella suite.
Non lanciare la vecchia suite indiscriminatamente: contiene test di fitting.
Il primo fitting reale resta test di accettazione eseguito dall'utente, dichiarato
non eseguito alla consegna tecnica. Non affermare validazione end-to-end reale
prima di quel passaggio.

Controlli UI su dati sintetici: creazione/edit atleta, import, zoom/pan, scelta
workout, preflight, job simulato, scenari, toggle bande, salvataggio, confronto e
persistenza dopo riavvio. Nessun seed automatico di dati reali in storage.
Requisiti mancanti o variazioni scientifiche richiedono modifica approvata di
questa specifica prima del codice. CONTROL.md è il registro di tali decisioni.
