# Potenza e frequenza cardiaca — diario di ricerca

Questo repository raccoglie una ricerca sulla relazione dinamica tra potenza e frequenza cardiaca negli allenamenti reali di ciclismo di Andrea. La domanda di partenza è semplice: conoscendo la potenza erogata nel tempo, quanto possiamo prevedere della risposta cardiaca dello stesso atleta in allenamenti non ancora osservati?

Il percorso raccontato qui arriva alla prima analisi estesa del modello P1D. È una tappa di identificazione e comprensione del sistema: la previsione fuori campione resta un obiettivo da verificare.

## 1. Partire dai dati reali

Il primo passo è stato conoscere lo storico degli allenamenti: disponibilità di potenza e frequenza cardiaca, continuità delle registrazioni, campioni mancanti, pause e possibili anomalie. Prima di cercare una relazione matematica, occorreva capire quali caratteristiche dei segnali potessero condizionarne la stima.

L'esplorazione è stata impostata sui dati effettivamente registrati, senza assumere soglie fisiologiche personali o attribuire automaticamente i ritardi osservati a un disallineamento dei sensori. La frequenza cardiaca, infatti, risponde al carico con una propria dinamica. Questa fase è raccolta nel [report esplorativo dei dati](exploration/phase_0_eda_report.pdf).

## 2. Osservare i transitori

L'attenzione si è poi concentrata su segmenti nei quali osservare come la frequenza cardiaca accompagna le variazioni di potenza. Il campione esplorato comprendeva 215 segmenti, separati empiricamente per durata in **G1, più brevi**, e **G2, più lunghi**, con una soglia di 144,5 secondi.

Una seconda lettura distingueva le risposte prevalentemente in discesa (UtD), quelle in salita (DtU) e i casi ambigui: rispettivamente 123, 2 e 90 segmenti. Si trattava di criteri descrittivi, utili per confrontare le forme delle curve e orientare la revisione visiva, senza attribuire ai gruppi un significato fisiologico. Le [tavole dei segmenti e i criteri di raggruppamento](reports/segment_groups_G1_G2/README.md) documentano questo passaggio.

## 3. Provare una dinamica semplice: il P1D

Per una prima descrizione della risposta cardiaca è stato adottato un modello del primo ordine con ritardo, il **P1D**. L'idea è che una variazione di potenza produca una risposta cardiaca ritardata e graduale, anziché istantanea.

Il modello descrive questa risposta attraverso un guadagno **K**, che regola l'ampiezza della variazione, un ritardo **L** e una costante di tempo **τ**, che ne regola la velocità. Nelle run analizzate compare anche **B**, il livello di equilibrio matematico alla potenza di riferimento: non coincide necessariamente con la frequenza cardiaca a riposo.

La stima sui segmenti è stata accompagnata da tre domande: quanto bene viene ricostruita la curva? Quanto sono determinati i parametri? Che cosa rimane nei residui, cioè nella differenza tra frequenza cardiaca osservata e ricostruita? Questa fase riguarda il fitting; validation e test non sono stati usati per dimostrare capacità predittiva.

## 4. Un buon fit non basta

La prima analisi estesa ha confrontato quattro insiemi: G1 Ambigui, G1 UtD, G2 Ambigui e G2 UtD. Nei segmenti brevi G1 la ricostruzione era spesso molto accurata: l'RMSE mediana era circa **0,70 bpm** negli ambigui e **1,22 bpm** negli UtD. Eppure combinazioni anche molto diverse di K, τ e B potevano produrre curve quasi equivalenti.

Il limite emerso riguarda la porzione di risposta osservata. Nei G1, dopo il ritardo, il segmento copriva tipicamente solo circa **0,3 costanti di tempo**: troppo poco per separare bene il guadagno dalla velocità della risposta. La correlazione stimata tra K e τ era infatti quasi unitaria. Una curva ben ricostruita non garantiva quindi parametri affidabili.

Nei G2 si osservavano invece circa **cinque costanti di tempo**. L'errore di fit era maggiore — RMSE mediana di **2,14 bpm** negli ambigui e **2,59 bpm** negli UtD — ma l'identificabilità e la precisione locale dei parametri miglioravano nettamente. Il vantaggio dei segmenti lunghi era soprattutto la maggiore informazione sulla dinamica del sistema.

## 5. Dove siamo arrivati

Anche nei G2, dove i parametri risultavano meglio determinati, i residui mantenevano una forte struttura temporale. Il P1D catturava dunque una parte importante della risposta cardiaca, lasciando dinamica non spiegata.

Questa prima tappa ha mostrato l'utilità di una baseline semplice e l'importanza di osservare sequenze sufficientemente lunghe, preservando la memoria tra fasi successive. Ha anche chiarito due limiti: la precisione locale dei parametri non dimostra ancora la loro ripetibilità tra allenamenti, e la bontà del fit non dimostra la previsione su sessioni nuove. I risultati non bastano inoltre a stabilire che una rete ricorrente sia necessaria o superiore ai modelli più semplici.

Numeri, diagnostiche e casi da rivedere sono raccolti nel [report di analisi delle run P1D](reports/P1D_first_full_dataset_run/Report_analisi_run_modello_P1D.md), che costituisce il punto di arrivo di questo diario.
