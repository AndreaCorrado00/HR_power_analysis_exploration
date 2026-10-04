# Specifica della Fase 0: esplorazione dei dati FIT

## Obiettivo

Produrre una descrizione riproducibile e scientificamente prudente dei dati
ciclistici disponibili, con particolare attenzione a disponibilita, qualita,
campionamento e sincronizzazione dei segnali di potenza e frequenza cardiaca.

La Fase 0 deve stabilire quali informazioni siano effettivamente contenute nei
file FIT e quali problemi possano condizionare la successiva identificazione di
modelli dinamici HR-power. Non deve stimare modelli e non deve suddividere il
dataset in training, validation e test.

## Perimetro

Sorgente dei dati:

- collegamento simbolico `dataset/raw/only_road_activities/`;
- 169 file FIT osservati al 19 settembre 2026;
- intervallo nominale ricavato dai nomi dei file: maggio 2025 - 19 settembre
  2026;
- i file FIT raw non saranno modificati.

Artefatti della Fase 0:

- report finale in formato PDF dentro `exploration/`;
- immagini del report dentro `exploration/images/`, escluse dal versionamento;
- codice riproducibile necessario a estrazione, controlli e grafici dentro
  `exploration/`;
- tabelle intermedie o riepilogative, se necessarie alla riproducibilita,
  dentro `exploration/`.

Il PDF sara il report destinato alla lettura. Eventuali file tecnici ausiliari
non costituiranno report alternativi.

## Vincoli scientifici

1. Nessuna analisi o metrica che richieda sorgenti esterne ai FIT.
2. Nessuna analisi o metrica che richieda parametri soggettivi o personali non
   osservati direttamente nei FIT, per esempio FTP, HR massima assunta, HR a
   riposo, soglie o zone definite dall'utente.
3. Nessuno split in training, validation e test in questa fase.
4. Nessuna interpolazione, correzione, filtraggio o rimozione implicita di
   campioni.
5. Le anomalie saranno quantificate e mostrate, non eliminate automaticamente.
6. Le soglie diagnostiche necessarie a produrre conteggi saranno dichiarate e
   accompagnate, quando possibile, da statistiche continue che consentano di
   valutarne la sensibilita.
7. La sincronizzazione HR-power sara studiata descrittivamente; non sara
   applicata alcuna correzione automatica del ritardo.

## Unita di analisi

L'EDA operera su due livelli distinti:

1. **Sessione:** un file FIT e i relativi metadati, riepiloghi e indicatori di
   completezza.
2. **Record temporale:** sequenza originale dei campioni, con timestamp e campi
   effettivamente registrati.

Le statistiche aggregate saranno presentate sia pesando i campioni sia
riassumendo le sessioni, per evitare che le attivita piu lunghe nascondano la
variabilita tra workout.

## Analisi previste

### 1. Inventario e struttura dei FIT

- leggibilita di ogni file e diagnostica degli errori;
- tipi di messaggi FIT presenti;
- campi effettivamente disponibili, unita e copertura;
- timestamp iniziale e finale;
- durata elapsed, timer e altre durate esplicitamente registrate;
- numero di record, lap ed eventi;
- informazioni su dispositivo e sensori, soltanto se contenute nei FIT;
- duplicati esatti o potenziali sovrapposizioni temporali;
- registrazioni multiple ravvicinate nella stessa giornata.

Output attesi:

- catalogo delle attivita;
- matrice sessione per variabile;
- riepilogo della copertura temporale e mensile;
- elenco dei campi realmente utilizzabili.

### 2. Numerosita e tempo di allenamento

- numero di sessioni e record;
- ore cumulative;
- distribuzione della durata per sessione;
- volume di registrazione per settimana e mese;
- confronto tra elapsed time e timer time;
- tempo per cui HR e potenza sono entrambe osservate;
- pause ed eventi registrati;
- frammentazione delle attivita.

Non sara introdotta una definizione arbitraria di `moving time`. Sara riportato
solo se presente nel FIT o se derivabile con una regola oggettiva e documentata
interamente dai campi registrati; in caso contrario verra omesso.

### 3. Campionamento e continuita temporale

Per ogni sessione e segnale:

- distribuzione degli intervalli tra timestamp consecutivi;
- mediana, percentili e massimo di `delta t`;
- quota di campioni alle frequenze osservate;
- gap temporali a diverse durate descrittive;
- timestamp duplicati, non monotoni o sovrapposti;
- relazione tra gap ed eventi di pausa, quando disponibile;
- evidenza di campionamento regolare o smart recording.

Non saranno effettuati resampling o interpolazione.

### 4. Qualita di potenza e frequenza cardiaca

Per entrambi i segnali:

- presenza per sessione e copertura temporale;
- campioni mancanti e sequenze consecutive di assenza;
- valori zero;
- distribuzione, percentili ed estremi;
- salti tra campioni consecutivi;
- valori costanti per periodi prolungati;
- dropout brevi e prolungati;
- valori rari o estremi da sottoporre a ispezione.

Per la potenza saranno distinti, quando i dati lo consentono, coasting e
possibili dropout senza assumere automaticamente che ogni zero sia anomalo.
Per HR saranno evidenziati assenza iniziale del segnale, plateau, salti e
dropout. Eventuali limiti diagnostici non saranno presentati come soglie
fisiologiche individuali.

### 5. Sincronizzazione HR-power

- disponibilita simultanea dei segnali;
- visualizzazione delle tracce nelle sessioni rappresentative;
- comportamento di HR in corrispondenza delle variazioni di potenza;
- cross-correlazione esplorativa su un intervallo di lag dichiarato;
- distribuzione e stabilita del lag apparente tra sessioni;
- confronto qualitativo tra fasi di aumento e riduzione del carico;
- segnalazione delle sessioni in cui il lag non e identificabile.

La cross-correlazione sara interpretata come diagnostica descrittiva. Non sara
usata da sola per attribuire un disallineamento strumentale, perche la dinamica
fisiologica, l'autocorrelazione e il profilo del percorso possono produrre un
lag apparente.

### 6. Distribuzioni dei campi osservati

Per potenza, HR e per ogni altro parametro effettivamente presente:

- percentili e range per sessione;
- distribuzione aggregata pesata per tempo;
- distribuzione delle statistiche tra sessioni;
- andamento nel calendario;
- esempi di tracce temporali;
- relazioni descrittive tra potenza e HR;
- relazione descrittiva con tempo trascorso e durata della sessione.

Per la potenza saranno inoltre descritti il tempo a zero e la persistenza dei
livelli osservati, senza imporre una definizione soggettiva di intervallo
strutturato.

### 7. Metriche derivate ammesse

Saranno considerate soltanto metriche calcolabili integralmente dai campi FIT
presenti e tramite formule documentate, per esempio:

- distanza e durate registrate;
- dislivello positivo, se l'altitudine e disponibile, con metodo dichiarato;
- velocita media e massima;
- potenza media e massima;
- lavoro meccanico in kJ;
- HR media e massima osservata;
- cadenza media e massima;
- tempo con potenza zero;
- statistiche descrittive delle fasi a potenza relativamente stabile, solo se
  la regola operativa e oggettiva e dichiarata.

Sono escluse, tra le altre:

- zone di potenza o HR;
- Intensity Factor e TSS;
- TRIMP e varianti;
- metriche basate su FTP, HR massima teorica o osservata assunta come massima
  individuale, HR a riposo, soglie personali o valutazioni del coach;
- stime di fatica, forma, recupero, fueling o idratazione;
- metriche proprietarie non riproducibili dai dati e dalle formule disponibili.

Metriche piu elaborate ma calcolabili dai soli FIT, come normalized power,
variability index o decoupling, non sono incluse automaticamente. Potranno
essere valutate in una fase separata solo se risultano necessarie e dopo una
specifica approvazione.

## Struttura prevista del report PDF

1. Guida alla lettura e principali limitazioni.
2. Provenienza, perimetro e struttura dei dati.
3. Numerosita e copertura temporale.
4. Disponibilita dei campi.
5. Durata e volume delle sessioni.
6. Campionamento, gap, pause e continuita.
7. Qualita della potenza.
8. Qualita della frequenza cardiaca.
9. Sincronizzazione e lag apparente HR-power.
10. Distribuzioni di tutti i parametri osservati.
11. Metriche oggettive derivate dai FIT.
12. Sessioni rappresentative e casi problematici.
13. Implicazioni per la successiva modellazione, senza proporre split.
14. Limiti descrittivi dell'EDA e dati non determinabili dai FIT.

Ogni risultato dovra indicare il denominatore pertinente: sessioni, record,
secondi osservati o durata coperta. Le figure dovranno essere leggibili senza
consultare il codice e distinguere chiaramente dati misurati, valori derivati e
indicatori diagnostici.

Il report non conterra una sezione di conclusioni. Le descrizioni saranno
limitate a cio che e direttamente sostenuto dai dati, senza inferenze causali o
fisiologiche. Il testo corrente sara giustificato; titoli, didascalie e immagini
saranno impaginati in modo da evitare sovrapposizioni, tagli o dimensioni non
leggibili.

## Criteri di completamento

La Fase 0 sara completata quando:

- tutti i FIT saranno stati inventariati o esplicitamente segnalati come non
  leggibili;
- copertura, campionamento e qualita di potenza e HR saranno quantificati;
- saranno disponibili diagnostiche sulla sincronizzazione senza correzioni
  implicite;
- tutti i campi osservati rilevanti saranno descritti;
- formule e criteri diagnostici saranno riproducibili;
- il PDF sara stato renderizzato e verificato visivamente;
- nessuno split o modello sara stato stimato;
- nessun dato raw sara stato modificato.

## Verifica prevista

- controllo automatico che i file raw non siano stati scritti;
- riconciliazione tra numero di FIT, righe del catalogo e sessioni nel report;
- controlli di coerenza su timestamp, durate e conteggi;
- esecuzione ripetibile dell'analisi a partire dai FIT;
- verifica visuale di tutte le pagine del PDF, incluse tabelle, legende,
  risoluzione delle figure e assenza di contenuti tagliati.
