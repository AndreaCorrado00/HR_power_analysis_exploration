# AR normalizzato e scala marginale del residuo

Struttura nota GLS con covarianza D R D: Pinheiro e Bates2000, https://stat.ethz.ch/R-manual/R-devel/library/nlme/html/gls.html.
Adattamento al progetto: r=m+s(t)u, Var(u)=1, u AR(2) stazionario. Dinamica ordine4 e media residua m congelate.
Due SD marginali (W): primi30s dopo un salto reale oppure resto. Nessun salto inventato a inizio segmento: scala base.
Soglia30s fissata, scale libere e positive; non imposto SD transizione maggiore. Non e GARCH.
AR parametrizzato da correlazioni parziali k1,k2: phi1=k1(1-k2),phi2=k2; varianza innovazione normalizzata q=(1-k1²)(1-k2²).
MLE gaussiana esatta con coppia iniziale stazionaria, indipendenza fra segmenti; peso uguale per campione; tre partenze.
Confronto interno scala unica ristimata con stessa likelihood/normalizzazione; confronti esterni originali congelati.
Nessun IC parametri stimato. Train soltanto per fit, validation per confronto, test escluso.
La previsione libera media resta invariata; la previsione AR a un passo cambia per il rapporto fra scale corrente e passate.
Simulazione1000 traiettorie per segmento, seed SHA256(workout:segment), niente feedback osservato.
Lap e parti stabili: stesso protocollo di lap_variability.py; metriche globali a peso uguale per workout.
Phase baseline include inizi con storia salto ignota; non equivale al plateau60 della diagnostica precedente.
Potenza negativa non corretta. Un miglioramento probabilistico non prova realismo fisiologico.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.scaled_ar_run

| split | mode | model | coverage80 | width80_w | interval_score80_w | nll |
|---|---|---|---|---|---|---|
| train | conditional | constant | 0.9071 | 144.5 | 206.2 | 5.403 |
| train | conditional | context | 0.9089 | 143.3 | 203.2 | 5.376 |
| train | conditional | garch | 0.8816 | 121.9 | 176.6 | 5.138 |
| train | conditional | targeted | 0.8759 | 117.4 | 175.2 | 5.144 |
| train | free | constant | 0.8522 | 234.3 | 332.6 | nan |
| train | free | context | 0.8465 | 232.4 | 333.9 | nan |
| train | free | garch | 0.8714 | 255.5 | 339.6 | nan |
| train | free | targeted | 0.8098 | 194.4 | 326.1 | nan |
| validation | conditional | constant | 0.9251 | 144.5 | 188.2 | 5.293 |
| validation | conditional | context | 0.9254 | 141.7 | 183.7 | 5.253 |
| validation | conditional | garch | 0.8848 | 110.4 | 157.1 | 5.042 |
| validation | conditional | targeted | 0.8794 | 106.8 | 155.9 | 5.046 |
| validation | free | constant | 0.886 | 234.2 | 299.9 | nan |
| validation | free | context | 0.879 | 229.9 | 298.8 | nan |
| validation | free | garch | 0.9026 | 255.6 | 310.4 | nan |
| validation | free | targeted | 0.847 | 194.4 | 286.5 | nan |
| train | conditional | constant_scaled | 0.9079 | 145.3 | 206.6 | 5.404 |
| train | conditional | phase_scaled | 0.9091 | 145.7 | 206.6 | 5.402 |
| train | free | constant_scaled | 0.8548 | 237.1 | 333.4 | nan |
| train | free | phase_scaled | 0.8561 | 238.4 | 334 | nan |
| validation | conditional | constant_scaled | 0.9258 | 145.3 | 188.7 | 5.295 |
| validation | conditional | phase_scaled | 0.9281 | 146.2 | 188.4 | 5.286 |
| validation | free | constant_scaled | 0.8885 | 237 | 301.1 | nan |
| validation | free | phase_scaled | 0.8904 | 239.2 | 301.9 | nan |

| split | phase | model | laps | real_sd_median_w | sim_sd_median_w | median_ratio | fraction_below_p10 |
|---|---|---|---|---|---|---|---|
| train | full | constant_scaled | 601 | 84.41 | 92.27 | 1.116 | 0.4093 |
| train | full | phase_scaled | 601 | 84.41 | 92.68 | 1.172 | 0.4359 |
| train | stable | constant_scaled | 311 | 63.41 | 89.87 | 1.428 | 0.7299 |
| train | stable | phase_scaled | 311 | 63.41 | 89.26 | 1.418 | 0.7299 |
| train | transition | constant_scaled | 601 | 91.38 | 89.22 | 1.026 | 0.2612 |
| train | transition | phase_scaled | 601 | 91.38 | 94.83 | 1.09 | 0.3095 |
| validation | full | constant_scaled | 239 | 97.43 | 92.4 | 0.97 | 0.3556 |
| validation | full | phase_scaled | 239 | 97.43 | 96.83 | 1.014 | 0.364 |
| validation | stable | constant_scaled | 107 | 57.83 | 90.99 | 1.544 | 0.7383 |
| validation | stable | phase_scaled | 107 | 57.83 | 90.38 | 1.533 | 0.7383 |
| validation | transition | constant_scaled | 239 | 103.5 | 90.91 | 0.9142 | 0.1715 |
| validation | transition | phase_scaled | 239 | 103.5 | 97.81 | 0.9705 | 0.2134 |
