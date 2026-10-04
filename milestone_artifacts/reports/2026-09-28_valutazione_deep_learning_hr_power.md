# Valutazione del deep learning per la dinamica HR–Power

Data: 28 settembre 2026  
Stato: osservazioni preliminari per discussione; nessun modello DL implementato o addestrato.

## Sintesi della valutazione

Il deep learning merita una prova controllata, soprattutto mediante una piccola
GRU o LSTM. Al momento non emerge una ragione sperimentale per sostituire il P1D
con un Transformer o un'architettura più complessa.

Il beneficio potenziale consiste nell'apprendere uno stato dinamico dalla storia
precedente al lap, senza imporre l'equilibrio iniziale che si è rivelato
problematico in diversi segmenti. Una rete non può però recuperare automaticamente
una storia che non riceve: azzerarne lo stato a ogni lap e fornire solo pochi
campioni precedenti potrebbe riproporre il problema attuale.

Questa è una valutazione di opportunità, non un risultato comparativo. Non è
ancora dimostrato che una rete generalizzi meglio di un modello dinamico semplice
con un'inizializzazione appropriata.

## Problema da affrontare

L'analisi delle due run P1D full più recenti ha verificato che i campioni del lap
con tempo t >= 0 entrano nel fit. Il plateau iniziale non deriva da un taglio
accidentale del transitorio nel percorso CSV → fit → risultati salvati.

Con le condizioni attuali:

```text
tau dx/dt + x = K [P(t-L) - P0]
HR_pred = HR0 + x
x(0) = 0
P(t<0) = P0
```

la previsione resta HR0 fino a L. Nei dati, invece, la HR può essere già in discesa
prima del lap e continuare a scendere dopo un aumento della potenza. La media dei
dieci secondi precedenti non garantisce che quel periodo sia di equilibrio.

Una rete con memoria potrebbe rappresentare tale comportamento se ricevesse
informazioni sufficienti per inizializzare lo stato. Questo non implica che sia
l'unica soluzione: occorre distinguere il limite della specifica inizializzazione
dal fallimento dell'intera classe dei modelli semplici.

È emerso anche un problema numerico distinto: in un segmento, una ricerca più
ampia sugli stessi parametri e bounds ha ridotto la SSE da 3615,75 a 3220,27
rispetto agli otto start della run. Il miglioramento non elimina il limite
strutturale sulla discesa iniziale. Non va attribuito alla maggiore complessità
del modello ciò che potrebbe dipendere da una migliore ottimizzazione.

Run considerate:

- `fb739aa964c348bea4ab0c629cd3fc67` — Dataset importato, creata il 28/09/2026 alle 16:17:30 UTC.
- `b5cf1b76b3bc4ea7bb9923025d85620c` — Extended_G1_UtD, creata il 28/09/2026 alle 16:15:55 UTC.

I relativi manifest e risultati sono nello storage locale della web app; lo
storage non è versionato in Git.

## Dati disponibili nelle run esaminate

| Dataset | Segmenti | Attività distinte | Durata sommata dei segmenti | Attività train / validation / test |
|---|---:|---:|---:|---:|
| Esteso G1/G2 | 215 | 17 | 28.289 s, circa 7,9 h | 12 / 2 / 3 |
| Sottoinsieme G1–UtD | 56 | 7 | 3.177 s, circa 53 min | 5 / 1 / 1 |

Gli split sono per attività, senza attività condivise tra train e validation/test.
Il secondo dataset è un sottoinsieme: le numerosità non devono essere sommate.
La somma delle durate non costituisce una misura del tempo unico disponibile,
poiché eventuali sovrapposizioni tra segmenti non sono state deduplicate in questo
conteggio. La tabella riguarda i dataset delle run, non un inventario completo
dello storico FIT del repository.

La quantità è compatibile con una prova esplorativa di un modello piccolo, ma non
consente di presumere una generalizzazione affidabile. Generare molte finestre
dagli stessi allenamenti aumenta gli esempi numerici, non il numero di attività
indipendenti. Tre attività test, o una nel sottoinsieme, danno una valutazione
limitata della variabilità tra sessioni.

Prima di decidere la fattibilità complessiva, occorre considerare lo storico
completo e la disponibilità di sequenze continue precedenti ai lap.

## Architetture candidate

| Architettura | Interesse per HR–Power | Valutazione per il primo esperimento |
|---|---|---|
| RNN semplice | Introduce uno stato ricorrente | Preferire una variante con porte, GRU o LSTM |
| GRU / LSTM compatta | Aggiorna uno stato nel tempo; può elaborare sessioni continue | Prima candidata, con capacità contenuta |
| TCN causale | Usa una finestra esplicita di storia tramite convoluzioni temporali | Buon confronto con la GRU |
| Transformer | Mette in relazione campioni distanti mediante attenzione | Complessità non ancora giustificata dai risultati del progetto |
| SSM neurali, ad esempio Mamba | Elaborano sequenze lunghe tramite stato e meccanismi selettivi | Da considerare se la lunghezza delle sequenze diventa un limite concreto |
| Modello ibrido ODE + rete | Mantiene una dinamica esplicita e apprende alcune componenti | Coerente con il progetto, ma richiede ulteriori decisioni modellistiche |

Gli studi originali su GRU/LSTM e TCN ne supportano l'uso come candidati per
sequenze, ma non stabiliscono quale architettura sia migliore per questi dati.
I risultati dei Transformer o di Mamba in altre applicazioni non costituiscono
una validazione della relazione HR–Power nel ciclismo.

### Evidenza pertinente e limiti di trasferibilità

Nazaret et al. combinano ODE e componenti neurali per prevedere la HR in workout
futuri usando lo storico precedente. Il lavoro usa 270.707 sessioni di corsa di
7.465 persone. È un riferimento metodologico utile per inizializzazione,
personalizzazione e previsione su nuove sessioni, ma differisce dal nostro caso:
ciclismo, potenza meccanica come ingresso e singolo atleta.

Non si può trasferire automaticamente né la prestazione riportata né la
sufficienza statistica del loro dataset al repository attuale.

## Esperimento candidato, da concordare prima dell'implementazione

1. **Un unico modello individuale.** Addestrare la rete sulle sessioni train
   dell'atleta; non stimare nuovi pesi per ogni lap test. Congelare i pesi prima
   della valutazione.
2. **Inizializzazione dalla storia.** Confrontare i dieci secondi attuali con un
   contesto più lungo o con elaborazione continua della sessione. La durata del
   contesto è una scelta da validare, non una costante fisiologica assunta.
3. **Definizione degli ingressi disponibili.** Dichiarare se la HR precedente al
   lap è ammessa per inizializzare lo stato. Questo sarebbe un protocollo
   condizionato a misure HR iniziali, non una previsione dalla sola potenza senza
   alcuna informazione HR della sessione.
4. **Previsione della traiettoria.** Nel segmento test, usare la potenza e lo
   stato iniziale senza fornire continuamente la HR osservata. L'aggiornamento
   con HR osservata a ogni passo costituisce un diverso problema di previsione
   o stima online e deve essere valutato separatamente. La potenza del segmento
   è un ingresso noto: prevedere una sessione futura senza conoscerla sarebbe
   ancora un altro problema.
5. **Confronto a parità di informazione.** Baseline e rete devono avere accesso
   alle stesse informazioni iniziali. Dare alla rete una lunga storia e al P1D
   soltanto due medie confonderebbe il beneficio dell'architettura con quello
   degli ingressi disponibili.
6. **Baseline semplici.** Includere almeno una baseline statica, una baseline di
   persistenza della HR iniziale e un modello dinamico semplice. Il P1D attuale
   rimane un riferimento, ma superarlo non basta a dimostrare che serva il DL,
   dato il limite già identificato nell'inizializzazione.
7. **Validazione per attività e temporale.** Escludere intere attività dal
   training; non distribuire casualmente campioni o finestre della stessa
   sessione tra train e test. Scegliere architettura, contesto e iperparametri
   senza usare il test. Valutare una strategia temporale e/o più partizioni per
   attività, compatibilmente con la numerosità disponibile.
8. **Stabilità del risultato.** Usare più seed, capacità contenuta e controlli
   dell'overfitting. Normalizzazione e ogni preprocessing appreso devono essere
   determinati sul train e applicati invariati agli altri set. Nessuna
   interpolazione o gestione dei gap implicita.

### Metriche e criterio di utilità

Riportare RMSE e MAE in bpm, bias, R2 e amplitude ratio, sia per attività sia in
aggregato. Separare l'errore nei primi secondi, nelle transizioni e nei recuperi;
controllare anche la struttura dei residui. Il confronto deve coprire traiettorie
complete, non soltanto predizioni del campione successivo assistite dalla HR
osservata.

Il criterio di successo dovrebbe essere un miglioramento fuori campione stabile
tra sessioni e seed, non solo una curva di training più aderente. L'entità minima
utile del miglioramento e la modalità di aggregazione vanno definite prima del
confronto finale. Non è stata fissata una soglia in questa valutazione.

## Cosa cambierebbe nella domanda scientifica

Una GRU compatta sarebbe soprattutto un esperimento sulla **predicibilità** della
traiettoria, quindi sull'ipotesi H1. Un risultato positivo indicherebbe che le
informazioni fornite contengono una dinamica apprendibile nelle condizioni di
validazione adottate.

I pesi della rete non sostituiscono direttamente K, L e tau. Un buon risultato
predittivo non dimostra identificabilità o ripetibilità di parametri individuali
(H2), né attribuisce significato fisiologico allo stato nascosto. In particolare,
uno stato neurale non va interpretato automaticamente come fatica o stato di forma.

Per H3, il beneficio della complessità deve essere dimostrato rispetto a baseline
semplici valutate correttamente e con informazioni comparabili.

## Raccomandazione e questioni aperte

La prima candidata è una **GRU compatta**, con TCN causale come eventuale confronto.
La prova dovrebbe essere separata dall'identificazione parametrica esistente e
non sostituire automaticamente la pipeline. Non emerge ancora una motivazione
sufficiente per iniziare da Transformer, Mamba o da un modello ibrido complesso.

Prima di implementare occorre concordare:

- se l'obiettivo primario è la previsione da potenza con inizializzazione HR,
  oppure la previsione senza HR osservata della nuova sessione;
- quale storia precedente è disponibile e utilizzabile in modo riproducibile;
- quale insieme di attività complete usare e quale validazione temporale adottare;
- quali baseline garantiscono un confronto equo;
- quali miglioramenti fuori campione giustificherebbero la maggiore complessità.

## Riferimenti consultati

1. Chung et al. (2014), *Empirical Evaluation of Gated Recurrent Neural Networks
   on Sequence Modeling*. [arXiv:1412.3555](https://arxiv.org/abs/1412.3555).
2. Bai, Kolter e Koltun (2018), *An Empirical Evaluation of Generic Convolutional
   and Recurrent Networks for Sequence Modeling*.
   [arXiv:1803.01271](https://arxiv.org/abs/1803.01271).
3. Vaswani et al. (2017), *Attention Is All You Need*.
   [arXiv:1706.03762](https://arxiv.org/abs/1706.03762).
4. Gu e Dao (2023; revisione 2024), *Mamba: Linear-Time Sequence Modeling with
   Selective State Spaces*. [arXiv:2312.00752](https://arxiv.org/abs/2312.00752).
5. Nazaret et al. (2023), *Modeling personalized heart rate response to exercise
   and environmental factors with wearables data*, npj Digital Medicine.
   [DOI:10.1038/s41746-023-00926-4](https://www.nature.com/articles/s41746-023-00926-4).

Le raccomandazioni per questo repository sono valutazioni progettuali basate sui
dati esaminati e sui riferimenti, non conclusioni sperimentali ottenute addestrando
queste architetture nel progetto.
