# Come siamo arrivati allo studio attuale

Questo progetto nasce da una domanda pratica: quanto della risposta cardiaca di
Andrea durante il ciclismo si può ricostruire e anticipare conoscendo la potenza?
Il lavoro ha trasformato uno storico di allenamenti in un percorso ripetibile di
preparazione, identificazione e valutazione. La milestone del **4 ottobre 2026**
riguarda questo insieme di strumenti e risultati, non soltanto un'equazione.

## Prima del modello: rendere leggibili i dati

La prima conquista è stata capire che cosa contenessero davvero le registrazioni.
Le uscite su strada hanno pause, tratti a potenza zero, interruzioni, campioni
mancanti e lap molto diversi. Trattare tutto come una serie uniforme avrebbe
nascosto parte del problema. L'esplorazione ha permesso di vedere i segnali,
riconoscere intervalli utilizzabili e conservare il legame con i file originali.

Da qui è nata l'app per esplorare FIT e ZIP, selezionare o unire lap ed esportare
segmenti con un manifest. Medie mobili e normalizzazioni sono diventate scelte
esplicite, con gli originali conservati. Il risultato utile è un dataset che si
può controllare e ricostruire, insieme a una conoscenza concreta dei suoi limiti.

## Seguire una transizione non significa aver identificato tutto

I primi esperimenti hanno usato un modello dinamico compatto del primo ordine,
con guadagno, costante di tempo ed eventuale ritardo: la famiglia P1D. La struttura
si inserisce nella letteratura HR–intensità; inizializzazione, stima e trattamento
dei dati sono adattamenti del progetto, non una replica integrale di uno studio.

Su transitori brevi il modello poteva seguire bene la curva cardiaca, ma valori
molto diversi di guadagno e costante di tempo potevano produrre quasi la stessa
traiettoria. Le analisi dei gruppi brevi e lunghi hanno reso visibile questa
distinzione: un errore piccolo non basta a dire che i parametri siano ben separati.
Per i transitori brevi è stata resa disponibile anche un'approssimazione che stima
il loro rapporto, senza fingere di recuperarli indipendentemente.

Questo ha cambiato il modo di lavorare: alla curva sovrapposta si sono affiancati
residui, incertezza locale, limiti dei parametri e confronto tra inizializzazioni
del solver. L'app conserva queste informazioni con le impostazioni dell'esperimento.

## Allargare il problema a tratti più lunghi e variabili

Il passo successivo è stato estendere il fitting oltre le singole transizioni,
verso sequenze più lunghe e attività complete, con recuperi e cambi di carico.
È una generalizzazione del campo di applicazione del fitting: la capacità di
trasferire i parametri a un'altra uscita richiede una verifica separata.

L'equilibrio iniziale stimato ha dato al modello un modo esplicito per gestire
segmenti che non cominciano già in equilibrio con la potenza. Questo livello,
indicato con B, è un parametro matematico riferito alla potenza iniziale; non è
una misura della frequenza cardiaca a riposo.

Il passaggio alle attività reali ha chiarito anche il peso delle interruzioni.
Il dataset delle run attuali deriva da 131 attività: conserva 357 segmenti di
almeno cinque minuti, appartenenti a 130 attività, interrompendo le serie ai gap
superiori a dieci secondi. Mantiene circa il 98,09% dei campioni sorgente.
I valori mancanti restano segnalati e non vengono riempiti in questo percorso.
Lo split tiene insieme tutti i segmenti di una stessa attività.

Il vantaggio dei tratti più lunghi è osservare una parte maggiore della risposta;
la difficoltà è rappresentare una relazione HR–potenza che non resta identica in
ogni situazione. Residui e fit falliti rimangono quindi parte del risultato.

## Dal fitting alla previsione: partire dal livello giusto

Per trasferire l'informazione dal train al test è stata aggiunta la stima dei
parametri condivisi tra segmenti dello stesso atleta, tenendo conto anche della
loro incertezza locale. La pagina si chiama **Parametri atleta**: la “popolazione”
qui è quella dei segmenti di Andrea, non un campione di ciclisti.

Le prime predizioni hanno mostrato che il livello cardiaco iniziale poteva pesare
molto sull'errore. Nel confronto esplorativo archiviato, estendere la calibrazione
di B da 10 a 180 secondi ha ridotto la mediana dell'RMSE da **25,70 a 7,12 bpm**.
Il confronto riguardava gli stessi 53 segmenti di 21 attività e gli stessi campioni
successivi a 180 secondi: 46 segmenti miglioravano, sei peggioravano e uno restava
invariato. Otto casi senza predizione restavano esclusi dal confronto.

Il miglioramento riguardava soprattutto l'allineamento del livello. Ha motivato
l'opzione di calibrazione a tre minuti, senza un nuovo stato dinamico o un ingresso
aggiuntivo. È stata una scelta esplorativa su dati già ispezionati: non prova che
tre minuti siano sempre ottimali. Nella procedura attuale, dopo questa finestra B
resta costante; la HR successiva serve a valutare la previsione, non a correggerla.

## Che cosa abbiamo oggi

La run completa conservata, **`b4ac2e82`**, usa lo split per attività con seed 52.
Dei 250 segmenti train, 219 hanno un fit riuscito e 31 falliscono; lo screening
mantiene 218 vettori per stimare i parametri condivisi. Il modello resta del primo
ordine: in questa configurazione il ritardo è fissato a zero, non stimato nullo
dai dati. Il guadagno medio è circa **0,296 bpm/W**, la costante di tempo media
circa **52,4 s**: descrittori del modello, non indici di forma fisica.

Con calibrazione locale di 180 secondi si ottengono **57 predizioni su 65 segmenti
test**, relative a **24 attività**. Sulla parte successiva alla calibrazione,
la mediana dell'RMSE è **7,24 bpm** e quella del MAE **5,99 bpm**. Sono mediane
tra segmenti riusciti, non un errore uniforme su ogni uscita. Gli otto fallimenti
restano visibili. In 56 dei 57 casi l'RMSE migliora rispetto alla baseline costante
pari al B utilizzato: è un riferimento semplice, che non sostituisce un confronto
con una regressione statica potenza–HR o con tutte le alternative possibili.

In pratica, il pacchetto consente di prendere uno storico, stimare una risposta
individuale e simulare l'andamento cardiaco di segmenti non usati nel fitting,
conoscendone la potenza e osservandone i primi tre minuti di HR. Consente anche
di riconoscere dove la ricostruzione non regge, invece di nasconderlo in una sola
misura media. Non è ancora una previsione dell'intera uscita a partire dalla sola
potenza, senza informazioni cardiache iniziali.

La run **`8dc6d46a`**, seed 60, era in corso allo snapshot e ha poi completato
l'identificazione durante il riordino: **211 fit riusciti su 239, con 28 fallimenti**.
Ripete il lavoro con un diverso split dello stesso insieme di dati. Il confronto
delle analisi servirà a controllare quanto il risultato dipenda dalla separazione
train/test; qui non ne anticipiamo una conclusione. Non è una conferma su un nuovo
atleta o un periodo mai osservato. Restano da chiarire la stabilità tra periodi,
la sensibilità alla scelta delle uscite e le situazioni in cui il modello perde
accuratezza, soprattutto lungo esercizi prolungati.

## Per atleti e coach: il valore è il pacchetto di lavoro

Uno studio condotto così può aiutare atleta e coach a leggere lo storico con
maggiore continuità. Il primo ritorno è spesso sui dati: sapere quali uscite
sono confrontabili, dove la registrazione è incompleta e quanto un'apparente
differenza dipenda dal tratto selezionato o dalle condizioni di partenza.

Il modello aggiunge un riferimento individuale con cui confrontare la risposta
cardiaca osservata a un certo andamento di potenza. Grafici ed errori possono
evidenziare tratti che meritano una revisione: per esempio una risposta che resta
più alta del previsto, un recupero descritto male o una differenza che compare
soltanto nella parte finale. Sono punti da discutere insieme al contesto dell'uscita,
non diagnosi automatiche di fatica, idratazione o stato di forma.

Il lavoro utile da consegnare comprende dati controllati, criteri di selezione,
analisi individuale, confronti su uscite riservate, casi rappresentativi e una
restituzione comprensibile di ciò che funziona e di ciò che resta incerto.
Ripetere lo stesso percorso su periodi successivi può rendere più ordinato il
confronto; attribuire significato alle variazioni richiede prima di verificarne
la ripetibilità. Le scelte di allenamento rimangono affidate ad atleta e coach.

**Il prodotto è questo pacchetto di lavoro.** L'equazione da sola non porta con sé
né la qualità dei dati, né la verifica dei risultati, né la loro interpretazione.
Le due app rendono il percorso utilizzabile e documentabile; lo studio ne misura
l'utilità concreta sul caso individuale.

## Dove ritrovare le evidenze

Gli aggregati attuali e gli hash delle sorgenti sono in
[reports/current_study/summary.json](reports/current_study/summary.json), rigenerabile
con [scripts/summarize_current_study.py](scripts/summarize_current_study.py).
Le decisioni di calibrazione e previsione sono nel
[protocollo dell'app](webapp/model_identification_app/POPULATION_PROTOCOL.md).

La branch `milestone/2026-10-04-hr-power`, commit `c95496e`, conserva codice e
artefatti precedenti alla pulizia. In `milestone_artifacts/` si trovano l'esplorazione
iniziale, i report G1/G2, le run storiche disponibili e
`reports/P1D_first_full_dataset_run/B_calibration_comparison/`, con codice, metriche
e assunzioni del confronto 10–180 secondi. L'inventario contiene gli hash delle copie.
Il README precedente, conservato nello stesso commit, raccoglie il quadro
bibliografico e i dettagli dei primi esperimenti.
