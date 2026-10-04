# HR–Power: strumenti per lo studio individuale del ciclista

Il repository raccoglie un percorso di lavoro sui dati reali di potenza e frequenza
cardiaca: esplorazione, preparazione, identificazione dinamica, verifica delle
predizioni e restituzione dei risultati. Il modello è uno strumento di questo
pacchetto di analisi. La [storia del progetto](history.md) racconta i risultati e
il possibile utilizzo per atleti e coach.

## Le due web app

| App | A cosa serve | Guida |
| --- | --- | --- |
| Dataset Exploration | Aprire FIT e ZIP, ispezionare attività e lap, selezionare segmenti, esportarli e applicare preprocessing esplicito | [Dettagli](webapp/dataset_exploration/README.md) |
| Identificazione HR–Power | Importare dati, separare attività train/test, stimare il modello, analizzare i fit e prevedere HR sui segmenti test | [Dettagli](webapp/model_identification_app/README.md) |

Le app funzionano in locale su Windows. I FIT sorgente restano invariati.

## Preparazione iniziale

Servono Python 3.14 (versione usata nel progetto), Node.js >=22.12 con npm e accesso
ai registry per la prima installazione. Aprire PowerShell nella radice della repo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r webapp/model_identification_app/requirements.txt

Push-Location webapp/dataset_exploration
npm.cmd ci
npm.cmd run build
Pop-Location

Push-Location webapp/model_identification_app
npm.cmd ci
npm.cmd run build
Pop-Location
```

Se l'ambiente esiste già, riutilizzarlo. Dopo modifiche al frontend ricompilare
la relativa app. Per la sola identificazione, `start.ps1 -Setup` installa le sue
dipendenze e compila il frontend prima dell'avvio.

## Avvio quotidiano

Per esplorare i dati:

```powershell
.\webapp\dataset_exploration\start.ps1
```

Si apre il browser; la porta cambia a ogni avvio. Usare l'indirizzo stampato nel
terminale. Per identificazione e consultazione delle run, in un altro terminale:

```powershell
.\webapp\model_identification_app\start.ps1
```

Aprire **http://127.0.0.1:8766**. Se il servizio è già attivo, usare quello:
non avviare due processi sullo stesso storage. `-Port 0` sceglie una porta libera,
stampata nel terminale.

Ctrl+C arresta il servizio; l'app di identificazione attende regolarmente i lavori
in coda. Un arresto forzato può lasciare una run interrotta: i risultati scritti
restano, ma la run non riprende automaticamente. Rieseguirla avvia un nuovo lavoro.

## Dalle attività ai risultati

### 1. Ispezionare ed esportare

In **Dataset Exploration**, usare **Sfoglia cartelle / ZIP**, caricare i FIT e
aprire le attività. Controllare segnali, lap, interruzioni e motivi di esclusione.
Unire eventualmente lap adiacenti, aggiungere i segmenti alla coda e controllarli
in **Pre-esportazione** prima di scaricare lo ZIP.

Lo ZIP contiene CSV e manifest: conservare entrambi. In **Elaborazione dataset**
si possono applicare medie mobili di 3, 5 o 10 secondi e normalizzazioni dichiarate.
Controllare l'anteprima prima di esportare. Questo passaggio è facoltativo:
le run attuali usano potenza e HR originali. Le medie centrate sono elaborazioni
offline che usano anche campioni successivi.

Gli ZIP con collegamenti ai FIT funzionano soltanto se gli originali sono ancora
raggiungibili. Per trasferire un dataset usare file incorporati, non link locali.

### 2. Importare e separare le attività

In **Identificazione HR–Power → Dataset**, importare ZIP/CSV/FIT dal computer o dalle
sorgenti locali. Si possono importare anche attività complete senza estrarre lap.
Leggere le segnalazioni su valori mancanti e gap prima del fitting.

Creare lo split **per attività**, mantenendo i segmenti della stessa uscita nello
stesso insieme. Salvare percentuali e seed prima di iniziare. Il 70/10/20 riserva
train, validation e test; la procedura attuale non usa la validation.
Il dataset corrente è `dataset/road_segments_gt10s_min5min.zip`, disponibile nella
workspace locale ma non incluso nel normale checkout Git.

### 3. Identificare e leggere i fit

In **Identificazione**, scegliere dataset, segnali, struttura e impostazioni;
controllare il riepilogo e avviare. Si stima un modello indipendente su ciascun
segmento train. La configurazione corrente usa **P1D completo**, equilibrio stimato,
segnali originali, nessuna pre-window e ritardo fissato a zero. Per ripetere un
esperimento usare le sue impostazioni salvate, non i default dell'interfaccia.

Il registro mostra avanzamento ed errori. In **Analisi**, confrontare HR misurata,
HR ricostruita, residui e diagnostica dei parametri. Un fit visivamente buono non
basta a rendere ogni parametro affidabile. **Confronto** accosta le distribuzioni
di due run e segnala differenze di dati e split.

### 4. Prevedere i segmenti test

In **Parametri atleta**, scegliere una run compatibile: P1D completo con equilibrio
stimato e protocollo `segment_v2`. Controllare esclusioni e soglie di qualità
prima di stimare i parametri condivisi tra segmenti train dello stesso atleta.
Qui “popolazione” indica la variabilità tra segmenti, non un insieme di atleti.

La modalità corrente **B locale, 180 s** mantiene fissi i parametri dinamici dal
train e calibra il livello sui primi tre minuti di HR del segmento test. Poi simula
HR usando la potenza, senza correggersi sulla HR successiva. Le metriche riguardano
solo la coda da 180 s in avanti. Restano disponibili la calibrazione a 10 s e la
modalità con sola HR iniziale; le analisi storiche conservano la loro configurazione.
Se mancano dati sufficienti, il fallimento viene riportato.

Leggere errori, grafici e casi falliti insieme. Cambiare le scelte dopo aver visto
il test rende esplorativo il confronto. Le fasce rappresentano la variabilità dei
parametri simulati, non tutti gli errori possibili. Il
[protocollo](webapp/model_identification_app/POPULATION_PROTOCOL.md) documenta
calibrazione, screening e valutazione.

### 5. Conservare e condividere i risultati

Usare il download del manifest, **Export CSV**, **Export PDF** e gli export della
pagina **Parametri atleta**. Accompagnare i grafici con configurazione, numero di
casi riusciti/falliti e distinzione tra fitting, calibrazione e test.

## Studio corrente e persistenza

La pulizia del 4 ottobre 2026 conserva nel registro:

| Run | Split seed | Stato alla milestone |
| --- | ---: | --- |
| `b4ac2e8208374c9fbf18a4009dc0e2fc` | 52 | Terminata con errori: 219 fit riusciti su 250; analisi test disponibile |
| `8dc6d46a06e6496aab0ba80040ba56ad` | 60 | In corso allo snapshot, poi terminata con errori: 211 fit riusciti su 239 |

Dataset, blob sorgente e risultati sono in `webapp/model_identification_app/storage`.
Lo storage è locale e ignorato da Git: farne una copia coerente, a servizio fermo,
per un backup completo. Per usare uno storage diverso:

```powershell
.\webapp\model_identification_app\start.ps1 -Port 8767 -Storage "C:\percorso\studio"
```

Riutilizzare lo stesso percorso per ritrovare le run. Eliminare una run dall'app
rimuove i risultati e archivia solo il manifest: non equivale a un backup.
I dati raw e gli strumenti riutilizzabili di preparazione restano conservati.

Lo snapshot precedente alla pulizia è nella branch **`milestone/2026-10-04-hr-power`**,
commit **`c95496e`**. Include codice e `milestone_artifacts/`, con copie degli artefatti
scientifici, inventario SHA-256 e istruzioni di recupero. Consultarlo in un checkout
separato, senza sostituire lo storage di un servizio attivo. La copia della run
allora in corso è parziale, non un checkpoint. La branch è locale: per un backup
fuori da questo PC occorre trasferirla.

Il [riepilogo verificabile](reports/current_study/summary.json) riporta gli aggregati
della run completa e gli hash delle sorgenti. Per rigenerarlo dalla workspace:

```powershell
.\.venv\Scripts\python.exe scripts/summarize_current_study.py
```

## Verifiche del software

I test automatici sono mantenuti dopo la pulizia degli esperimenti storici.
In un ambiente di sviluppo con `pytest` e `httpx` installati:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\src"
.\.venv\Scripts\python.exe -m pytest tests webapp/model_identification_app/tests webapp/dataset_exploration/tests -q

Push-Location webapp/dataset_exploration
npm.cmd test -- --run
npm.cmd run build
Pop-Location

Push-Location webapp/model_identification_app
npm.cmd test
npm.cmd run build
Pop-Location
```
