# Prompt operativo — identificazione baseline HR–Power

## Obiettivo

Implementare una prima identificazione del modello dinamico HR–Power su segmenti già selezionati e preprocessati.
L'obiettivo è stimare il modello, verificarne il fit in modo minimale e quantificare l'incertezza dei parametri.

---

## 1. Modello da identificare

Usare un modello **first-order plus dead time (P1D)**:

\[
G(s)=\frac{K e^{-Ls}}{\tau s+1}
\]

Parametri:

- \(K\): steady-state gain, in bpm/W;
- \(L\): dead time, in secondi;
- \(\tau\): time constant, in secondi.

Input:

\[
P(t)
\]

Output:

\[
HR(t)
\]
---

## 2. Identificazione

Stimare:

\[
\hat\theta=[\hat K,\hat L,\hat\tau]
\]

tramite **nonlinear least squares con bounds**.

Funzione obiettivo:

\[
J(K,L,\tau)=
\sum_t
\left[
HR(t)-\widehat{HR}(t;K,L,\tau)
\right]^2
\]

Vincoli minimi:

\[
K>0
\]

\[
L\ge0
\]

\[
\tau>0
\]

Usare un ottimizzatore bounded robusto, ad esempio:

```python
scipy.optimize.least_squares(..., method="trf")
```

È preferibile usare più inizializzazioni e verificare che la soluzione converga agli stessi parametri.

Output minimo per segmento:

```text
K_hat
L_hat
tau_hat
RMSE
optimizer_status
```

---

## 3. Analisi minima dei residui

Definire:

\[
e(t)=HR(t)-\widehat{HR}(t)
\]

Per ogni fit verificare almeno:

### Bias

Calcolare:

\[
\bar e=
\frac{1}{N}\sum_t e(t)
\]

### Struttura temporale

Visualizzare:

\[
e(t)
\]

nel tempo.

### Autocorrelazione

Calcolare almeno l'autocorrelazione al lag 1.

L'obiettivo non è imporre perfetta white noise, ma verificare che non rimanga una forte dinamica sistematica non catturata dal modello.

Output minimo:

```text
residual_mean
residual_sd
residual_autocorrelation_lag1
```

e grafico dei residui nel tempo.

---

## 4. Analisi minima della precisione dei parametri

Usare il Jacobiano restituito dal nonlinear least squares per stimare una covariance matrix approssimata:

\[
\widehat{Cov}(\hat\theta)
\approx
\hat\sigma^2
(J^T J)^{-1}
\]

dove:

\[
\hat\sigma^2
=
\frac{SSE}{N-p}
\]

con:

- \(N\): numero di osservazioni;
- \(p=3\): numero di parametri.

Da questa matrice ricavare:

\[
SE(K),\quad SE(L),\quad SE(\tau)
\]

e gli intervalli approssimativi al 95%:

\[
\hat\theta_j
\pm
1.96\,SE(\hat\theta_j)
\]

Calcolare anche il Relative Standard Error:

\[
RSE_j=
\frac{SE(\theta_j)}
{|\hat\theta_j|}
\cdot100
\]

Output minimo:

```text
SE_K
SE_L
SE_tau

CI95_K
CI95_L
CI95_tau

RSE_K
RSE_L
RSE_tau
```

---
### Output atteso per segmento
Produrre un grafico con due subplot:

1. HR osservata vs HR prevista + input di potenza;
2. residui nel tempo.

---

Crea una web app, SPA con framework vue, sotto webapp/model_identification_app che permetta il seguente workflow di esperimenti:
- pagina di carimento del dataset: poter caricare più dataset a partire da quelli presenti nella repository. Un dataset viene caricato importando i record csv, e ne devo poter caricare più di uno, eventualmente rinominandoli
- nella medesima pagina, caricato il dataset, quando viene selezionato, si deve visulizzare la durata media +-std dei segmenti. 
- sempre nella stessa pagina, devo poter suddividere il dataset in train val e test con percentuali di defoult 70-10-20% con seed regolabile ma fissato a un vaore qualsiasi di defoult
- pagina di identificazione del modello: devo poter selezionare il modello (al momento uno unico, ma prevedi di poterne attaccare di più) e lanciare (solo sul train) la stima dei parametri
- Nella medesima pagina devo visualizzare le proprietà della run che sta per partire e le run precedenti, potendovi eventualmente riaccedervi in un secondo momento
- Pagina di analisi: devo poter visualizzare tutti i fit di train con i doppi grafici come sopra e le distribuzioni dei parametri (tramite boxplots). Essendo l'analisi modello dipendendente, prepara il tutto in modo che sia scalabile modulabile per analisi diverse su modelli diversi
- Pagina di confronto: devo poter conforntare le distribuzioni dei parametri e le performance tra due modelli. Al momento è sufficiente la distribuzione dei parametri, ma anche il confronto dipende dal modello, quindi anche qui prepara il codice come al punto precedente

Devo sempre poter recuperare le run precedenti anche quando riavvio il servizio (procedura da documentare) e ogni esperimetno deve essere rigidamente documentato nelle sue impostazioni per essere perfettamente riproducibile. Quando lancio un esperimento il suo manifest deve venire salvato, e quando invece lo elimino, solo il suo manifest, deve venire archiviato in una folder apposita. Considera inoltre una rinomina dei manifest intelligente che permetta di capire rapidamente i parametri di esperimento.

Appositamente non vengono, al momento, usati validation e test set