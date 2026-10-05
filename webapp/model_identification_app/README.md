# Identificazione HR–Power

SPA Vue locale per importare segmenti, creare split riproducibili e identificare
un modello P1D full o short-transient indipendente su ogni segmento **train**.
La pagina **Parametri atleta** stima parametri condivisi dal train e valuta le
predizioni sul test, con inizializzazione o calibrazione esplicita. La validation
resta riservata. Non si attribuisce significato fisiologico ai parametri.
Per il percorso operativo completo e le run della milestone vedere il
[README principale](../../README.md) e il [protocollo di previsione](POPULATION_PROTOCOL.md).

## Default P1D congelati (5 ottobre 2026)

Preset delle nuove run dalla run `a6c56bc0c679469886964802dfda81b0`
(`2026-10-05T04:57:50.984075+00:00`): P1D full, segnali raw,
`estimated_equilibrium`, senza pre-window, protocollo `segment_v2`.
Bounds: K [1e-6, 5] bpm/W, L [0, min(30, T)] s, tau [0.01, 1800] s.
I due limiti di B restano vuoti e devono essere dichiarati per ciascun atleta;
non si trasferiscono i bpm della run di riferimento.
Ricerca `profile_multistart`: griglia 301 x 141, 8 raffinamenti, 8 start,
seed fitting 42, massimo 500 valutazioni per start; TRF, loss lineare,
Jacobiano a 3 punti, ftol/xtol/gtol 1e-8 e x_scale=jac.
Split iniziale 70/10/20, seed 60; raggruppamento per attività quando disponibile.

Questi sono default operativi modificabili, non una validazione universale del
framework. B è un parametro matematico, senza interpretazione fisiologica.
Il manifest sorgente riporta `completed_with_errors`. Le configurazioni salvate
e i fallback storici di validazione/replay restano invariati; il preset per nuove
run è esposto da `default_config(new_run=True)` e dall'API `/api/models`.
La struttura short-transient conserva i propri default.

## Avvio e riavvio (Windows)

Dalla radice della repository, prima installazione o dopo modifiche al codice:

```powershell
.\webapp\model_identification_app\start.ps1 -Setup
```

Richiede Python 3.14 (versione usata nelle verifiche), Node.js >=22.12 con npm
e accesso ai registry per l'installazione. Il comando installa le dipendenze
Python nella `.venv` del repository, esegue `npm ci`, compila la SPA e avvia
il backend. Usa il lockfile npm incluso. Nell'ambiente Codex corrente è anche
supportato il Node incluso nel runtime con npm locale in `storage/tools`.
La build e le dipendenze sono già state preparate in questa workspace.

Per gli avvii successivi, senza reinstallare o ricompilare:

```powershell
.\webapp\model_identification_app\start.ps1
```

Aprire **http://127.0.0.1:8766**. Il browser non viene aperto automaticamente.
Usare `-Port 0` per una porta libera (stampata a terminale), oppure `-Port 8767`.
Per fermare il servizio premere Ctrl+C; durante una run l'arresto regolare
attende la fine dei lavori in coda. Un arresto forzato lascia i risultati già
scritti; al riavvio la run viene marcata **Interrotta**, senza essere ripresa
automaticamente. È possibile rieseguirla dalle sue impostazioni.

È ammesso un solo processo sullo stesso storage. Per un altro spazio di lavoro:

```powershell
.\webapp\model_identification_app\start.ps1 -Port 8767 -Storage "C:\percorso\esperimenti"
```

Per ritrovare le run, riavviare con **lo stesso percorso Storage**. Il default
è `webapp/model_identification_app/storage`, indipendente dalla directory
corrente. Il servizio ascolta solo su loopback; non è un servizio multiutente.

## Workflow

1. **Dataset:** importare uno o più ZIP/CSV/FIT dalla lista delle sorgenti in
   `dataset/`, oppure caricare file dal computer. Il caricamento legge tutti
   i record, conserva i CSV originali e rende il dataset persistente.
   I CSV separati possono essere accompagnati dal manifest JSON originale.
2. Selezionare un dataset per leggerne numero di segmenti e durata media ± SD
   campionaria, in secondi. Nei nuovi import la durata riguarda solo t>=0;
   i campioni negativi restano conservati come contesto. SD non definita
   con un solo segmento. Il nome è modificabile senza alterare le run precedenti.
3. Selezionare G1/G2 e UtD/DtU/Ambigui, quindi **Crea dataset** per salvare il
   sottoinsieme. I filtri non modificano il dataset originale. Sono disponibili
   anche gruppi diversi o non classificati se presenti nell'import.
4. Salvare lo split: default **70/10/20**, seed **60**. Le percentuali sono
   assegnate a segmenti interi o a gruppi per `activity_id`, con ordinamento
   iniziale stabile, shuffle PCG64 e metodo dei maggiori resti per gli interi.
   Mostriamo le percentuali effettive dei segmenti. Con pochi gruppi uno dei set
   riservati può essere vuoto. Un nuovo split non modifica le run già avviate.
5. **Identificazione:** scegliere dataset, struttura del modello, uso opzionale
   della pre-window, colonne originali o medie
   mobili già presenti, bounds, multistart e seed del fit. Controllare il
   riepilogo e avviare. Il manifest viene salvato prima di eseguire il primo fit.
6. Nel registro sono disponibili avanzamento, impostazioni, download manifest,
   riesecuzione e apertura dell'analisi. È possibile continuare a usare l'app
   mentre il worker esegue la run; le run vengono elaborate in serie.
7. **Analisi:** qualità della traiettoria, residui, precisione dei parametri e
   identificabilità restano separate. Schede train quattro per pagina, con
   contesto pre-window, potenza, HR osservata/prevista, residui e ACF.
   Zoom temporale sincronizzato, download PNG, **Export CSV** e **Export PDF**.
8. **Confronto:** scegliere due run, anche dello stesso modello. I boxplot
   confrontano parametri con nome e unità compatibili. Non costituiscono un
   confronto predittivo; differenze di dataset/split vengono segnalate.

Per eliminare una run occorre confermare nell'app: i suoi risultati sono
rimossi, **solo il manifest è archiviato**. I dataset e i CSV restano. Dal
registro aprire **Manifest archiviati** per scaricarlo o rieseguire la run.

## Contratto dei dati

### Attività FIT complete

Sono supportati FIT singoli e ZIP contenenti FIT, anche in sottocartelle.
Per `dataset/cleaned_only_road_activieties.zip` scegliere **Importa dalla repository**:
l'archivio contiene collegamenti ai FIT, non i dati binari. La risoluzione è
limitata alle sorgenti in `dataset/`, incluso il collegamento già presente
`dataset/raw/only_road_activities` alla cartella fisica dei raw. Collegamenti
esterni diversi o mancanti vengono rifiutati. Gli ZIP caricati dal browser
devono contenere file reali, non collegamenti.

Ogni FIT diventa una serie di tipo `activity`, senza tagli per lap né classi
G1/G2 o UtD/DtU. Sono conservati tutti i messaggi `record` nell'ordine originale:
timestamp assoluto, secondi dal primo record, potenza in W, HR in bpm e, quando
presenti, cadenza, velocità, quota e temperatura. Per velocità e quota i campi
FIT `enhanced_*` hanno precedenza. Non si importano coordinate GPS nel CSV.
I FIT originali restano conservati come blob immutabili, insieme al CSV derivato;
hash, parser/versione e regole di conversione sono registrati nei metadati.

Nessuna interpolazione, rimozione di campioni, sostituzione dei valori mancanti
o media mobile. Timestamp assenti o non crescenti bloccano l'importazione.
La pagina Dataset mostra campioni mancanti e gap (intervalli superiori a 1,5
volte la mediana), conservando anche conteggio degli zeri e sampling nei
metadati. I dati mancanti impediscono il fitting dell'attività con i modelli
attuali; i gap restano soggetti alle assunzioni temporali del modello esistente.
Queste segnalazioni non costituiscono una valutazione completa della qualità.

Per questi dataset la UI propone lo split **per attività**. L'identità è
`fit:<SHA-256 del FIT>`: copie identiche con nomi diversi restano nello stesso
gruppo. Non è un riconoscimento di registrazioni equivalenti ricodificate né
un collegamento automatico ai segmenti CSV importati separatamente. Lo split di
dataset misti FIT/CSV viene bloccato: importare attività e segmenti in dataset
separati, per evitare sovrapposizioni non riconoscibili tra train e test.
Le attività iniziano a t=0 e non hanno pre-window: lasciare disattivata tale
opzione. Il protocollo di fitting e i modelli restano invariati; validation/test
sono riservati durante il fitting; il test può essere valutato separatamente
nella pagina **Parametri atleta** per le run compatibili.

Il limite cumulativo dei FIT risolti o contenuti negli ZIP è 256 MiB, oltre
ai limiti ZIP e upload indicati sotto. Importazioni errate non creano dataset;
eventuali blob già scritti non modificano le sorgenti.

### Segmenti CSV

Un CSV rappresenta un segmento. Richiesti `elapsed_seconds` e almeno una coppia
`power_w, heart_rate_bpm` oppure `power_ma_w, heart_rate_ma_bpm` (W e bpm).
Le colonne normalizzate non vengono usate nel P1D di questa versione.
`activity_id` è richiesto per costruire lo split; può essere fornito nel CSV
o nel manifest. `first_lap`, `last_lap`, `timestamp` e metadati sorgente sono
preservati quando disponibili. I riferimenti ai FIT non sono necessari al fit:
l'equilibrio iniziale è assunto, non ricostruito dal FIT.

Per più segmenti della stessa attività, lo split per segmento richiede timestamp
assoluti per verificarne la non sovrapposizione; se mancano o condividono campioni
occorre scegliere lo split per attività. Il dataset G1/G2 della repository
include segmenti con estremi inclusivi: questo controllo può quindi intervenire.
Gruppi e classi provengono da `duration_group`, `empirical_label` o cartelle
come `UtD_G1`; non vengono inferiti dalla forma del segnale.

ZIP letti in memoria, senza estrazione: massimo 256 MiB di input totale,
512 MiB espansi per archivio e 10.000 voci. Percorsi unsafe, nomi duplicati,
incoerenze manifest/CSV e tempi non crescenti vengono rifiutati. Nessuna
interpolazione, smoothing, rimozione degli zeri o outlier. Segnali mancanti/non
finiti impediscono il singolo fit e sono riportati come errore, senza cancellare
il segmento. Campionamento irregolare e gap producono segnalazioni.

## Protocollo v3: strutture, inizializzazione e risultati

Modello esplicitamente richiesto dall'utente, non presentato come replica di un
articolo specifico:

```text
tau dx/dt + x = K [P(t-L)-P0]
HRhat(t) = HR0 + x(t)
x(0)=0, P(t<0)=P0
```

La struttura alternativa **short-transient**, scelta esclusivamente dallo
sperimentatore, usa `dx/dt = gamma [P(t-L)-P0]`, `HRhat=HR0+x`, con
`gamma=K/tau` in bpm/(W s). Stima solo gamma e L: K e tau non vengono ricostruiti.
È l'approssimazione del transitorio breve specificata nel protocollo utente,
non una nuova replica bibliografica. La scelta non viene automatizzata.

La pre-window è riconosciuta dai tempi `-10 <= elapsed_seconds < 0`, come
nell'archivio `dataset_segments_G1_G2_extended_10s.zip`. L'uso è **opt-in**:
nella modalità `equilibrium`, quando selezionato, `P0=mean(Ppre)` e `HR0=mean(HRpre)` sono medie aritmetiche
dei campioni dei segnali scelti (raw o medie mobili). La finestra è assunta
di equilibrio; non viene verificata la stazionarietà. Quando disattivata,
`P0=P(0)` e `HR0=HR(0)` usano il primo campione del segmento.
In entrambi i casi i campioni negativi sono esclusi da obiettivo, metriche e T.
Se sono presenti tempi negativi è richiesto un campione a t=0; i CSV storici
con soli tempi positivi vengono riferiti al proprio primo campione.
Prima di t=0 l'ingresso del modello è P0, non la traiettoria misurata pre-window.

La finestra conserva tempi, HR e potenza separatamente nella run. Il manifest
registra presenza, numero campioni, estremi temporali e finitezza dei segnali
per ogni segmento train. La presenza viene riconosciuta dai campioni negativi,
senza imporre una griglia a 1 Hz o ricostruire campioni mancanti. Se richiesta
ma assente o con segnali non finiti, il segmento fallisce esplicitamente
(`pre_window_absent` / `pre_window_nonfinite`). Se non richiesta, eventuali
valori non finiti nel solo contesto sono salvati come null e non entrano nel fit.

Nella modalità `equilibrium` (default storico) si assume equilibrio a t=0 e `x(0)=0`. P0 e HR0 restano riferimenti fissi;
HR0 non è la frequenza cardiaca a riposo. Eventuali transitori già presenti
all'inizio possono distorcere le stime. K è in bpm/W; L e tau in secondi.

La modalità `estimated_equilibrium`, default delle nuove run P1D full, è l'estensione
concordata con l'utente il 28 settembre 2026, senza rivendicare una replica bibliografica:

```text
HRhat(t) = B + [HR(0)-B] exp(-t/tau) + K f(t; L,tau,P-P0)
x(0) = HR(0)-B
```

`f` è la risposta forzata a guadagno unitario del P1D. Si stimano `[K,L,tau,B]`;
B è il livello matematico di equilibrio a P0, in bpm, senza interpretazione
fisiologica. HR(0) è fissata al primo campione del segmento. La pre-window,
se scelta, determina solo P0; la sua HR resta contesto e può essere mancante.
La potenza precedente resta approssimata da P0, senza ricostruirla dai FIT.
Prima del ritardo è così possibile una discesa o salita esponenziale.
I due `equilibrium_bounds` devono essere finiti e crescenti, scelti esplicitamente
dallo sperimentatore: campi vuoti impediscono l'avvio della modalità alternativa.
Non sono derivati dal range HR del lap. Short-transient resta invariato.
B può compensarsi con K/tau: SE, CI, rango e correlazioni restano separati dalla
qualità di traiettoria. La baseline è il P1D in equilibrio con lo stesso solver
migliorato. I test verificano soluzione analitica e recupero su dati sintetici;
il confronto in-sample non dimostra capacità predittiva fuori campione.

La potenza è mantenuta costante tra due campioni (zero-order hold); la risposta
del primo ordine, o dell'integratore short-transient, viene integrata esattamente, con ritardo continuo, anche
frazionario. Questa è una convenzione di simulazione dichiarata, non un
ricampionamento dei dati. Anche durante un gap la potenza viene mantenuta
costante, con segnalazione del gap se dt > 1,5 × mediana(dt).

Fitting con `scipy.optimize.least_squares`, TRF, loss `linear` (SSE), Jacobiano
`3-point`, `x_scale='jac'`, tolleranze ftol/xtol/gtol=1e-8.
Documentazione primaria: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html

Default editabili: K in [1e-6,5], L in [0,T], tau in [0.01,1800], otto start,
seed 42, massimo 500 valutazioni per start (escluse quelle per le differenze
finite). Sono limiti numerici, non fisiologici. Primo start [0.3,5,45] adattato
all'interno dei bounds; altri start deterministici uniformi in L e log-uniformi
in K/tau. Selezioniamo la soluzione con SSE minimo, dichiarando eventuale
mancata convergenza. Ogni start conserva parametri iniziali/finali, SSE e status.

Per le nuove run P1D, `search_strategy=profile_multistart` aggiunge una griglia
di 301 ritardi uniformi nei bounds effettivi e 141 tau log-spaziati. Con L fissato
si usa un solo ritardo. Per ogni coppia si calcola analiticamente K ottimo nei
bounds; con B stimato si risolve congiuntamente il problema lineare K/B vincolato,
valutando soluzione interna e quattro lati del rettangolo dei bounds, anche
in presenza di disegni singolari. Si raffinano fino a 8 candidati separati almeno
0.05 nel piano degli indici normalizzati della griglia, con TRF su tutti i
parametri liberi. Restano tutti gli start originali; vince la SSE minima.
Non è garantito il minimo globale. `n_starts` conta solo gli start originali.
Configurazione e manifest conservano dimensioni della griglia e raffinamenti;
ogni tentativo salva `source`. `search` registra numero di coppie, SSE minima
della griglia, SSE del multistart originale e origine della soluzione selezionata.
La covarianza usa il Jacobiano completo finale, non quello del problema profilato.
Gli start casuali di B sono uniformi; il nominale è HR(0) limitato nei bounds.
Il replay di run senza `search_strategy` conserva `multistart`; la modalità
storica resta `equilibrium`. Le run precedenti non vengono riscritte.

Per short-transient i bounds iniziali di gamma sono [1e-6/1800, 5/0.01],
derivati dagli estremi ammessi di K/tau, e restano modificabili. Il primo start
è [0.3/45,5]; gli altri sono log-uniformi in gamma e uniformi in L.

Dal protocollo P1D 1.1.0, T = ultimo tempo meno primo tempo del segmento.
`upper[1]=null` (campo UI vuoto) usa T; un massimo personalizzato in secondi
usa min(Lmax,T) per ciascun segmento. Il minimo di L resta zero. Lmax=0
fissa L=0 e stima soltanto K e tau, oppure gamma. Ogni risultato conserva
`segment_duration_seconds` e `effective_bounds`; il manifest conserva la
configurazione richiesta. I risultati storici non vengono riscritti.

Le stime sono in `parameters.{K,L,tau}.estimate` (anche B se stimato) oppure `parameters.{gamma,L}.estimate`.
Ogni parametro espone `se`, `ci95`, `rse_pct`, `at_bound` (alias `bound_hit`), `near_bound`, `fixed`.
Per ogni parametro, `at_bound` usa la distanza dal limite più vicino con
tolleranza 32 × eps(float64) × max(1,abs(lower),abs(upper)); `near_bound`
usa max(tolleranza al bound, 1e-5 × (upper-lower)). Un parametro al bound è
anche vicino al bound. Tolleranze assolute e distanze da entrambi i limiti
sono salvate per parametro, nelle rispettive unità.
Lo status numerico
è `optimizer.status`, con `success` e `message`. Le metriche sono:

- `RMSE = sqrt(SSE/N)`, `MAE = mean(abs(HR-HRhat))`, `bias = residual_mean = mean(HR-HRhat)`;
- `R2 = 1-SSE/sum((HR-mean(HR))²)` e
  `amplitude_ratio = range(HRhat)/range(HR)`; entrambi `null` per HR costante;
- `residual_sd`: SD campionaria con ddof=1;
- `residual_autocorrelation_lag1`: somma dei prodotti dei residui centrati
  adiacenti divisa per la somma dei quadrati centrati. Il lag è in campioni,
  non necessariamente un secondo; non definita se i residui sono costanti.
  La stessa formula è applicata al lag 5. `residual_acf` conserva i lag
  da 0 a min(40,N-1), senza interpolazione; lag 5 è null se N<=5.

Covarianza = SSE/(N-p) × inv(JᵀJ), con p numero di parametri liberi
(3 per P1D in equilibrio, 4 con B stimato, 2 per short-transient, meno uno se L fissato), implementata via SVD equivalente evitando
di formare l'inversa delle equazioni normali. CI95 = stima ± 1,96 SE, senza
troncamento ai bounds; RSE = 100 SE/abs(stima), non definito se abs(stima)<1e-8.
La riga iniziale è compresa in N: la previsione è HR0, che con pre-window
può differire dall'osservazione HR(0).
Con B stimato il residuo iniziale è zero per costruzione. La scala SSE/(N-p)
resta quella della pipeline: approssimazione locale condizionata al campione
HR(0), senza propagare l'incertezza di tale misura.
Con rango insufficiente covariance/SE/CI/RSE non vengono dichiarati.
Con L fissato, le sue SE/CI/RSE sono `null`; la matrice di covarianza mantiene
l'ordine dei parametri della struttura, con riga e colonna zero per il parametro fissato.
Le correlazioni sono cov(i,j)/sqrt(cov(i,i)cov(j,j)); null se non definibili.
`rho=(T-L)/tau` è salvato per P1D full; per short-transient è null e
`rho_applicable=false`. Non esistono soglie o esclusioni basate su rho.

Warning per bounds vicini, rango ridotto, condizionamento del Jacobiano >1e8,
abs(ACF1)>0,5, input costante e disaccordo multistart. L'accordo usa tolleranza
relativa 5% e assoluta 0,01 per K/L/tau/B, 1e-6 bpm/(W s) per gamma;
le tolleranze sono salvate in `multistart_tolerances`.
Soluzioni con SSE entro max(1e-8,1% SSE migliore)
sono confrontate anche per segnalare predizioni equivalenti e parametri diversi.
`optimizer_success` riporta la convergenza; `identification_valid` richiede
anche parametri e residui finiti e parametri nei bounds effettivi, incluso
0 ≤ L ≤ T. Se il controllo interno fallisce, il record è `failed`, viene
conteggiato come fallito ed escluso dai boxplot e dai confronti dei fit.
`failure_reasons` ed `error` motivano il fallimento; le diagnostiche restano
negli output completi. Prima dell'ottimizzazione `optimizer_success` è `null`.
La validità operativa non certifica identificabilità, precisione o qualità
della traiettoria: rango, CI, RSE e multistart rimangono diagnostiche separate.
I boxplot includono i fit validi anche con warning. La configurazione principale
aggiunge solo le scelte necessarie; l'analisi organizza metriche e diagnostiche
in aree distinte con dettagli espandibili.

L'incertezza è **locale, approssimata e condizionata ai riferimenti iniziali**.
Non corregge autocorrelazione, errore sull'ingresso o preprocessing precedente.
Un buon fit e CI stretti non dimostrano ripetibilità o generalizzazione.
Baseline statica e verifica fuori campione sono rinviate in questo esperimento.

## Persistenza e riproduzione

```text
storage/
  datasets/<id>.json          dataset importati, filtri e split corrente
  blobs/<sha256>             CSV originali e snapshot del codice
  runs/<nome-leggibile>.json manifest della run, scritto atomicamente
  runs/<id>/<segment>.json   stime, diagnostica e serie train
  runs/<id>/exports/         report.pdf e tables.zip generati su richiesta
  archived_manifests/*.json  solo manifest delle run eliminate
```

Nome esempio: `20260926T080000Z__G1-UtD__p1d__raw__70-10-20__s42__n8-f42__<id>.json`.
`s42` è il seed split, `n8-f42` indica numero start e seed del fit; i bounds
completi sono nel manifest. ID univoco per distinguere run con stessi parametri.

Il manifest congela dataset, hash CSV, provenienza/preprocessing, filtri, tutti
gli ID train/val/test, percentuali, seed, colonne, equazioni e condizioni
iniziali, configurazione completa del solver, versioni Python/pacchetti e hash
del codice. Le sorgenti Python e Vue e i lockfile sono copiati nei blob:
`environment.code_blobs` mappa il percorso relativo al rispettivo SHA256.
Questi snapshot permettono il ripristino del codice oltre alla verifica degli hash.

**Ripeti impostazioni** usa i CSV e lo split congelati, senza risplittare o
dipendere dal nome corrente del dataset. Usa il codice installato al momento:
se differisce, la nuova run lo segnala. Per riproduzione rigorosa utilizzare
anche lo snapshot del codice e le versioni dell'ambiente originale; non è
garantita identità bit-per-bit fra piattaforme o librerie numeriche diverse.

Le run schema v1 vengono lette senza riscriverle. Una loro riesecuzione usa
`initialization_protocol=legacy_v1`: primo record, inclusi eventuali tempi
negativi nel vecchio obiettivo, e bounds inferiori L storici conservati.
Questo protocollo non è ammesso per nuove run via API/UI. La riesecuzione
registra la differenza di codice e l'inclusione storica del contesto; per
applicare il nuovo protocollo creare una nuova run dalla configurazione.

Il manifest schema v2 esplicita `model_structure`, `pre_window_seconds`,
`use_pre_window`, `P0_method`, `HR0_method`, `parameter_bounds`, `n_multistart`,
`optimizer_settings`, inventario della finestra e schema della diagnostica rho.

Gli export sono disponibili dopo la conclusione della run, anche con errori.
**Export CSV** scarica un ZIP con fits, parameters, multistart, series,
pre_window e residual_acf in CSV UTF-8, oltre a manifest e risultati JSON
integrali. Celle vuote indicano valori non disponibili/non applicabili.
**Export PDF** genera il report dalla run salvata, senza rifare fitting:
configurazione e numerosità, aggregati della qualità e dei residui, distribuzioni
e precisione dei parametri, identificabilità/multistart/rho, schede di tutti i
segmenti inclusi i fallimenti, e appendice della configurazione con ambiente.
Gli aggregati usano solo i fit validi, non pesati per durata, con n dei valori
disponibili; non producono interpretazioni fisiologiche. Gli export conservati
in `runs/<id>/exports/` vengono sostituiti alla successiva esportazione e
rimossi insieme ai risultati quando si elimina la run.

Per backup copiare l'intera directory storage a servizio fermo, insieme
all'app e ai suoi lockfile. Il solo manifest documenta l'esperimento ma per
rieseguirlo servono anche i CSV identificati dagli hash. Lo storage è escluso
da Git e non viene cancellato dagli avvii o dalle build.

## Estensione con altri modelli

Registrare un modulo in `backend/models/__init__.py` con `METADATA`,
`default_config`, `validate_config`, `fit(t,power,hr,config)`. Il risultato
espone parametri con unità, metriche, diagnostica e serie. In
`src/models/registry.ts` registrare componenti separati per fit, distribuzioni
e confronto. Questa prima versione include soltanto P1D; introdurre nuovi
modelli richiede una decisione scientifica e relativa validazione.

## Verifiche

Dalla radice del repository:

```powershell
.\.venv\Scripts\python -m pytest webapp/model_identification_app/tests
```

Dalla directory dell'app:

```powershell
npm test
npm run build
```

Test numerici con risposte analitiche e covariance da sensibilità analitiche;
import/split, sovrapposizioni, persistenza/replay/archivio; interazioni Vue e
boxplot. `storage/browser-check` e `storage/test-*`, se presenti, sono spazi
di verifica separati dal catalogo di esperimenti dell'app.
