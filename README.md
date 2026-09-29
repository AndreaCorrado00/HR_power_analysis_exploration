# Identificazione della dinamica potenza–frequenza cardiaca nel ciclismo

Studio quantitativo su dati storici di un singolo atleta (Andrea), finalizzato a verificare se modelli dinamici compatti possano descrivere e prevedere la frequenza cardiaca a partire dalla potenza meccanica durante allenamenti reali.

**Stato al 29 settembre 2026:** implementati il modello del primo ordine con ritardo (P1D), una variante con equilibrio stimato e un'approssimazione per transitori brevi. Completata una prima analisi di fitting e identificabilità sui segmenti; predisposto un dataset di attività complete. **La capacità predittiva fuori campione e la ripetibilità tra sessioni non sono ancora dimostrate.**

## 1. Domanda di ricerca e perimetro

Il sistema osservato ha come ingresso la potenza $P(t)$, in watt, e come uscita la frequenza cardiaca $HR(t)$, in bpm. L'obiettivo prospettico è identificare sullo storico un modello individuale capace di simulare $\widehat{HR}(t)$ in sessioni non utilizzate nella stima, data la traiettoria di potenza e un protocollo esplicito di inizializzazione.

Le ipotesi da verificare sono:

- **H1 — Predicibilità:** la sola potenza contiene informazione utile per prevedere la dinamica HR fuori campione.
- **H2 — Ripetibilità:** parametri stimati su sottoinsiemi comparabili dello stesso atleta sono sufficientemente stabili.
- **H3 — Valore della complessità:** strutture più articolate migliorano sostanzialmente la previsione rispetto a baseline semplici.

Nell'esperimento attuale i parametri sono stimati **separatamente su ogni segmento train**: non è ancora identificato un unico modello trasferibile tra allenamenti. Qualità della ricostruzione, identificabilità dei parametri e generalizzazione sono quindi risultati distinti.

Il perimetro rimane power-only. Parametri e stati del modello non sono biomarcatori; un'eventuale componente lenta non è identificata con la fatica. Diagnosi, prescrizione dell'allenamento e inferenze sullo stato di forma non sono obiettivi di questa fase.

## 2. Fondamento bibliografico

La scelta di una struttura semplice si colloca nella letteratura sull'identificazione ingresso–uscita della risposta cardiaca. [Hunt e Wang (2024)](https://doi.org/10.12688/f1000research.153397.2) considerano esplicitamente strutture con poli, zeri e ritardo, evidenziando anche l'effetto di transitori iniziali e preprocessing. I lavori [2, 3] forniscono confronti sperimentali tra strutture dinamiche e modalità di esercizio.

**Il codice attuale è un adattamento definito dal protocollo del progetto, non una replica integrale di uno di questi studi.** Inizializzazione, gestione dei dati di campo, bounds e procedura numerica sono scelte specifiche, documentate sotto e nel [protocollo dell'app di identificazione](webapp/model_identification_app/README.md). Le prestazioni pubblicate su protocolli controllati non costituiscono una stima delle prestazioni attese sui dati di Andrea.

| Fonte | Contributo al quadro scientifico | Limite di trasferibilità |
| --- | --- | --- |
| [1 — Hunt & Wang, 2024](https://doi.org/10.12688/f1000research.153397.2) | Confronto tra primo/secondo ordine, zeri e ritardo; riferimento diretto per la famiglia P1D e il trattamento dei transitori. | Test controllati su treadmill e cicloergometro; preprocessing e condizioni iniziali differiscono dal progetto. |
| [2 — Spörri et al., 2022](https://doi.org/10.3389/fcteg.2022.894180) | Confronto tra primo e secondo ordine su cicloergometro, con dati separati di stima e validazione. | Eccitazione sperimentale e obiettivo anche di controllo in retroazione; non dimostra il vantaggio del secondo ordine su allenamenti di campo. |
| [3 — Hunt et al., 2019](https://doi.org/10.1371/journal.pone.0220826) | Identificazione di guadagno e costante di tempo con modelli del primo ordine per cicloergometro e treadmill. | Segnali detrendizzati e variazioni controllate intorno a un livello di esercizio; non una validazione su sessioni eterogenee. |
| [4 — Zakynthinaki, 2015](https://doi.org/10.1371/journal.pone.0118263) | Riferimento per formulazioni della cinetica HR mediante equazioni differenziali accoppiate. | Struttura diversa dal P1D; le interpretazioni fisiologiche proposte nell'articolo non vengono trasferite ai parametri del repository. |
| [5 — Bearden & Moffatt, 2001](https://doi.org/10.1152/jappl.2001.90.6.2081) | Cinetica di consumo di ossigeno e HR in transizioni ciclistiche da una baseline già attiva. | Contesto fisiologico controllato; non fornisce da solo una validazione del nostro modello power-only. |
| [6 — Nascimento et al., 2022, online 2021](https://doi.org/10.1080/17461391.2021.1938689) | Fitting esponenziale del primo ordine della fase fondamentale di HR e variabilità cardiaca in diversi domini di intensità. | HR e HRV sono grandezze distinte; il progetto modella HR, non gli indici HRV né i relativi meccanismi. |

## 3. Modello matematico implementato

### 3.1 Primo ordine con ritardo — P1D

Definendo l'ingresso incrementale $u(t)=P(t)-P_0$, la funzione di trasferimento della risposta forzata, a stato iniziale nullo, è:

$$
G(s)=\frac{X(s)}{U(s)}=\frac{K e^{-Ls}}{\tau s+1}.
$$

La modalità `equilibrium` implementa:

$$
\tau\frac{dx(t)}{dt}+x(t)=K\,[P(t-L)-P_0],
\qquad \widehat{HR}(t)=HR_0+x(t),
\qquad x(0)=0.
$$

| Simbolo | Definizione operativa | Unità |
| --- | --- | --- |
| $P_0$ | Potenza di riferimento, fissata prima del fitting | W |
| $HR_0$ | Frequenza cardiaca di riferimento, fissata prima del fitting | bpm |
| $x(t)$ | Stato matematico: scostamento dell'uscita dal riferimento | bpm |
| $K>0$ | Guadagno statico incrementale | bpm/W |
| $\tau>0$ | Costante di tempo | s |
| $L\geq0$ | Ritardo puro dell'ingresso | s |

Senza pre-window si usano $P_0=P(0)$ e $HR_0=HR(0)$. Con pre-window opzionale, i riferimenti sono le medie aritmetiche dei campioni disponibili nei 10 secondi precedenti $t=0$. Questi campioni non entrano nell'obiettivo di fitting né nelle metriche. L'equilibrio iniziale è **assunto**, senza verifica automatica della stazionarietà.

Per $t<0$ il modello assume $P(t)=P_0$: la traiettoria precedente misurata non viene propagata nello stato. $HR_0$ non rappresenta necessariamente la frequenza cardiaca a riposo; $L$ non identifica automaticamente un disallineamento dei sensori.

### 3.2 Variante con equilibrio stimato

La modalità `estimated_equilibrium`, disponibile per il P1D completo, mantiene la stessa dinamica ma stima anche il livello $B$:

$$
\tau\dot{x}(t)+x(t)=K\,[P(t-L)-P_0],
\qquad \widehat{HR}(t)=B+x(t),
\qquad x(0)=HR(0)-B.
$$

Equivalentemente, per $t\geq0$:

$$
\widehat{HR}(t)=B+[HR(0)-B]e^{-t/\tau}
+\frac{K}{\tau}\int_0^t e^{-(t-v)/\tau}[P(v-L)-P_0]\,dv.
$$

$B$ è l'equilibrio matematico a $P_0$, in bpm, non una misura di HR a riposo. I parametri liberi sono $(K,L,\tau,B)$; $HR(0)$ è fissata al primo campione del segmento. La pre-window, se attivata, determina soltanto $P_0$. Il termine libero permette un rilassamento esponenziale anche prima che agisca l'ingresso ritardato, ma può introdurre compensazioni tra $B$, $K$ e $\tau$.

### 3.3 Approssimazione short-transient

La struttura alternativa `short_transient` implementa:

$$
\dot{x}(t)=\gamma[P(t-L)-P_0],
\qquad \widehat{HR}(t)=HR_0+x(t),
\qquad x(0)=0,\qquad \gamma=\frac{K}{\tau}.
$$

Stima soltanto $\gamma$, in bpm/(W·s), e $L$. È un'approssimazione della risposta forzata del P1D su tempi brevi rispetto a $\tau$, con inizializzazione in equilibrio; non recupera separatamente $K$ e $\tau$ e non rappresenta il raggiungimento di un plateau. La scelta della struttura è esplicita, non automatizzata in base alla durata del segmento.

### 3.4 Assunzioni di simulazione

I parametri sono costanti all'interno di ciascun fit. La potenza è mantenuta costante tra campioni consecutivi (*zero-order hold*); l'integrazione della risposta è esatta sotto questa convenzione, anche con campionamento irregolare e ritardo frazionario. Durante un gap il valore precedente di potenza rimane applicato: è un'assunzione sul segnale non osservato, non una sua ricostruzione verificata.

Il fitting non introduce automaticamente smoothing, interpolazione o detrending. Può usare colonne originali oppure medie mobili già presenti, con scelta registrata nella run. L'eventuale imputazione del dataset di attività complete è una trasformazione separata, descritta nella sezione 5.

## 4. Identificazione, incertezza e diagnostica

Per ogni segmento train si minimizza la somma dei quadrati dei residui:

$$
\widehat{\theta}=\operatorname*{arg\,min}_{\theta\in\Theta}
\sum_{i=1}^{N}e_i(\theta)^2,
\qquad e_i=HR(t_i)-\widehat{HR}(t_i;\theta).
$$

Il solver è `scipy.optimize.least_squares`, metodo trust-region reflective, loss lineare, Jacobiano numerico a tre punti. La ricerca usa multistart riproducibile; per le nuove run P1D la strategia predefinita aggiunge una griglia in $(L,\tau)$, risolve il sottoproblema lineare vincolato in $K$ (e $B$, quando stimato), quindi raffina i candidati. Vince la SSE minima; non è garantito il minimo globale.

I bounds predefiniti sono $K\in[10^{-6},5]$ bpm/W, $\tau\in[0{,}01,1800]$ s e $L\in[0,T]$, con $T$ durata del segmento. Sono vincoli numerici modificabili, non intervalli fisiologici. È possibile fissare $L=0$; i bounds di $B$ devono essere scelti esplicitamente. Configurazioni e limiti effettivi sono conservati nei manifest.

Le diagnostiche comprendono RMSE, MAE, bias, deviazione standard e ACF dei residui, $R^2$ come misura supplementare, parametri ai bounds, accordo tra start, rango e condizionamento del Jacobiano. I lag dell'ACF sono in campioni, non necessariamente in secondi.

L'incertezza è approssimata localmente mediante:

$$
\widehat{\operatorname{Cov}}(\widehat{\theta})
\simeq \frac{\mathrm{SSE}}{N-p}(J^\top J)^{-1},
\qquad CI_{95\%}\simeq\widehat{\theta}\pm1{,}96\,SE.
$$

Qui $p$ è il numero di parametri liberi; il calcolo usa una SVD e non dichiara queste incertezze quando il rango è insufficiente. Gli intervalli non correggono autocorrelazione, errore sulla potenza o incertezza dei riferimenti iniziali e non sono troncati ai bounds. Con $B$ stimato il residuo iniziale è nullo per costruzione. Intervalli stretti non certificano ripetibilità né accuratezza fisiologica.

## 5. Dati e stato sperimentale

### Esplorazione e selezione dei segmenti

La prima fase ha esaminato continuità, sampling, dati mancanti, pause, potenza zero e sincronizzazione: [report EDA](exploration/phase_0_eda_report.pdf). La successiva analisi descrittiva comprende **215 segmenti**, suddivisi empiricamente in G1 e G2 alla soglia di **144,5 s**. Le classi sono UtD (123), DtU (2) e ambigui (90); criteri e tavole sono nel [report dei raggruppamenti](reports/segment_groups_G1_G2/README.md). Queste etichette descrivono i segnali e non identificano categorie fisiologiche.

### Prima analisi delle run P1D

La tabella riprende il [report delle quattro run](reports/P1D_first_full_dataset_run/Report_analisi_run_modello_P1D.md), che include l'analisi di $B$. Le numerosità si riferiscono ai fit riportati, non all'intero inventario dei 215 segmenti. **Tutte le metriche seguenti sono in-sample.**

| Gruppo | n | RMSE mediana (bpm) | $R^2$ mediano | ACF1 mediana | $\rho$ mediana | Correlazione locale $K,\tau$ mediana |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 ambigui | 81 | 0,70 | 0,965 | 0,699 | 0,284 | 0,9992 |
| G1 UtD | 34 | 1,22 | 0,955 | 0,822 | 0,331 | 0,9993 |
| G2 ambigui | 7 | 2,14 | 0,959 | 0,940 | 5,70 | 0,562 |
| G2 UtD | 49 | 2,59 | 0,961 | 0,959 | 4,91 | 0,907 |

La diagnostica $\rho=(T-L)/\tau$ quantifica la durata osservata dopo il ritardo in unità di costante di tempo. Nei G1, $\rho\ll1$ e correlazioni locali quasi unitarie indicano difficoltà nel separare guadagno e costante di tempo: per tempi brevi, $1-e^{-t/\tau}\simeq t/\tau$. La correlazione riportata deriva dalla covarianza locale del fit, non da un confronto longitudinale tra sessioni.

Nei G2 il report rileva maggiore identificabilità e precisione locale, pur con RMSE più alte. L'ACF elevata evidenzia struttura temporale residua: può riflettere dinamica omessa, inizializzazione, preprocessing o caratteristiche degli errori, e non identifica da sola un meccanismo fisiologico. Il confronto tra gruppi diversi non isola causalmente l'effetto della durata e non dimostra la necessità di un modello specifico più complesso.

### Preparazione delle attività complete

Il [protocollo di rifinitura del 29 settembre 2026](references/dataset_refinement_protocol.md) documenta un passaggio distinto: esclusione delle attività con gap temporali maggiori di 10 s, tagli delle code con dati mancanti secondo regole fissate e imputazione locale riproducibile di potenza/HR. I FIT e l'export originale sono preservati.

Il [riepilogo di verifica](reports/dataset_refinement/verification.json) riporta 131 attività sorgente, 92 escluse e **39 conservate**, di cui 27 modificate e 16 tagliate; sono state inserite 91 righe e imputati 423 valori di potenza e 178 di HR. Le trasformazioni conservano provenienza e flag dei valori sintetici. L'imputazione non garantisce la preservazione della correlazione P–HR; i valori sintetici **non devono essere trattati come ground truth** nella valutazione predittiva. Questo passaggio non comprende nuovi fit né una valutazione fuori campione.

### Stato delle ipotesi e validazione da completare

| Obiettivo | Evidenza disponibile | Verifica ancora necessaria |
| --- | --- | --- |
| H1 — Predicibilità | Ricostruzione dei segmenti utilizzati nella stima | Predizione su intervalli/sessioni esclusi dal fitting e confronto con baseline statica |
| H2 — Ripetibilità | Diagnostiche locali di identificabilità e incertezza | Stabilità test-retest, sensibilità al preprocessing e alla selezione delle sessioni |
| H3 — Valore della complessità | P1D e short-transient disponibili nel software | Confronti fuori campione tra baseline e strutture, a parità di dati e protocollo |

L'app conserva split train/validation/test, ma attualmente esegue il fitting soltanto sul train e non valuta i set riservati. La baseline statica $\widehat{HR}(t)=\beta_0+\beta_1P(t)$ resta da includere nel confronto sperimentale.

La validazione prevista procede da holdout di intervalli non sovrapposti a holdout di sessioni e temporale, senza split casuali dei singoli campioni. Dovrà fissare parametri e scelte sul training, dichiarare l'informazione HR ammessa per inizializzare il test e riportare almeno MAE, RMSE e bias sui soli dati osservati, con diagnostica per transizioni, recuperi e durata. Modelli di ordine superiore, componenti lente o nuove covariate richiedono una decisione successiva supportata dai risultati.

## 6. Implementazione e riproducibilità

| Componente | Contenuto |
| --- | --- |
| [Esplorazione dati](webapp/dataset_exploration/README.md) | Interfaccia locale per ispezione e preparazione dei segmenti |
| [Identificazione HR–Power](webapp/model_identification_app/README.md) | Avvio, contratto dati, split, configurazione, export e protocollo completo |
| [Modello P1D](webapp/model_identification_app/backend/models/p1d.py) | Simulazione, fitting e diagnostiche |
| [Ricerca profilata](webapp/model_identification_app/backend/models/profile_search.py) | Griglia e selezione dei candidati da raffinare |
| [Rifinitura attività](scripts/refine_activities.py) | Trasformazione riproducibile del dataset di attività complete |

Ogni run conserva split, seed, colonne utilizzate, condizioni iniziali, bounds, impostazioni del solver, hash dei dati, snapshot del codice e versioni dell'ambiente. Per riprodurre una run servono anche i dati identificati dagli hash; il solo manifest non basta. Gli artefatti locali possono non essere distribuiti con il repository.

Le istruzioni di avvio e verifica restano nei README delle applicazioni. I risultati storici devono essere interpretati con il manifest della rispettiva run: l'attuale configurazione predefinita non viene attribuita retroattivamente a esperimenti precedenti.

## 7. Riferimenti

1. **Hunt, K. J., & Wang, H. (2024).** *Identification of heart rate dynamics during treadmill and cycle ergometer exercise: the role of model zeros and dead time.* F1000Research, 13:894, versione 2. [DOI: 10.12688/f1000research.153397.2](https://doi.org/10.12688/f1000research.153397.2).
2. **Spörri, A. H., Wang, H., & Hunt, K. J. (2022).** *Heart Rate Dynamics Identification and Control in Cycle Ergometer Exercise: Comparison of First- and Second-Order Performance.* Frontiers in Control Engineering, 3:894180. [DOI: 10.3389/fcteg.2022.894180](https://doi.org/10.3389/fcteg.2022.894180).
3. **Hunt, K. J., Grunder, R., & Zahnd, A. (2019).** *Identification and comparison of heart-rate dynamics during cycle ergometer and treadmill exercise.* PLOS ONE, 14(8):e0220826. [DOI: 10.1371/journal.pone.0220826](https://doi.org/10.1371/journal.pone.0220826).
4. **Zakynthinaki, M. S. (2015).** *Modelling Heart Rate Kinetics.* PLOS ONE, 10(4):e0118263. [DOI: 10.1371/journal.pone.0118263](https://doi.org/10.1371/journal.pone.0118263).
5. **Bearden, S. E., & Moffatt, R. J. (2001).** *V̇O₂ and heart rate kinetics in cycling: transitions from an elevated baseline.* Journal of Applied Physiology, 90(6):2081–2087. [DOI: 10.1152/jappl.2001.90.6.2081](https://doi.org/10.1152/jappl.2001.90.6.2081).
6. **Nascimento, E. M. F., et al. (2022; pubblicazione online 2021).** *Heart rate variability kinetics during different intensity domains of cycling exercise in healthy subjects.* European Journal of Sport Science, 22(8):1231–1239. [DOI: 10.1080/17461391.2021.1938689](https://doi.org/10.1080/17461391.2021.1938689).
