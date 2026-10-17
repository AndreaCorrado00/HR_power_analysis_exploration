# Transizioni: errore medio e dispersione

Analisi precedenti: diagnostics/variance_transition_aggregate.csv confrontava media/varianza delle sole innovazioni per fase;
interval_report.md verificava ACF/ARCH nei plateau e dopo normalizzazione entro intervallo.
lap_variability_report.md confrontava SD della potenza totale, non il residuo dopo la dinamica.
Qui si aggiungono train, residuo della dinamica e allineamento per direzione/ampiezza/tempo dal salto.

Modelli congelati, nessun rifit e nessuna simulazione nuova; test escluso.
Residuo = reale-target-risposta ordine4-media stazionaria AR; innovazione = errore AR a un passo.
Ogni cambio target e un evento; nessun evento inventato a inizio segmento. Censura al cambio successivo o gap.
Classi salto assoluto: <25,25-75,75-150,>=150 W. Bin temporali 0-4,5-9,...25-29,30-59,>=60s.
Plateau60 qui include solo campioni almeno60s dopo un salto noto: diverso dal plateau storico >=30s.
Profili pesati per campione, con numerosita eventi/workout. Riepilogo per fase a peso uguale per workout.
SD e dispersione attorno alla media del gruppo, non RMSE attorno a zero.
Controllo fuori dal train: sottrazione diagnostica della media train della stessa cella direzione/ampiezza/tempo;
minimo5 eventi e3 workout train, nessuna stima sulla validation. Confronto sugli stessi campioni supportati.
La sottrazione non cambia il modello: misura quanto una semplice forma sistematica trasferibile spiega gli errori.
Nessun p-value iid o IC sui secondi correlati. Celle sparse, durata e livelli target possono confondere i confronti.
Un mancato miglioramento non dimostra l'assenza di ogni errore sistematico possibile.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.transition_diagnostics


| split | signal | phase | workouts | n | mean_w | variance_w2 | mse_w2 | sd_w |
|---|---|---|---|---|---|---|---|---|
| train | innovation | 30-59 | 36 | 6799 | -1.478 | 2711 | 2705 | 52.07 |
| train | innovation | plateau60 | 36 | 87303 | -0.09226 | 2454 | 2455 | 49.54 |
| train | innovation | transition | 36 | 18273 | -0.6152 | 3928 | 3917 | 62.68 |
| train | residual | 30-59 | 36 | 6799 | -3.755 | 6507 | 6794 | 80.67 |
| train | residual | plateau60 | 36 | 87303 | 0.03486 | 6996 | 7065 | 83.64 |
| train | residual | transition | 36 | 18273 | -1.953 | 9526 | 9779 | 97.6 |
| validation | innovation | 30-59 | 12 | 2907 | -2.275 | 2256 | 2278 | 47.5 |
| validation | innovation | plateau60 | 12 | 31090 | -0.03434 | 1707 | 1707 | 41.32 |
| validation | innovation | transition | 12 | 8388 | -2.734 | 4307 | 4316 | 65.63 |
| validation | residual | 30-59 | 12 | 2907 | -10.82 | 7523 | 8294 | 86.74 |
| validation | residual | plateau60 | 12 | 31090 | 0.3015 | 4714 | 4721 | 68.66 |
| validation | residual | transition | 12 | 8388 | -10.75 | 1.096e+04 | 1.161e+04 | 104.7 |

## Sottrazione diagnostica media train sulla validation

| signal | phase | n | workouts | available_n | raw_mse | centered_mse | mse_reduction_pct | raw_variance | centered_variance |
|---|---|---|---|---|---|---|---|---|---|
| innovation | 30-59 | 2877 | 12 | 2907 | 2290 | 2270 | 0.8685 | 2269 | 2252 |
| innovation | plateau60 | 30517 | 12 | 31090 | 1707 | 1707 | 0.009591 | 1708 | 1707 |
| innovation | transition | 8358 | 12 | 8388 | 4324 | 4261 | 1.451 | 4315 | 4270 |
| residual | 30-59 | 2877 | 12 | 2907 | 8280 | 8153 | 1.532 | 7514 | 7518 |
| residual | plateau60 | 30517 | 12 | 31090 | 4728 | 4728 | 0.01124 | 4721 | 4714 |
| residual | transition | 8358 | 12 | 8388 | 1.162e+04 | 1.078e+04 | 7.224 | 1.097e+04 | 1.05e+04 |
