# Dataset exploration web app — design

## Obiettivo

Creare in `webapp/dataset_exploration/` una web app locale in formato SPA,
basata su Vue, per ispezionare dataset di attività ciclistiche FIT, selezionare
lap o blocchi di lap contigui, applicare normalizzazioni dichiarate ed esportare
serie temporali riproducibili.

L'applicazione è uno strumento locale di esplorazione e preparazione dei dati.
Non introduce modelli fisiologici, interpretazioni cliniche, classificazioni o
decisioni automatiche di coaching.

## Perimetro funzionale

L'applicazione deve consentire di:

1. indicare e caricare una directory locale contenente file FIT;
2. seguire directory e file raggiunti tramite collegamenti simbolici;
3. mostrare tutte le attività ammesse dal filtro di durata in una griglia;
4. visualizzare, per ogni attività, potenza e frequenza cardiaca rispetto al
   tempo trascorso da `0` alla durata dell'attività, formattato `h:mm:ss`;
5. impostare la durata massima delle attività mostrate;
6. aprire una singola attività e controllarne le serie con zoom mediante una
   finestra temporale interattiva;
7. dichiarare peso, frequenza cardiaca massima e frequenza cardiaca di soglia;
8. attivare separatamente le normalizzazioni basate su tali parametri;
9. segmentare un'attività secondo i messaggi FIT `lap`;
10. selezionare un singolo lap o unire lap contigui in un unico blocco;
11. esportare le serie temporali selezionate, non i FIT originali;
12. scrivere l'esportazione in un percorso locale dichiarato oppure, se ciò
    non è possibile, scaricare uno ZIP dal browser.

Non sono previste autenticazione, database, pubblicazione remota, ricerca,
segmentazione automatica alternativa ai lap o funzionalità ulteriori.

## Architettura

La soluzione usa due componenti locali serviti dalla stessa porta:

- una SPA Vue 3 costruita con Vite;
- un backend Python che riutilizza `fitdecode` e, quando appropriato, le
  funzioni già presenti in `src/power_hr_eda`.

Il backend serve sia le API sia gli asset compilati della SPA. Il processo si
lega a `127.0.0.1` e sceglie una porta libera all'avvio. L'indirizzo effettivo
`IP:porta` deve essere registrato nella documentazione della web app al termine
dell'implementazione.

Apache ECharts viene usato per i grafici perché supporta serie quantitative,
zoom e selezione della finestra temporale in Vue senza richiedere un secondo
sistema di visualizzazione.

## Caricamento del dataset

L'interfaccia accetta un percorso locale. Il backend:

- risolve il percorso senza modificare la sorgente;
- accetta directory reali o simboliche;
- individua i file con estensione `.fit` nelle directory previste;
- segue i collegamenti simbolici ai file;
- segnala errori di percorso, accesso o parsing senza alterare i FIT;
- conserva per ogni attività il percorso sorgente e un identificativo stabile
  derivato dal file nel dataset caricato.

Il browser non deve essere considerato responsabile della risoluzione dei
collegamenti simbolici: questa operazione appartiene al backend locale.
Il backend conserva il percorso simbolico come identificativo, ma risolve il
target reale prima di passarlo al decoder FIT. Link non risolvibili, file vuoti
e FIT non validi devono produrre motivazioni di esclusione distinguibili.

## Inventario e classificazione delle attività

Per ogni FIT il backend ricava almeno:

- identificativo dell'attività;
- percorso sorgente;
- istante iniziale e finale osservato;
- durata osservata;
- presenza e copertura di potenza e frequenza cardiaca;
- numero di record;
- numero di messaggi `lap` validi;
- eventuale errore di parsing.

La schermata principale contiene due sezioni:

1. **Attività estraibili**: attività con almeno un lap dotato di confini
   temporali utilizzabili;
2. **Esclusi dall'estrazione**: attività senza voci riconducibili ai lap o senza
   confini lap utilizzabili.

Ogni attività esclusa deve avere un'etichetta esplicita che ne indica il
motivo. Rimane visualizzabile e ispezionabile, ma non può essere selezionata per
l'estrazione. Il filtro di durata massima si applica alla visualizzazione in
entrambe le sezioni e non modifica la classificazione.

## Griglia e dettaglio

La griglia mostra una scheda per attività con:

- nome o identificativo del file;
- durata in formato `h:mm:ss`;
- grafico compatto di potenza e frequenza cardiaca;
- asse orizzontale da `0` alla durata osservata;
- numero di lap oppure etichetta di esclusione.

Il dettaglio della singola attività mostra:

- potenza e frequenza cardiaca originali;
- tempo trascorso dall'inizio dell'attività;
- confini dei lap sovrapposti al grafico;
- controllo di zoom/finestra temporale;
- elenco ordinato dei lap con numero, inizio, fine e durata;
- una partizione iniziale composta da un segmento per ciascun lap;
- selezione di uno o più segmenti della partizione;
- unione di segmenti adiacenti;
- annullamento dell'unione, con ripristino dei lap originari;
- aggiunta dei segmenti selezionati alla raccolta di esportazione.

L'unione è valida soltanto quando comprende una sequenza senza interruzioni di
lap contigui della stessa attività. Non è consentito unire lap non contigui o
appartenenti ad attività differenti.

La raccolta di esportazione può contenere più segmenti della stessa attività e
segmenti provenienti da attività differenti. I duplicati della stessa attività
e dello stesso intervallo di lap non devono essere aggiunti.

## Vista pre-esportazione

Prima dell'esportazione l'utente accede a una vista dedicata che mostra tutti i
segmenti raccolti, con attività sorgente, intervallo di lap, durata, numero di
campioni e grafico della serie temporale. Da questa vista può rimuovere singoli
segmenti ed esportare l'intera raccolta. I parametri e le opzioni di
normalizzazione sono globali, dichiarati nella schermata di caricamento e
riportati nella vista pre-esportazione.

## Assunzioni sui lap

La segmentazione iniziale usa esclusivamente i messaggi FIT `lap`. Per ogni lap:

- `start_time` definisce l'inizio;
- `timestamp` definisce la fine;
- i record sono inclusi secondo una convenzione coerente e testata, evitando
  duplicazioni ai confini tra segmenti consecutivi;
- il tempo relativo del segmento esportato riparte da zero.

Non si inferiscono lap da eventi generici, cambi di potenza o algoritmi di
change-point detection. Se i messaggi lap sono assenti o inutilizzabili,
l'attività appartiene a **Esclusi dall'estrazione**.

## Normalizzazioni

Le grandezze misurate originali rimangono sempre disponibili e non vengono
sovrascritte. Le normalizzazioni producono colonne derivate opzionali:

- `power_w_kg = power_w / weight_kg`;
- `hr_pct_max = 100 * heart_rate_bpm / hr_max_bpm`;
- `hr_pct_threshold = 100 * heart_rate_bpm / hr_threshold_bpm`.

I parametri sono dichiarati nella schermata e devono essere numerici, finiti e
strettamente positivi. Una normalizzazione con parametro mancante o non valido
non può essere applicata. Le unità sono:

- peso: kg;
- potenza originale: W;
- potenza normalizzata: W/kg;
- frequenza cardiaca originale: bpm;
- frequenza cardiaca normalizzata: percentuale del riferimento dichiarato.

Queste trasformazioni non sono interpretate come biomarcatori o stati
fisiologici.

## Formato di esportazione

Ogni esportazione produce uno ZIP. Lo ZIP contiene:

- un CSV per ogni lap o blocco selezionato;
- un `manifest.json` riferito all'intera esportazione.

Ogni CSV contiene almeno:

- identificativo dell'attività;
- indice del lap iniziale e finale;
- timestamp originale;
- tempo relativo in secondi a partire da zero;
- potenza originale in W, se disponibile;
- frequenza cardiaca originale in bpm, se disponibile;
- le sole colonne normalizzate attivate dall'utente.

Il manifest contiene almeno:

- versione del formato;
- data di creazione;
- dataset sorgente;
- file e segmenti inclusi;
- confini temporali di ogni segmento;
- definizione e unità delle colonne;
- parametri di normalizzazione dichiarati;
- formule applicate;
- indicazione esplicita delle normalizzazioni attive;
- convenzione usata per i confini dei lap e il tempo relativo.

Timestamp originali, tempo relativo, formule e parametri devono permettere di
ricostruire e interpretare le serie temporali esportate senza accedere ai FIT.
Il backend tenta di scrivere lo ZIP nel percorso locale indicato. Se il percorso
non è disponibile o il browser non può usarlo direttamente, restituisce lo ZIP
come download.

## Errori e stati dell'interfaccia

L'interfaccia deve rappresentare almeno:

- nessun dataset caricato;
- caricamento in corso;
- percorso non valido o non accessibile;
- FIT non leggibile;
- dataset senza attività;
- attività escluse dall'estrazione;
- parametri di normalizzazione non validi;
- selezione di lap non contigui;
- esportazione completata o fallita.

Gli errori di un singolo FIT non devono impedire l'inventario degli altri file.

## Verifica

La verifica deve includere:

- lettura di directory reali e simboliche;
- classificazione tra attività estraibili ed escluse;
- motivazione esplicita delle esclusioni;
- filtro sulla durata massima;
- formato `h:mm:ss` e asse temporale a partire da zero;
- validazione e calcolo delle tre normalizzazioni;
- conservazione dei valori originali;
- segmentazione ai confini dei lap senza duplicazioni;
- rifiuto dell'unione di lap non contigui;
- unione corretta di lap contigui;
- tempo relativo del segmento a partire da zero;
- coerenza tra CSV, manifest, formule, unità e parametri;
- costruzione della SPA;
- avvio su una porta libera;
- prova locale sul dataset `dataset/cleaned`;
- documentazione finale dell'indirizzo `IP:porta` effettivamente usato.

## Vincoli di riproducibilità

I FIT sorgente non vengono modificati. Le trasformazioni applicate
all'esportazione sono esplicite nel manifest. Le decisioni su formule, unità,
confini dei lap e formato di esportazione sono parte di questa specifica e
devono rimanere documentate nel repository.
