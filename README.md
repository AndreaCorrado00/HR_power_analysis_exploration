# Studio HR / Power

**Dallo storico degli allenamenti alla previsione della risposta cardiaca del singolo ciclista.**

Questa suite locale aiuta il preparatore a rispondere a una domanda concreta:
*conoscendo come un atleta ha risposto alla potenza nelle sedute precedenti, quale andamento della frequenza cardiaca possiamo attenderci in un nuovo allenamento?*

Si importano le attività, si costruisce un modello individuale e lo si mette alla prova su sedute successive. Si può poi preparare un allenamento, salvarne la previsione **prima dell'esecuzione** e confrontarla con il FIT registrato dall'atleta. Potenza e frequenza cardiaca si leggono lungo tutta la seduta, comprese ripetute, recuperi e transizioni.

Il progetto nasce da uno studio sulla relazione potenza–frequenza cardiaca nel ciclismo. L'app ne raccoglie il metodo in un ambiente utilizzabile con più atleti, mantenendo separati dati, modelli e risultati di ciascuno. Non serve un account online: interfaccia e calcoli lavorano sul computer che avvia il servizio.

## Indice

- [Cosa si ottiene](#cosa-si-ottiene)
- [Installazione e avvio](#installazione-e-avvio)
- [Il percorso di lavoro](#il-percorso-di-lavoro)
- [Come leggere i risultati](#come-leggere-i-risultati)
- [Preparare e importare una prescrizione](#preparare-e-importare-una-prescrizione)
- [Metodo e assunzioni](#metodo-e-assunzioni)
- [Letteratura di riferimento](#letteratura-di-riferimento)
- [Dati, backup e archivio storico](#dati-backup-e-archivio-storico)
- [Problemi frequenti](#problemi-frequenti)
- [Struttura del repository e verifiche](#struttura-del-repository-e-verifiche)

## Cosa si ottiene

| Strumento | Utilità per il preparatore |
|---|---|
| Storico individuale | Consultare potenza e frequenza cardiaca, individuare le attività utilizzabili e vedere i problemi di registrazione. |
| Modello dell'atleta | Riassumere con pochi parametri come la frequenza cardiaca segue le variazioni di potenza nei dati disponibili. |
| Verifica su sedute successive | Misurare quanto il modello si discosta dai dati che non ha usato per costruirsi. |
| Previsione di una seduta | Visualizzare potenza eseguita attesa e risposta cardiaca attesa a partire dai blocchi prescritti. |
| Confronto dopo l'allenamento | Separare lo scostamento nell'esecuzione dalla difficoltà di prevedere la risposta cardiaca. |
| Versioni e confronto tra atleti | Conservare la storia dei modelli e confrontare i parametri insieme ai periodi e alle intensità rappresentate. |

Il risultato utile non è soltanto una curva che segue bene i dati. È una previsione accompagnata da **errore, condizioni di utilizzo e tracciabilità**: quali allenamenti l'hanno costruita, quale modello è stato usato e che cosa era noto quando è stata salvata.

La suite non prescrive automaticamente l'allenamento e non assegna un punteggio di forma o fatica. Un parametro che cambia è un dato da approfondire nel contesto dell'atleta; da solo non dimostra un miglioramento, un peggioramento o una causa fisiologica.

## Installazione e avvio

Il percorso di avvio fornito è per **Windows con PowerShell**. L'ambiente di sviluppo e verifica usa Python 3.14; per compilare l'interfaccia occorrono Node.js 22.12 o successivo e npm. Le dipendenze sono registrate in [requirements.txt](study_app/requirements.txt) e [package-lock.json](study_app/frontend/package-lock.json).

Scaricare o clonare il repository, aprire PowerShell nella sua cartella e, al primo avvio, eseguire:

```powershell
.\study_app\start.ps1 -Setup
```

Il comando prepara l'ambiente Python, installa le dipendenze, compila l'interfaccia e avvia il servizio. L'installazione delle dipendenze richiede accesso a Internet. Su un nuovo checkout questa preparazione è necessaria: ambiente Python e interfaccia compilata non sono conservati in Git.

Per gli avvii successivi:

```powershell
.\study_app\start.ps1
```

Aprire **http://127.0.0.1:8770**. Tenere aperta la finestra PowerShell mentre si usa l'app: chiuderla può interrompere un'importazione o un'elaborazione. Per fermare il servizio usare `Ctrl+C`; se un'elaborazione è attiva, l'arresto può attendere il suo termine.

Se serve una porta diversa:

```powershell
.\study_app\start.ps1 -Port 8775
```

L'avvio dell'app e l'importazione dei file **non stimano alcun modello**. L'identificazione parte soltanto con il comando esplicito dell'utente. In una nuova installazione lo spazio di lavoro è vuoto; riavviare un'installazione già usata conserva gli atleti e i risultati presenti.

## Il percorso di lavoro

### 1. Aggiungere l'atleta e caricare lo storico

Inserire nome, cognome, età e, se disponibile, FTP. Importare uno o più file **FIT originali**, oppure uno ZIP contenente FIT anche in sottocartelle. Occorrono registrazioni di potenza e frequenza cardiaca per costruire il modello HR.

La FTP è facoltativa per creare l'anagrafica e consultare i file, ma serve per applicare le regole congelate di ricostruzione dei target. Si può modificarla e richiedere una nuova preparazione dello storico; gli esperimenti già salvati mantengono la propria revisione dei dati.

Per ogni attività lo storico mostra utilizzabilità e qualità dei dati. Con **Apri**, grafico e dettagli compaiono sotto la riga dell'allenamento; **Chiudi** li richiude. Lo zoom permette di concentrarsi su una ripetuta o un recupero. I segnali comprendono potenza reale, target ricostruito quando disponibile e frequenza cardiaca.

**Il target ricostruito non è il programma originale del preparatore.** Le regole storiche del progetto, chiamate regole AR, riconoscono i lap e ricostruiscono una prescrizione compatibile con quanto registrato. Servono allo studio retrospettivo; non provano che quel target fosse noto prima della seduta.

Un'attività importata può risultare esclusa dall'identificazione: per esempio, perché mancano lap riconoscibili, FTP o tratti continui sufficienti. I file restano consultabili. Gap, campioni mancanti e anomalie vengono segnalati; non vengono riparati con interpolazioni implicite.

### 2. Costruire e verificare il modello

Creare un esperimento scegliendo atleta, data di separazione e fuso orario. La suite divide le attività in ordine cronologico, senza mescolare casualmente i secondi di una stessa seduta:

| Parte dello storico | Come viene usata |
|---|---|
| **Train**: attività iniziate prima della mezzanotte della data scelta | Serve a stimare i parametri del modello. |
| **Validation**: attività iniziate dalla data scelta compresa | Serve a verificare il modello senza ristimarlo su quelle attività. |
| **Verifica prospettica**: nuova seduta, con previsione già salvata prima della partenza | Serve a verificare ciò che era effettivamente prevedibile prima di osservare l'allenamento. |

Per esempio, scegliendo il 1° settembre, le attività iniziate fino al 31 agosto appartengono al train; quelle dal 1° settembre appartengono alla validation. Una seduta è assegnata interamente in base al suo inizio.

Prima di avviare, leggere il riepilogo: conta **attività, tratti e campioni effettivamente utilizzabili**, non soltanto i file caricati. Il protocollo richiede almeno cinque tratti HR utilizzabili nel train; superare questo controllo non garantisce che i dati bastino a ottenere parametri affidabili.

Con **Avvia identificazione** la suite stima il modello ausiliario di potenza e quello cardiaco, raccoglie i parametri HR dei tratti utilizzabili e calcola i risultati sulla validation. Le configurazioni sono congelate: non viene cercato automaticamente un modello diverso quando il risultato è insoddisfacente.

Nella pagina dei risultati si scorrono le sedute di validation, le traiettorie, gli errori e i residui. Un'elaborazione che fallisce conserva la diagnostica; una previsione poco accurata resta un risultato da considerare, non viene nascosta sostituendo il modello.

### 3. Conservare le versioni dell'atleta

Ogni identificazione completata produce una versione con periodo e attività usati, configurazione, parametri, risultati e campo di potenze e durate rappresentato nei dati.

Prima di usare una versione per una nuova seduta, controllare quanto quella seduta assomiglia al materiale su cui il modello è stato costruito. Un modello basato soprattutto su lavori brevi e moderati ha meno evidenza a sostegno di previsioni per una seduta lunga o a intensità poco rappresentate.

Una nuova importazione non aggiorna il modello. Per aggiornarlo occorre creare esplicitamente un nuovo esperimento. Le sedute entrate nel train della nuova versione conservano il loro ruolo di verifica della versione precedente.

### 4. Preparare una seduta e salvarne la previsione

Nell'editor si costruiscono blocchi e ripetizioni indicando durata e potenza target, oppure si importa una prescrizione JSON o CSV. Si sceglie una versione del modello dell'atleta e si imposta la simulazione.

Il grafico sovrappone prescrizione, potenza eseguita prevista e HR prevista. Le fasce di variabilità di potenza e HR si possono attivare separatamente. La simulazione ripete il calcolo con diverse realizzazioni ammesse dal modello: la curva media riassume questi tentativi.

**Salvare la previsione prima dell'allenamento.** Insieme ai segnali vengono conservati prescrizione, modello, impostazioni della simulazione e data di creazione. È questa fotografia che verrà confrontata con l'esecuzione, senza riscriverla a posteriori.

### 5. Confrontare ciò che è accaduto

Importare il FIT della nuova seduta e associarlo alla previsione salvata. La pagina distingue tre letture:

| Confronto | Domanda a cui risponde |
|---|---|
| **Esecuzione**: potenza prescritta, prevista e reale | Quanto l'atleta si è discostato dal lavoro previsto? |
| **Previsione a priori**: HR salvata prima della seduta contro HR registrata | Quanto siamo riusciti a prevedere prima di conoscere l'esecuzione? |
| **Diagnostica successiva**: HR ricalcolata dalla potenza reale contro HR registrata | Conoscendo il lavoro effettivamente svolto, quanto errore rimane nella risposta HR? |

Se il terzo confronto migliora molto rispetto al secondo, lo scostamento nell'esecuzione può spiegare una parte dell'errore. Non significa che la previsione originale fosse corretta. Se anche il terzo confronto è scarso, il modello potenza–HR o le condizioni della registrazione richiedono attenzione; la sola curva non identifica la causa.

Le metriche di aderenza e gli scostamenti per blocco accompagnano il risultato dell'intera sessione. Se l'atleta cambia l'allenamento, la seduta resta informativa: non si eliminano automaticamente le parti più difficili da prevedere.

### 6. Seguire il lavoro nel tempo

La valutazione raccoglie i confronti associati alle versioni del modello. Si possono anche scegliere due atleti e leggere i loro parametri con una guida interpretativa.

Il confronto ha senso insieme a periodo, tipo di sedute, intensità, durata e incertezza delle stime. Non produce una classifica: un tempo di risposta più breve o un guadagno diverso non sono, da soli, un giudizio sul livello dell'atleta.

## Come leggere i risultati

| Voce | Lettura pratica |
|---|---|
| **MAE**, in bpm | Scostamento assoluto medio. Un MAE di 5 bpm significa un errore medio di 5 battiti nei campioni confrontati; non significa che ogni punto sia entro 5 bpm. |
| **RMSE**, in bpm | Dà più peso agli errori grandi. È utile insieme al MAE per capire se alcune fasi della seduta sono particolarmente lontane dalla previsione. |
| **Bias**, in bpm | Errore medio con segno, calcolato come osservato meno previsto. Positivo: il modello tende a sottostimare HR; negativo: tende a sovrastimarla. |
| **Residuo** | Differenza tra HR osservata e prevista in ogni istante. Aiuta a localizzare errori nelle salite di intensità, nei recuperi o con il passare del tempo. |
| **Copertura della fascia** | Quota dei campioni osservati che cade entro la fascia prevista. Va letta insieme alla sua larghezza. |
| **Larghezza della fascia** | Quanto è ampio l'intervallo rappresentato. Una fascia molto larga può contenere molti dati ma essere poco utile per distinguere scenari. |

Le metriche della finestra ingrandita non sostituiscono quelle dell'intera seduta. Nella sintesi della validation ogni workout ha lo stesso peso: una seduta lunga non domina automaticamente la media delle altre.

Le fasce al 95% rappresentano una **variabilità parziale prevista dal modello**, non una garanzia che il 95% delle future misure vi cadrà. Includono la componente variabile della potenza e la variabilità dei parametri HR; non includono tutte le fonti di errore, tra cui rumore residuo HR e incertezza dei riferimenti iniziali. La loro utilità va verificata sui dati successivi.

## Preparare e importare una prescrizione

Le durate sono in **secondi**, le potenze in **watt assoluti**. I numeri seguenti illustrano il formato e non sono una proposta di allenamento per un atleta specifico.

### CSV: un blocco per riga

File UTF-8 con queste due colonne, separate da virgola:

```csv
duration_s,target_w
600,150
180,220
120,100
180,220
120,100
300,120
```

Nel CSV ogni ripetizione va scritta per esteso. L'editor e il JSON permettono invece di raggruppare le ripetizioni.

### JSON: blocchi e ripetizioni

```json
{
  "schema_version": 1,
  "name": "Esempio di seduta",
  "blocks": [
    {"duration_s": 600, "target": {"kind": "constant", "watts": 150}},
    {"repeat": 3, "blocks": [
      {"duration_s": 180, "target": {"kind": "constant", "watts": 220}},
      {"duration_s": 120, "target": {"kind": "constant", "watts": 100}}
    ]},
    {"duration_s": 300, "target": {"kind": "constant", "watts": 120}}
  ]
}
```

Per prescrivere un intervallo, il target può essere `{"kind":"range","low_w":180,"high_w":220}`. Prima di simulare bisogna scegliere esplicitamente un valore centrale, un profilo di potenza nel tempo oppure scenari distinti. **“180–220 W” non significa che l'atleta eseguirà casualmente tutte le potenze comprese nel range.**

Gli [esempi pronti](study_app/examples/) e la [guida ai formati e ai limiti](study_app/README.md#prescrizioni) completano queste indicazioni. ZWO, TCX, GPX e target espressi in percentuale della FTP non sono attualmente formati di importazione della prescrizione.

## Metodo e assunzioni

### Due passaggi collegati

```text
Prescrizione → potenza eseguita simulata → frequenza cardiaca prevista
```

Il primo passaggio rappresenta la risposta della potenza alla prescrizione con una dinamica di ordine 2 e una componente autoregressiva AR(2), che descrive la persistenza temporale degli scostamenti. È un modello ausiliario: i suoi effetti si leggono soprattutto nei grafici.

Il secondo passaggio usa un modello HR del primo ordine con ritardo, chiamato **P1D**. In parole pratiche, HR non segue istantaneamente un cambio di potenza: il modello rappresenta sia il ritardo sia la gradualità della risposta.

| Parametro | Significato nel modello |
|---|---|
| **K**, bpm/W | Ampiezza della variazione HR associata a una variazione di potenza a regime, nelle condizioni descritte dal modello. |
| **L**, secondi | Ritardo tra variazione della potenza e risposta modellata. |
| **τ (tau)**, secondi | Costante di tempo: regola la rapidità con cui la risposta si avvicina al nuovo equilibrio. |

I parametri stimati sui diversi tratti dello **stesso atleta** vengono riassunti con un modello statistico multivariato REML. “Popolazione di parametri” indica quindi la variabilità tra quei tratti, non un insieme di altri atleti usato per sostituire il suo storico. Deviazione standard tra tratti e incertezza della media sono grandezze diverse.

Per chi vuole approfondire, la dinamica HR è scritta come:

```text
tau · dx/dt + x = K · [P(t − L) − P0]
HR prevista = B + x
x(0) = HR0 − B
```

Nella previsione, `B = A + K · P0`: **A e HR0 provengono soltanto dal train**. B non viene aggiustato usando una finestra HR della validation e la misura HR iniziale della seduta da verificare non viene usata per calibrare la previsione. La frequenza cardiaca prevista alla partenza può quindi differire da quella effettiva: anche questo scostamento fa parte della verifica.

La struttura dei modelli e le impostazioni sono [congelate](study_app/scientific/frozen_config.json); i coefficienti vengono stimati sullo storico dell'atleta quando l'utente avvia l'identificazione. Una baseline statica è conservata come riferimento di confronto, ma non viene disegnata come curva nei grafici.

### Regole che rendono il confronto leggibile

| Aspetto | Regola della suite |
|---|---|
| Selezione dei dati | Regole AR storiche congelate; soglie di zona scalate rispetto alla FTP dell'atleta, con riferimento storico 325 W. Durate, tolleranze e arrotondamento dei target a 5 W restano invariati. |
| Dati non visti | La validation non partecipa alla stima. Una verifica prospettica richiede anche una previsione salvata prima dell'attività; importare oggi una vecchia seduta non la rende automaticamente un nuovo test. |
| Origine temporale | Primo avvio del timer disponibile, altrimenti primo campione; confronto sul tempo trascorso. |
| Ritardo HR | Rimane nel modello. Non si spostano le curve dopo la seduta per farle coincidere meglio. |
| Pause e gap | La previsione salvata resta invariata. Nella diagnostica con potenza reale i tratti si interrompono e ripartono dai riferimenti train, con reinizializzazioni dichiarate. |
| Cambi di blocco | Non azzerano lo stato dinamico del modello. |
| Sensori | Campioni mancanti e anomalie sono quantificati; nessuna interpolazione automatica dei casi difficili. |
| Condizioni esterne | I dati disponibili, come temperatura o cadenza, aiutano a descrivere il contesto ma non diventano implicitamente nuovi ingressi del modello. |

Questa versione studia la relazione **potenza–HR**. Non identifica automaticamente perché la frequenza cardiaca di una giornata sia diversa e non trasforma i parametri in indicatori clinici o misure dirette di fatica. La precisione osservata su un atleta o periodo non va trasferita automaticamente ad altri.

## Letteratura di riferimento

I lavori seguenti sono i riferimenti scientifici indicati nel progetto. Hanno motivato lo studio della dinamica HR–potenza, della variabilità individuale e della previsione su sedute successive. **La configurazione P1D/REML e la catena di potenza di questa suite sono scelte del progetto: non si rivendica una replica integrale dei quattro articoli.**

### Lefever, Berckmans e Aerts — dinamica HR nel ciclismo su strada

Lefever, J., Berckmans, D., & Aerts, J.-M. (2014; pubblicazione online 2012). *Time-variant modelling of heart rate responses to exercise intensity during road cycling.* European Journal of Sport Science, 14(sup1), S406–S412. [Articolo e DOI](https://doi.org/10.1080/17461391.2012.708791).

Studia strutture matematiche compatte per descrivere la risposta cardiaca durante prove su strada, confrontando complessità, ingressi e parametri costanti o variabili nel tempo. Il contributo al progetto è l'idea di partire da una dinamica semplice e verificarne l'utilità sui dati reali. Le prove ripetute dello studio non coincidono con uno storico eterogeneo di allenamenti: la trasferibilità va misurata.

### Mazzoleni e colleghi — risposta ai cambi di intensità

Mazzoleni, M. J., Battaglini, C. L., Martin, K. J., Coffman, E. M., & Mann, B. P. (2016). *Modeling and predicting heart rate dynamics across a broad range of transient exercise intensities during cycling.* Sports Engineering, 19, 117–127. [Articolo e DOI](https://doi.org/10.1007/s12283-015-0193-3); [scheda degli autori, Duke University](https://scholars.duke.edu/publication/1119769).

Propone un modello non lineare della risposta HR durante cambi di intensità e considera potenza e cadenza in prove al cicloergometro. Per questo lavoro è un riferimento sull'importanza di valutare transizioni e recuperi, oltre alle medie della seduta. La suite corrente mantiene la sola potenza come ingresso e non implementa quel modello non lineare.

### de Leeuw e colleghi — dati di campo e osservazione nel tempo

De Leeuw, A. W., Voet, J. G., van Erp, T., Lamberts, R. P., de Koning, J. J., & Knobbe, A. (2025). *Coupling heart rate and power data in professional road cycling: Shorter heart rate response indicate better 10-min time trial power output.* Journal of Sports Sciences, 43(10), 978–985. [Articolo e DOI](https://doi.org/10.1080/02640414.2025.2481533); [scheda della pubblicazione, University of Groningen](https://research.rug.nl/en/publications/coupling-heart-rate-and-power-data-in-professional-road-cycling-s/).

Analizza due anni di dati di 23 ciclisti semi-professionisti e mette in relazione tempi di risposta HR individuali e prestazioni in prove controllate. Motiva l'interesse per parametri osservati nel tempo su dati di campo. Le associazioni riportate non autorizzano a interpretare automaticamente un parametro di questa suite come misura dello stato di forma.

### Nazaret e colleghi — prevedere una nuova seduta dallo storico

Nazaret, A., Tonekaboni, S., Darnell, G., Ren, S. Y., Sapiro, G., & Miller, A. C. (2023). *Modeling personalized heart rate response to exercise and environmental factors with wearables data.* npj Digital Medicine, 6, 207. [Articolo completo](https://www.nature.com/articles/s41746-023-00926-4).

Studia la previsione personalizzata dell'andamento HR di nuove sedute usando lo storico e un modello che combina equazioni dinamiche e apprendimento automatico. È un riferimento metodologico per distinguere la previsione futura dall'adattamento ai dati già osservati. Il contesto di attività e gli ingressi differiscono dal ciclismo basato sulla potenza; la suite non ne adotta le reti neurali né le covariate ambientali.

## Dati, backup e archivio storico

Ogni atleta ha una cartella dedicata sotto `storage/athletes/`. Lo storage comprende FIT originali, revisioni dei dati, esperimenti, modelli, previsioni e confronti, con un indice SQLite. Gli originali non vengono sovrascritti; gli artefatti scientifici completati sono versionati e controllati tramite hash.

**Per un backup**, fermare il servizio e copiare l'intera cartella `storage/`, inclusa `study.sqlite3`. Per ripristinarla, lavorare a servizio fermo e usare una copia completa: il solo database o i soli JSON non bastano. `storage/` è escluso da Git, quindi un commit del codice non è un backup degli atleti.

Lo studio precedente è conservato in [`archive/`](archive/README_ARCHIVE.md), separato dall'app corrente. L'app non carica automaticamente i vecchi risultati come modelli attivi. Alcuni file storici erano collegamenti assoluti: dopo lo spostamento possono non risolversi; gli archivi ZIP di collegamenti non contengono necessariamente i FIT originali. I dati locali ignorati da Git non sono garantiti in un nuovo clone del repository.

## Problemi frequenti

| Situazione | Cosa controllare |
|---|---|
| FIT rifiutato con errore di intestazione | Verificare che sia il file originale esportato dal dispositivo. Un file chiamato `.fit` che contiene solo un percorso testuale è un collegamento, non una registrazione. |
| ZIP rifiutato | Deve contenere solo FIT e cartelle, senza link simbolici, cifratura o altri ZIP annidati. |
| Attività esclusa dall'identificazione | Leggere i motivi nello storico e nel riepilogo dell'esperimento; controllare FTP, lap e continuità dei campioni. |
| File già presente | Lo stesso contenuto viene riconosciuto come duplicato. Un contenuto diverso con la stessa data iniziale viene segnalato, senza sostituire l'originale. |
| Importazione o identificazione apparentemente ferme | Tenere aperto il terminale del servizio e controllarne i messaggi. Non chiuderlo per accelerare il lavoro; un arresto può lasciare l'operazione incompleta. |
| Simulazione troppo grande | Ridurre esplicitamente numero di traiettorie, durata o scenari secondo il messaggio. La suite non riduce di nascosto la simulazione richiesta. |
| Pagina non raggiungibile | Avviare `start.ps1` e verificare l'indirizzo e la porta indicati nel terminale. |
| Interfaccia vecchia dopo modifiche al codice | Ricompilare con `start.ps1 -Setup` e ricaricare la pagina. |

Le durate di elaborazione dipendono dal numero di campioni e dalle risorse del computer. La versione attuale non offre una stima garantita del tempo residuo. Per dettagli sui limiti di upload e simulazione vedere la [guida locale](study_app/README.md).

## Struttura del repository e verifiche

| Percorso | Contenuto |
|---|---|
| `study_app/frontend/` | Interfaccia Vue, grafici e interazioni. |
| `study_app/backend/` | Servizio Python/FastAPI, import, esperimenti e gestione degli artefatti. |
| `study_app/scientific/` | Nucleo scientifico, configurazioni congelate e provenienza. |
| `study_app/examples/` | Esempi di prescrizione CSV e JSON. |
| `study_app/tests/` | Test backend della nuova suite. |
| `storage/` | Dati operativi locali, esclusi da Git. |
| `archive/` | Studio, dati e applicativi precedenti. |
| `planning/local-study-webapp/` | Specifica, decisioni approvate e verifiche registrate. |

I test automatici della nuova suite verificano importazione, separazione cronologica, persistenza, simulazioni e confronti usando dati sintetici e parametri prefissati. Le routine di fitting sono bloccate durante questi test: **test software superati non significano modello scientificamente validato sul nuovo atleta**. La qualità predittiva si misura con gli esperimenti e con le successive sedute reali.

Per chi sviluppa, dalla radice del repository:

```powershell
.venv/Scripts/python.exe -B -m pytest study_app/tests -q -p no:cacheprovider
cd study_app/frontend
npm.cmd test
npm.cmd run build
```

Non eseguire indiscriminatamente la suite sotto `archive/`: comprende esperimenti e test storici che possono avviare fitting. La precedente baseline statica resta nei calcoli; nasconderne la curva non modifica il protocollo.

Ulteriori dettagli: [guida locale](study_app/README.md), [specifica funzionale](planning/local-study-webapp/SPEC.md), [decisioni e perimetro](planning/local-study-webapp/CONTROL.md), [verifiche della consegna iniziale](planning/local-study-webapp/VERIFICATION.md), [provenienza del nucleo](study_app/scientific/PROVENANCE.json).
