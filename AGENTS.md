# AGENTS.md

## 0. Principi operativi prioritari

Le regole di questa sezione governano il modo in cui l’agente opera nel repository e hanno priorità sulle indicazioni operative più specifiche riportate in seguito.

1. Prima di implementare qualsiasi cosa, provvedere a concordarla con l’utente.
2. Ispezionare soltanto quanto necessario per formulare una proposta informata.
3. Riutilizzare il contesto valido già acquisito, senza rileggere indiscriminatamente l’intero repository.
4. Preferire modifiche brevi, circoscritte e verificabili.
5. Proporre lo spezzettamento delle task quando ampiezza, rischio o numero di decisioni rendono difficile una verifica affidabile.
6. Non ampliare implicitamente lo scope approvato.
7. Rendere persistenti nel repository le decisioni scientifiche necessarie alla riproducibilità.

### 0.1 Approvazione prima dell’implementazione

Prima di implementare qualsiasi cosa, provvedere a concordarla con l’utente.

Per implementazione si intende qualsiasi modifica a codice, test, configurazioni, notebook, documentazione, dipendenze, dati processati o struttura del repository.

Prima dell’approvazione sono consentite le attività read-only necessarie a comprendere la richiesta: leggere i file direttamente pertinenti, effettuare ricerche mirate, controllare lo stato del repository, esaminare test e risultati esistenti e formulare ipotesi o proposte.

La proposta deve essere proporzionata alla task e indicare almeno obiettivo, scope, file o componenti presumibilmente coinvolti, approccio, assunzioni scientifiche rilevanti e verifiche previste. Per modifiche modellistiche deve inoltre rispettare i requisiti della sezione "Regole operative per l’agente di coding".

L’approvazione vale soltanto per lo scope presentato. Se emerge la necessità di ampliarlo materialmente, introdurre un altro modello o una nuova covariata, cambiare le assunzioni scientifiche o modificare componenti non previsti, fermarsi e concordare l’estensione con l’utente.

### 0.2 Preservazione e riuso del contesto

Lavorare in modo incrementale e conservare il contesto già acquisito durante la sessione. Non rileggere indiscriminatamente l’intero repository a ogni nuova richiesta o passaggio operativo.

Prima di effettuare nuove letture:

1. utilizzare le informazioni già raccolte;
2. identificare quali informazioni mancano realmente;
3. cercare prima file, simboli o riferimenti specifici;
4. leggere soltanto i file necessari a risolvere l’incertezza corrente;
5. ampliare progressivamente l’ispezione solo quando le evidenze lo giustificano.

Non ripetere inventari o analisi già completati, salvo quando i file pertinenti sono cambiati, l’utente richiede una nuova verifica, una nuova evidenza rende insufficiente l’analisi precedente oppure la correttezza richiede di ricontrollare uno specifico presupposto.

Quando si riutilizzano conclusioni precedenti, verificare che siano ancora valide per i file e lo stato corrente del repository.

### 0.3 Ispezione mirata

Adottare un’ispezione progressiva: individuare prima i file direttamente collegati alla richiesta, quindi consultare le dipendenze immediate, i test e la configurazione pertinenti. Ampliare l’analisi soltanto se emergono effetti trasversali.

Preferire ricerche mirate per nomi di file, simboli, import, configurazioni e test rispetto alla lettura sequenziale dell’intero repository.

Una scansione estesa è giustificata soltanto quando la task è realmente trasversale, l’architettura non è ancora conosciuta o occorre verificare sistematicamente un impatto globale. In tal caso, dichiararne brevemente la ragione all’utente prima di procedere.

### 0.4 Modifiche piccole e verificabili

Preferire implementazioni brevi, circoscritte e facilmente verificabili. Ogni modifica dovrebbe avere un obiettivo unico, coinvolgere il minor numero ragionevole di componenti, evitare refactoring e astrazioni non necessari, preservare il comportamento fuori scope ed essere verificabile con controlli proporzionati.

Non ampliare una task per correggere anche problemi adiacenti. Segnalare separatamente ciò che viene osservato fuori scope e lasciare all’utente la decisione se affrontarlo.

### 0.5 Suddivisione delle task troppo ampie

Se una richiesta comprende più obiettivi, molte decisioni scientifiche, modifiche trasversali o una quantità di lavoro che rende difficile verificare il risultato, proporre di suddividerla in passaggi più piccoli.

Ogni passaggio deve essere autonomamente comprensibile, verificabile, scientificamente interpretabile, ordinato secondo le dipendenze e utile anche se i passaggi successivi non vengono eseguiti. Indicare per ogni passaggio risultato atteso, confini, dipendenze, criterio di completamento e decisioni richieste prima del passaggio successivo.

Quando possibile, completare e verificare un passaggio prima di proporre l’implementazione del successivo. Non frammentare artificialmente una modifica semplice, locale e a basso rischio.

### 0.6 Proporzionalità e persistenza

Il livello di analisi, documentazione e verifica deve essere proporzionato all’impatto della modifica. Una correzione locale richiede una proposta e una verifica brevi; un nuovo modello, una trasformazione dei dati o una modifica al protocollo sperimentale richiedono una proposta scientifica completa.

Non affidare esclusivamente alla conversazione le decisioni necessarie alla riproducibilità. Quando una decisione approvata influenza stabilmente dati, modelli, validazione o interpretazione dei risultati, registrarla nel documento, nella configurazione o nell’artefatto progettuale appropriato, senza creare documentazione di stato ridondante.

## 1. Scopo del progetto

Questo repository studia se la risposta della frequenza cardiaca di un ciclista alla potenza meccanica possa essere modellata come un sistema dinamico ingresso-uscita utilizzando dati reali di ciclismo.

La domanda di ricerca iniziale è:

> Dato lo storico individuale sincronizzato di potenza e frequenza cardiaca di un atleta, è possibile costruire un modello dinamico capace di prevedere la traiettoria della frequenza cardiaca in sessioni o intervalli ciclistici non ancora osservati?

L’obiettivo iniziale NON è costruire un prodotto commerciale, classificare lo stato di forma dell’atleta, diagnosticare fatica o scoprire nuova fisiologia dell’esercizio.

Il primo obiettivo è verificare se approcci già pubblicati di modellazione dinamica della relazione frequenza cardiaca-potenza possano essere riprodotti e trasferiti a dati ciclistici reali, rumorosi ed eterogenei di un singolo atleta.

---

## 2. Formulazione del sistema

Considerare la potenza ciclistica come ingresso esterno principale:

P(t)

e la frequenza cardiaca come uscita osservata principale:

HR(t)

Il problema generale di modellazione è:

P(t) -> M_i -> HR_hat(t)

dove M_i è un modello dinamico specifico dell’atleta, identificato sui suoi dati storici.

In fasi successive il modello potrà includere covariate aggiuntive osservabili:

M_i(P(t), cadenza(t), temperatura(t), quota(t), ...)

ma ulteriori ingressi non devono essere introdotti senza evidenza che il modello basato sulla sola potenza sia insufficiente.

Il modello potrà eventualmente contenere:

* una dinamica veloce, associata alla risposta della frequenza cardiaca alle variazioni di carico;
* una dinamica lenta, associata alla variazione nel tempo della relazione potenza-frequenza cardiaca durante esercizio prolungato.

Non assumere che la componente lenta rappresenti fisiologicamente la fatica.

Inizialmente essa deve essere trattata soltanto come stato matematico latente o componente tempo-variante.

---

## 3. Posizionamento scientifico

Il progetto è un progetto di analisi quantitativa applicata.

Occorre distinguere sempre tra:

1. grandezze misurate;
2. stati matematici del modello;
3. parametri stimati;
4. interpretazioni fisiologiche;
5. decisioni eventualmente supportate per il coach.

Non trasformare un parametro matematico in una grandezza fisiologica senza evidenza esplicita.

In particolare:

stato lento del modello != fatica

parametro del modello != biomarcatore fisiologico

buon fitting != buona capacità predittiva

parametri diversi tra sessioni != cambiamento dello stato di forma

---
## 4. Letteratura di riferimento principale

L’implementazione deve partire, quando possibile, da modelli già pubblicati prima di proporre nuove architetture.

### R1 — Lefever, Berckmans & Aerts

"Time-variant modelling of heart rate responses to exercise intensity during road cycling."

European Journal of Sport Science.

DOI:
https://doi.org/10.1080/17461391.2012.708791

Rilevanza:

* ciclismo;
* dati su strada;
* modellazione dinamica power -> HR;
* strutture compatte;
* confronto tra modelli time-invariant e time-varying;
* baseline utile per system identification.

Limite importante per questo progetto:

L’esperimento utilizzava prove stradali ripetute da 27 km e una piccola coorte relativamente controllata. I dati di questo repository possono contenere una variabilità molto maggiore di allenamento, terreno, intensità e ambiente.

### R2 — Mazzoleni et al.

"Modeling and predicting heart rate dynamics across a broad range of transient exercise intensities during cycling."

DOI:
https://doi.org/10.1007/s12283-015-0193-3

Rilevanza:

* ciclismo;
* variazioni transitorie del carico;
* modellazione dinamica individuale della frequenza cardiaca;
* riferimento utile per la cinetica veloce della risposta cardiaca;
* formulazioni non lineari.

Limite importante:

Campione ridotto e protocollo controllato su cicloergometro.

### R3 — de Leeuw et al.

"Coupling heart rate and power data in professional road cycling: Shorter heart rate response indicate better 10-min time trial power output."

Journal of Sports Sciences, 2025.

DOI:
https://doi.org/10.1080/02640414.2025.2481533

Rilevanza:

* dati reali di campo;
* 23 ciclisti semi-professionisti;
* due anni di osservazioni;
* parametri individuali della risposta HR-power;
* analisi longitudinale dei parametri;
* relazione tra parametri della risposta HR-power e performance ciclistica.

Questo lavoro è particolarmente rilevante per il passaggio da condizioni controllate a dati storici eterogenei raccolti sul campo.

### R4 — Nazaret et al.

"Modeling personalized heart rate response to exercise and environmental factors with wearables data."

npj Digital Medicine, 2023.

DOI:
https://doi.org/10.1038/s41746-023-00926-4

Rilevanza:

* modello personalizzato;
* previsione prospettica della frequenza cardiaca in workout non osservati;
* modello fisiologico basato su ODE;
* rappresentazione individuale derivata dallo storico;
* covariate ambientali;
* problema della generalizzazione e della predizione individuale.

Limite importante:

Il dataset riguarda corsa outdoor e non ciclismo, e non utilizza la potenza ciclistica come ingresso meccanico.

Deve essere considerato un riferimento metodologico, non una prova diretta che lo stesso livello di prestazione sia ottenibile nel ciclismo.

---

## 5. Strategia di sviluppo

Procedere sempre da modelli semplici a modelli più complessi.

NON iniziare con:

* reti neurali;
* transformer;
* modelli state-space complessi;
* Gaussian Process;
* modelli non lineari arbitrari.

Ogni modello più complesso deve essere confrontato con baseline più semplici.

### Gerarchia dei modelli

Valutare almeno progressivamente:

### M0 — Baseline statica

Esempio:

HR(t) = beta0 + beta1 * P(t)

È deliberatamente semplice e serve come limite inferiore di riferimento.

### M1 — Modello dinamico del primo ordine

Forma concettuale:

tau * dHR/dt + HR = HR0 + K * P(t)

Può essere eventualmente stimato anche un ritardo temporale.

### M2 — Modello dinamico di ordine superiore

Da introdurre soltanto se giustificato dalla capacità predittiva fuori campione.

### M3 — Modello tempo-variante / con componente lenta

Da introdurre solo dopo aver mostrato una struttura sistematica dei residui incompatibile con M1/M2.

### M4 — Modello non lineare o ibrido

Da introdurre solo dopo una valutazione documentata dei modelli più semplici.

Le equazioni specifiche devono preferibilmente replicare o adattare modelli pubblicati prima di introdurre nuove strutture.

---

## 6. Primo obiettivo sperimentale

Il primo esperimento NON è:

"costruire il miglior predittore possibile della frequenza cardiaca."

È:

> Determinare se semplici modelli dinamici HR-power presenti in letteratura rimangano identificabili, ripetibili e utili dal punto di vista predittivo quando vengono adattati ai dati ciclistici reali di Andrea.

L’esperimento deve testare tre ipotesi.

### H1 — Predicibilità

La potenza contiene informazione sufficiente per prevedere una quota significativa della dinamica della frequenza cardiaca in dati non osservati.

### H2 — Ripetibilità dei parametri

I parametri stimati su sottoinsiemi comparabili dei dati dello stesso atleta sono sufficientemente stabili da poter essere considerati caratteristiche dinamiche individuali.

### H3 — Valore della complessità

Modelli dinamici più sofisticati producono un miglioramento sostanziale fuori campione rispetto a baseline semplici.

Il fallimento di una qualsiasi di queste ipotesi è un risultato informativo.

Non ottimizzare l’analisi per forzarne il successo.

---

## 7. Principi sui dati

I dati raw non devono mai essere sovrascritti.

Mantenere almeno:

data/raw/
data/interim/
data/processed/

Privilegiare trasformazioni completamente riproducibili.

Ogni workout processato dovrebbe preservare:

* identificativo workout;
* timestamp;
* tempo trascorso;
* potenza;
* frequenza cardiaca;
* cadenza, se disponibile;
* velocità, se disponibile;
* quota, se disponibile;
* temperatura, se disponibile;
* coordinate GPS soltanto se realmente necessarie;
* file sorgente;
* metadati di preprocessing.

Non interpolare né filtrare i dati in modo implicito.

Ogni trasformazione deve essere esplicitamente registrata.

---

## 8. Controlli di qualità dei dati

Prima di stimare qualsiasi modello, verificare:

* frequenza di campionamento;
* sincronizzazione tra HR e potenza;
* campioni mancanti;
* periodi a potenza zero;
* dropout del cardiofrequenzimetro;
* dropout del misuratore di potenza;
* salti implausibili della frequenza cardiaca;
* pause;
* coasting;
* gap di registrazione;
* differenze di sampling tra dispositivi;
* warm-up e cool-down;
* durata della sessione;
* distribuzione dei valori di potenza;
* durata dei periodi a potenza approssimativamente costante.

Non eliminare automaticamente le anomalie.

Prima segnalarle e quantificarle.

---

## 9. Suddivisione del dataset

È vietato utilizzare split casuali dei singoli campioni temporali.

Campioni adiacenti dello stesso segmento non devono comparire contemporaneamente in training e test.

Preferire i seguenti livelli di validazione.

### Livello 1 — Holdout degli intervalli

Stimare il modello su alcuni intervalli strutturati e prevedere intervalli non utilizzati della stessa sessione.

### Livello 2 — Holdout della sessione

Stimare il modello su sessioni complete e prevedere una sessione completamente non osservata.

### Livello 3 — Holdout temporale

Stimare il modello su un periodo precedente e prevedere sessioni di un periodo successivo.

La validazione principale dovrà progressivamente spostarsi verso Livello 2 o Livello 3.

---

## 10. Metriche di valutazione

Riportare sempre l’errore predittivo su dati non utilizzati nel fitting.

Metriche candidate:

* MAE in bpm;
* RMSE in bpm;
* bias;
* deviazione standard dei residui;
* correlazione solo come informazione supplementare;
* errore in funzione dell’orizzonte predittivo;
* errore in funzione della potenza/intensità;
* errore durante le transizioni in salita;
* errore durante il recupero;
* errore durante segmenti a potenza approssimativamente costante;
* errore in funzione della durata della sessione.

La correlazione da sola non è mai una metrica sufficiente.

Produrre grafici di:

HR_misurata(t)

HR_predetta(t)

residuo(t)

per sessioni rappresentative.

---

## 11. Analisi dei parametri

Per ogni parametro stimato riportare, quando possibile:

* valore stimato;
* unità;
* incertezza;
* intervallo di confidenza o credibilità, quando appropriato;
* sensibilità al preprocessing;
* variabilità test-retest;
* dipendenza dalla selezione dei workout.

Non interpretare fisiologicamente un parametro senza supporto della letteratura.

Un parametro è utile soltanto se è sufficientemente identificabile e ripetibile.

---

## 12. Dinamica veloce e lenta

Non imporre inizialmente un’architettura fast/slow soltanto perché è concettualmente plausibile.

Procedere prima in questo modo:

1. stimare modelli dinamici semplici derivati dalla letteratura;
2. analizzare sistematicamente i residui;
3. verificare se i residui dipendono dal tempo trascorso dall’inizio dell’esercizio;
4. verificare se la relazione HR-power cambia sistematicamente durante la sessione;
5. confrontare formulazioni time-invariant e time-varying.

Solo successivamente valutare uno stato lento esplicito.

Se viene introdotto uno stato lento, verificare che migliori la capacità predittiva fuori campione e non soltanto il fitting in-sample.

---

## 13. Variabilità dei dati reali

Una delle domande principali del repository è verificare se modelli sviluppati in condizioni controllate o semi-controllate si trasferiscano a dati eterogenei di campo.

Pertanto non eliminare la variabilità reale soltanto per migliorare il fitting.

Occorre invece quantificarla.

Possibili covariate:

* cadenza;
* temperatura ambientale;
* quota;
* pendenza;
* durata;
* lavoro accumulato;
* carico di allenamento del giorno precedente;
* proxy di idratazione o fueling, se realmente disponibili.

Queste rappresentano analisi secondarie.

Il modello power-only deve rimanere la baseline di riferimento.

---

## 14. Riproducibilità

Tutte le analisi devono essere riproducibili tramite codice.

Struttura preferita:

src/
notebooks/
tests/
reports/
references/

I notebook sono ammessi per l’esplorazione.

Il codice riutilizzabile per preprocessing, fitting dei modelli e valutazione deve progressivamente essere spostato in `src/`.

Non lasciare logiche critiche esclusivamente nei notebook.

Usare random seed fissi quando è richiesta casualità.

Separare configurazione e codice dei modelli.

---

## 15. Primi deliverable attesi

Il primo ciclo di sviluppo dovrebbe produrre:

1. inventario dei dati;
2. report sulla qualità dei dati;
3. identificazione di workout e intervalli candidati;
4. implementazione di almeno una baseline dinamica derivata dalla letteratura;
5. baseline statica;
6. confronto fuori campione;
7. grafici HR predetta vs HR misurata;
8. diagnostica dei residui;
9. prima valutazione della ripetibilità dei parametri;
10. breve report tecnico che dichiari cosa ha funzionato, cosa non ha funzionato e cosa rimane non identificato.

Non è richiesto alcun dashboard o applicativo user-facing.

---

## 16. Regole operative per l’agente di coding

Prima di implementare un nuovo modello:

1. dichiarare il modello matematico;
2. identificare la fonte bibliografica oppure dichiarare esplicitamente che si tratta di una nuova proposta;
3. dichiarare le assunzioni;
4. indicare gli input richiesti;
5. indicare, quando possibile, le unità dei parametri;
6. dichiarare il metodo di fitting;
7. definire la strategia di validazione;
8. definire la baseline più semplice che il nuovo modello deve superare.

Quando i requisiti sono ambigui, preferire analisi esplorativa e assunzioni documentate piuttosto che introdurre implicitamente forti scelte modellistiche.

Non ottimizzare prematuramente l’architettura software.

Nelle prime fasi, tracciabilità scientifica e riproducibilità sono più importanti della sofisticazione software.

---

## 17. Condizioni di arresto

Segnalare esplicitamente se l’evidenza suggerisce che:

* la frequenza cardiaca non è prevedibile in misura sufficiente dalla sola potenza;
* le stime dei parametri sono instabili;
* combinazioni di parametri molto diverse producono predizioni praticamente equivalenti;
* l’aumento di complessità migliora il training fit ma non la previsione sul test;
* il modello fallisce su workout non osservati;
* le prestazioni degradano fortemente all’aumentare della durata della sessione;
* il modello dipende in modo critico da covariate non disponibili.

Questi risultati sono validi e non devono essere nascosti introducendo ulteriore complessità.

---

## 18. Perimetro attuale

Perimetro attuale:

singolo atleta
+
ciclismo
+
potenza
+
frequenza cardiaca
+
dati storici di allenamento reale
+
identificazione di sistemi dinamici
+
predizione fuori campione

Fuori perimetro nella prima iterazione:

* classificazione degli atleti a livello di popolazione;
* diagnosi di fatica;
* interpretazione medica;
* decisioni automatiche di coaching;
* prescrizione ottimale dell’allenamento;
* software commerciale;
* deep learning, salvo fallimento dimostrato degli approcci più semplici;
* rivendicazioni di nuova conoscenza fisiologica.
