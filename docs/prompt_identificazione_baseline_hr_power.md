# Prompt operativo — identificazione baseline HR–Power

## Obiettivo

Implementare una prima identificazione del modello dinamico HR–Power su segmenti già selezionati e preprocessati.

Non introdurre per ora:
- detrending aggiuntivo;
- normalizzazione rispetto a FTP;
- modelli time-varying;
- modelli di ordine superiore;
- interpretazioni fisiologiche longitudinali.

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

I segmenti possono essere sia UP sia DOWN e avere durata indicativamente compresa tra 40 s e 5 min.

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

Il residuo medio dovrebbe essere vicino a zero.

### Struttura temporale

Visualizzare:

\[
e(t)
\]

nel tempo.

Segnalare fit sospetti se i residui mostrano:

- trend crescente o decrescente evidente;
- pattern sistematico;
- errore persistentemente positivo o negativo.

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

Non è necessario, in questa fase, eseguire test formali di normalità o eteroschedasticità.

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

## 5. Output finale per ogni segmento

Produrre una riga riassuntiva con almeno:

```text
segment_id
direction
duration_s

K_hat
L_hat
tau_hat

RMSE

residual_mean
residual_sd
residual_autocorrelation_lag1

SE_K
SE_L
SE_tau

RSE_K
RSE_L
RSE_tau

optimizer_status
```

Produrre inoltre due grafici:

1. HR osservata vs HR prevista;
2. residui nel tempo.

---

## 6. Obiettivo della fase

Questa fase deve rispondere solo a tre domande:

1. Il modello P1D converge sul segmento?
2. I residui mostrano errori sistematici evidenti?
3. \(K\), \(L\) e \(\tau\) risultano stimati con precisione ragionevole?

Non utilizzare ancora i parametri per conclusioni su fitness, fatica o stato di forma.
