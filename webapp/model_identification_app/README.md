# Identificazione HR–Power

SPA Vue locale per importare segmenti, creare split riproducibili e identificare
un P1D indipendente su ogni segmento **train**. Validation e test vengono
riservati, ma non sono utilizzati. Non viene misurata capacità predittiva fuori
campione, né si attribuisce significato fisiologico ai parametri.

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

1. **Dataset:** importare uno o più ZIP/CSV dalla lista delle sorgenti in
   `dataset/`, oppure caricare file dal computer. Il caricamento legge tutti
   i record, conserva i CSV originali e rende il dataset persistente.
   I CSV separati possono essere accompagnati dal manifest JSON originale.
2. Selezionare un dataset per leggerne numero di segmenti e durata media ± SD
   campionaria, in secondi. Durata = ultimo meno primo tempo; SD non definita
   con un solo segmento. Il nome è modificabile senza alterare le run precedenti.
3. Selezionare G1/G2 e UtD/DtU/Ambigui, quindi **Crea dataset** per salvare il
   sottoinsieme. I filtri non modificano il dataset originale. Sono disponibili
   anche gruppi diversi o non classificati se presenti nell'import.
4. Salvare lo split: default **70/10/20**, seed **42**. Le percentuali sono
   assegnate a segmenti interi o a gruppi per `activity_id`, con ordinamento
   iniziale stabile, shuffle PCG64 e metodo dei maggiori resti per gli interi.
   Mostriamo le percentuali effettive dei segmenti. Con pochi gruppi uno dei set
   riservati può essere vuoto. Un nuovo split non modifica le run già avviate.
5. **Identificazione:** scegliere dataset, modello, colonne originali o medie
   mobili già presenti, bounds, multistart e seed del fit. Controllare il
   riepilogo e avviare. Il manifest viene salvato prima di eseguire il primo fit.
6. Nel registro sono disponibili avanzamento, impostazioni, download manifest,
   riesecuzione e apertura dell'analisi. È possibile continuare a usare l'app
   mentre il worker esegue la run; le run vengono elaborate in serie.
7. **Analisi:** boxplot delle stime e tutti i fit train, quattro per pagina,
   con potenza, HR osservata/prevista e residui. Zoom sincronizzato e download
   PNG tramite il controllo ECharts. Metriche, SE/CI/RSE e diagnostica per fit.
8. **Confronto:** scegliere due run, anche dello stesso modello. I boxplot
   confrontano parametri con nome e unità compatibili. Non costituiscono un
   confronto predittivo; differenze di dataset/split vengono segnalate.

Per eliminare una run occorre confermare nell'app: i suoi risultati sono
rimossi, **solo il manifest è archiviato**. I dataset e i CSV restano. Dal
registro aprire **Manifest archiviati** per scaricarlo o rieseguire la run.

## Contratto dei dati

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

## P1D v1: assunzioni e risultati

Modello esplicitamente richiesto dall'utente, non presentato come replica di un
articolo specifico:

```text
tau dx/dt + x = K [P(t-L)-P0]
HRhat(t) = HR0 + x(t)
P0=P(0), HR0=HR(0), x(0)=0, P(t<0)=P0
```

Si assume equilibrio al primo campione. P0 e HR0 restano riferimenti fissi;
HR0 non è la frequenza cardiaca a riposo. Eventuali transitori già presenti
all'inizio possono distorcere le stime. K è in bpm/W; L e tau in secondi.

La potenza è mantenuta costante tra due campioni (zero-order hold); la risposta
del primo ordine viene integrata esattamente, con ritardo continuo, anche
frazionario. Questa è una convenzione di simulazione dichiarata, non un
ricampionamento dei dati. Anche durante un gap la potenza viene mantenuta
costante, con segnalazione del gap se dt > 1,5 × mediana(dt).

Fitting con `scipy.optimize.least_squares`, TRF, loss `linear` (SSE), Jacobiano
`3-point`, `x_scale='jac'`, tolleranze ftol/xtol/gtol=1e-8.
Documentazione primaria: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html

Default editabili: K in [1e-6,5], L in [0,120], tau in [0.01,1800], otto start,
seed 42, massimo 500 valutazioni per start (escluse quelle per le differenze
finite). Sono limiti numerici, non fisiologici. Primo start [0.3,5,45] adattato
all'interno dei bounds; altri start deterministici uniformi in L e log-uniformi
in K/tau. Selezioniamo la soluzione con SSE minimo, dichiarando eventuale
mancata convergenza. Ogni start conserva parametri iniziali/finali, SSE e status.

Le stime sono in `parameters.{K,L,tau}.estimate` (K_hat/L_hat/tau_hat).
Ogni parametro espone `se`, `ci95`, `rse_pct`, `at_bound`. Lo status numerico
è `optimizer.status`, con `success` e `message`. Le metriche sono:

- `RMSE = sqrt(SSE/N)`, `residual_mean = mean(HR-HRhat)`;
- `residual_sd`: SD campionaria con ddof=1;
- `residual_autocorrelation_lag1`: somma dei prodotti dei residui centrati
  adiacenti divisa per la somma dei quadrati centrati. Il lag è in campioni,
  non necessariamente un secondo; non definita se i residui sono costanti.

Covarianza = SSE/(N-3) × inv(JᵀJ), implementata via SVD equivalente evitando
di formare l'inversa delle equazioni normali. CI95 = stima ± 1,96 SE, senza
troncamento ai bounds; RSE = 100 SE/abs(stima), non definito se abs(stima)<1e-8.
La riga iniziale, esattamente fissata a HR(0), è compresa in N come da protocollo.
Con rango insufficiente covariance/SE/CI/RSE non vengono dichiarati.

Warning per bounds vicini, rango ridotto, condizionamento del Jacobiano >1e8,
abs(ACF1)>0,5, input costante e disaccordo multistart. L'accordo usa tolleranza
relativa 5% e assoluta 0,01; soluzioni con SSE entro max(1e-8,1% SSE migliore)
sono confrontate anche per segnalare predizioni equivalenti e parametri diversi.
I boxplot includono tutte le stime prodotte, anche con warning o ottimizzatore
non convergente; i fallimenti privi di stima sono esclusi e conteggiati.

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
