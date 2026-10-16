# Decomposizione della potenza: risposta dinamica e residuo stocastico

## Obiettivo e dataset

Separare la potenza osservata nelle componenti:

\[
P_{\mathrm{real},t}=P_{\mathrm{prescritta},t}+r_t+e_t,
\]

dove il target è disponibile nel dataset, \(r_t\) descrive la risposta transitoria ai cambi di target ed \(e_t\) è il residuo da modellare successivamente mediante AR.

Si userà il dataset `data/processed/prescribed_workouts_final/`, con **prescrizioni ricostruite dalla potenza osservata**, come documentato in [prescribed_dataset_final.md](prescribed_dataset_final.md). Questa scelta è confermata dall'utente. I risultati saranno condizionati al target ricostruito: non dimostreranno previsione prospettica rispetto a prescrizioni originali indipendenti. La possibile dipendenza tra ingresso ricostruito e residuo limita l'interpretazione causale e le garanzie statistiche di identificazione.
ok
L'AR(2) già esaminato produce traiettorie plausibili, ma assorbe insieme transitori e rumore. La nuova separazione deve dipendere dalla risposta riproducibile rispetto ai cambi di target; la sola autocorrelazione non distingue le due componenti.

## 1. Formulazione consigliata

Con passo di campionamento \(\Delta t=1\,\mathrm{s}\), definiamo:

\[
u_t=P_{\mathrm{prescritta},t}-P_{\mathrm{prescritta},t-1},
\qquad
y_t=P_{\mathrm{real},t}-P_{\mathrm{prescritta},t}.
\]

Il modello deterministico proposto è:

\[
y_t=r_t+e_t,
\qquad
r_t=-\sum_{i=1}^{n}a_i r_{t-i}+\sum_{j=0}^{n}b_j u_{t-j},
\qquad n\in\{2,3,4\}.
\]

Equivalentemente, indicando con \(q^{-1}\) il ritardo di un campione:

\[
r_t=G_n(q^{-1})u_t,
\qquad
G_n(q^{-1})=
\frac{b_0+b_1q^{-1}+\cdots+b_nq^{-n}}
{1+a_1q^{-1}+\cdots+a_nq^{-n}}.
\]

L'ordine \(n\) è l'ordine dinamico nominale: eventuali cancellazioni polo-zero possono ridurre quello effettivo. Le grandezze \(u,y,r,e\) sono in watt; i coefficienti \(a_i,b_j\) sono adimensionali.

Si tratta di una struttura standard di identificazione ingresso–uscita con dinamica deterministica separata dal disturbo, coerente con l'impostazione *output-error*. L'aggiunta di un modello autonomo del rumore porta verso una struttura Box–Jenkins. L'adattamento qui proposto non è un modello fisiologico pubblicato specificamente per questo atleta.

Riferimento metodologico: [MathWorks — Input-Output Polynomial Models](https://www.mathworks.com/help/ident/input-output-polynomial-models.html).

Proprietà richieste:

- **Stabilità:** tutti i poli devono essere all'interno del cerchio unitario.
- **Termine contemporaneo:** \(b_0u_t\) consente un cambiamento immediato di \(y_t\), che si verifica al cambio di target anche se la potenza reale non si è ancora mossa.
- **Simulazione libera:** la ricorsione usa i valori simulati di \(r\), senza sostituirli con i ritardi del residuo osservato \(y\).
- **Continuità:** lo stato continua attraverso i cambi di lap e di target, senza reset alle transizioni.

Per un cambio isolato di ampiezza \(A\) al tempo \(t_0\):

\[
r_{t_0+k}=A h_k,
\]

dove \(h_k\) è la risposta impulsiva di \(G_n\). Cambi successivi producono risposte sovrapposte. Il fitting usa l'intero tratto continuo, non soltanto finestre attorno alle transizioni.

## 2. Assunzioni e parametrizzazione

In assenza di nuovi cambi di target, la stabilità implica:

\[
r_t\longrightarrow 0.
\]

Il modello descrive quindi un errore transitorio di inseguimento, non uno scostamento permanente dal target. Si assumono risposta proporzionale all'ampiezza del cambio e parametri condivisi tra workout dello stesso atleta.

Si propone di imporre la stabilità direttamente nella parametrizzazione dei poli, consentendo poli reali e coppie complesse coniugate. Non si impongono segni ai coefficienti, per consentire ritardo, overshoot e recupero. Poli quasi unitari e cancellazioni polo-zero devono essere segnalati come possibili problemi di identificabilità.

Un eventuale bias globale rimane nella media del residuo:

\[
e_t=\mu+v_t.
\]

La media \(\mu\), in watt, viene stimata come parametro accessorio già durante il fitting dinamico, per evitare che la dinamica debba imitare una media non nulla. Non si introducono offset liberi per lap o workout. La decomposizione mantiene \(r_t\) come solo termine transitorio; \(e_t\) può avere media non nulla.

## 3. Eventuale separazione tra salita e discesa

La prima famiglia da confrontare usa l'ingresso firmato \(u_t=\Delta P_t\). L'estensione asimmetrica usa:

\[
u_t^+=\max(\Delta P_t,0),
\qquad
u_t^-=\max(-\Delta P_t,0),
\]

\[
r_t=-\sum_{i=1}^{n}a_i r_{t-i}
+\sum_{j=0}^{n}\left(b_j^+u_{t-j}^++b_j^-u_{t-j}^-\right).
\]

Si propone un denominatore comune alle due direzioni: stessa famiglia di tempi dinamici, risposte diverse. La condivisione dei poli è un'assunzione da verificare, non una proprietà fisiologica dell'atleta. Il modello simmetrico è il caso vincolato \(b_j^-=-b_j^+\).

Per contenere la complessità, confrontare prima gli ordini 2, 3 e 4 simmetrici; valutare poi l'asimmetria sull'ordine più piccolo convincente. Tutta la selezione resta nei dati di sviluppo. Questa procedura non costituisce una ricerca esaustiva di tutte le combinazioni ordine–asimmetria.

## 4. Stima robusta

Per ogni candidato simulare \(r_t(\theta)\) sull'intero tratto continuo e minimizzare:

\[
\min_{\theta,\mu}
\sum_{w\in\mathrm{training}}\frac{1}{N_w}
\sum_{t\in w}
\rho_\delta\!\left(\frac{y_t-\mu-r_t(\theta)}{s}\right),
\]

dove \(N_w\) è il numero di campioni utilizzati nel workout, \(s\) una scala robusta in watt e \(\rho_\delta\) la perdita di Huber.

Scelte proposte:

- Scala e soglia Huber determinate usando solo il training e mantenute comuni ai candidati.
- Peso uguale per workout; campioni equiponderati al suo interno.
- Ottimizzazione vincolata stabile, con più inizializzazioni riproducibili.
- Confronto di sensibilità con minimi quadrati.
- Nessuna eliminazione automatica degli estremi; verificare che la perdita robusta non riduca sistematicamente il contributo delle transizioni.

La Huber limita l'influenza degli estremi, ma non risolve l'autocorrelazione. Non prefiltrare inizialmente con l'AR(2) attuale, che contiene anche i transitori da separare. La prima stima è sequenziale; una stima congiunta dinamica–AR resta un'eventuale estensione da concordare se la separazione risultasse sensibile al rumore colorato.

## 5. Continuità, disponibilità e condizioni iniziali

Riutilizzare le regole di disponibilità e continuità della simulazione libera AR, descritte nel [README del modulo](../src/power_hr_eda/power_residual_ar/README.md): nessun reset per lap o cambio di target numerico; tratti distinti in presenza di interruzioni reali, pause o segnali/target invalidi. I target massimali categorici senza valore in watt non definiscono un ingresso numerico per questo modello.

Non interpolare, filtrare o concatenare implicitamente tratti separati. Non costruire differenze di target attraverso confini di indisponibilità.

Usare lo storico disponibile del target per propagare lo stato. Quando manca, adottare una convenzione comune, proposta come stato nullo, dichiarando che equivale ad assumere transitorio iniziale assente. Il primo target disponibile non genera un salto artificiale da zero.

Non stimare lo stato iniziale di validation usando l'intera potenza osservata. L'effetto dell'inizializzazione deve essere riportato e verificato con lo stesso criterio per tutti gli ordini; eventuali analisi di sensibilità sul tratto iniziale non devono sostituire silenziosamente la valutazione sull'intero tratto.

## 6. Confronto degli ordini e validazione

La selezione valuta la ricostruzione deterministica senza feedback della potenza osservata:

\[
\widehat P_t=P_{\mathrm{prescritta},t}+\widehat\mu+\widehat r_t.
\]

Usare holdout per workout, preferibilmente temporale. Tutti gli ordini devono condividere campioni valutati, inizializzazione e trattamento dei gap. Non usare split casuali dei campioni temporali.

Baseline:

1. \(r_t=0\), senza bias: \(\widehat P_t=P_{\mathrm{prescritta},t}\).
2. \(r_t=0\), con lo stesso bias globale consentito ai candidati dinamici, stimato esclusivamente sul training.

| Verifica | Scopo |
| --- | --- |
| RMSE, MAE e bias per workout, in W | Misurare il miglioramento sull'intera traiettoria |
| Errori dopo salite, discese e nei plateau | Evitare che i plateau nascondano transitori mal descritti |
| Media dei residui allineati alle transizioni | Cercare risposta sistematica ancora non spiegata |
| Risposte impulsive e stabilità tra sottoinsiemi | Verificare ripetibilità e identificabilità |
| Bootstrap per workout | Quantificare l'incertezza rispettando la dipendenza temporale interna |

Scegliere l'ordine più piccolo con prestazioni sostanzialmente equivalenti al migliore, considerando l'incertezza delle differenze. La regola operativa di equivalenza e le finestre diagnostiche devono essere fissate prima della selezione. Un guadagno minimo accompagnato da poli instabili tra fit o quasi cancellati non giustifica l'ordine superiore.

Non usare AIC/BIC calcolati assumendo erroneamente indipendenti gli errori di simulazione. Non selezionare la dinamica tramite l'RMSE di una traiettoria casuale generata dall'AR.

Il protocollo AR esistente segnala che il precedente test è già stato esaminato. Quel test può fornire confronti descrittivi, ma non una nuova conferma indipendente. Il protocollo di sviluppo e l'eventuale disponibilità di dati realmente non esaminati devono essere dichiarati prima dell'esperimento.

## 7. Rifitting dell'AR

Congelata la struttura dinamica, calcolare:

\[
\widehat e_t=y_t-\widehat r_t
\]

e rifittare inizialmente lo stesso AR(2), con intercetta, sui soli dati di training:

\[
e_t=c+\phi_1e_{t-1}+\phi_2e_{t-2}+\varepsilon_t.
\]

I coefficienti \(\phi_i\) sono adimensionali; \(c\) ed \(\varepsilon_t\) sono in watt. La media stazionaria dell'AR, quando definita, è \(c/(1-\phi_1-\phi_2)\). Non aggiungere nuovamente \(\widehat\mu\) alla simulazione se la media è già inclusa nell'AR di \(e_t\).

Il residuo \(e_t\) può restare autocorrelato: è ciò che descrive l'AR. Sono le innovazioni \(\varepsilon_t\) a dover risultare compatibili con rumore non correlato. Verificare anche la stabilità dell'AR e la diagnostica delle innovazioni.

Il criterio decisivo per la decomposizione è che in \(e_t\) non resti una risposta sistematica ai cambi di prescrizione. Se resta, l'AR sta ancora compensando una dinamica mancante. Se scompare soltanto nel training, senza miglioramento fuori campione, la separazione non è dimostrata.

## 8. Perimetro e verifiche di un'eventuale implementazione

Componenti presumibilmente coinvolti: un modulo dedicato alla risposta dinamica in `src/power_hr_eda/`, riuso delle regole di lettura e continuità del modulo `power_residual_ar`, test mirati in `tests/` e nuovi artefatti in una directory dedicata di `reports/`. I percorsi definitivi saranno concordati nella proposta implementativa.

Preservare dataset, risultati AR precedenti e dati raw. Nessuna nuova covariata, nessun modello HR, nessuna interpretazione fisiologica dei poli o dei coefficienti.

Verifiche previste prima di interpretare risultati reali:

- Recupero di risposte sintetiche note con rumore colorato, per verificare la separazione proposta.
- Stabilità e causalità della simulazione, incluso il termine contemporaneo.
- Sovrapposizione delle risposte senza reset ai cambi di target.
- Gestione di gap, target non numerici e inizializzazione senza salti artificiali.
- Assenza di uso della potenza osservata nella ricorsione deterministica di validation.
- Supporto comune nel confronto degli ordini e persistenza di configurazione, split e seed.

L'implementazione richiede una successiva approvazione del relativo scope. La presente proposta registra la formulazione e la scelta esplicita di usare prescrizioni ricostruite.
