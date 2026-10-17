# Variabilita temporale interna ai lap

Nessun rifit. Train e validation soltanto. Lap reali da lap_index, campioni validi come nella pipeline originale.
Confronto SD campionaria (ddof=1) della potenza reale con la distribuzione della SD di 1000 traiettorie libere.
Non e un confronto con l'ampiezza delle bande fra traiettorie. Include la risposta deterministica in entrambe le serie.
Simulazione per segmento continuo, senza reset ai lap; frammenti validi dello stesso lap combinati sugli stessi timestamp.
Stabile: almeno30s dall'inizio lap, dall'ultimo cambio target e dall'inizio del segmento valido.
Transition: complemento della parte stabile, include inizializzazioni dopo gap; non solo cambi target.
Almeno30 campioni validi per ciascun gruppo; segmenti <=ordine AR esclusi come nel confronto precedente.
Seed SHA256(workout:segment), modelli e inizializzazioni identici al confronto della varianza.
Rapporto=mediana SD simulate / SD reale, poi mediana fra lap; zero SD reale: rapporto non definito.
Aggregato principale a peso uguale per lap; file workouts permette confronto a livello workout.
Percentili10-90 descrivono la variabilita simulativa, non IC sui parametri o test di significativita.
Nessuna correzione per potenza negativa applicata.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.lap_variability

| split | phase | model | laps | workouts | real_sd_median_w | sim_sd_median_w | median_ratio | fraction_below_p10 | fraction_above_p90 |
|---|---|---|---|---|---|---|---|---|---|
| train | full | constant | 601 | 36 | 84.41 | 91.23 | 1.111 | 0.4027 | 0.2296 |
| train | full | context | 601 | 36 | 84.41 | 103 | 1.234 | 0.5108 | 0.1631 |
| train | full | garch | 601 | 36 | 84.41 | 98.14 | 1.182 | 0.2912 | 0.03161 |
| train | full | targeted | 601 | 36 | 84.41 | 80.92 | 0.9837 | 0.203 | 0.1797 |
| train | stable | constant | 311 | 36 | 63.41 | 88.87 | 1.412 | 0.7235 | 0.1415 |
| train | stable | context | 311 | 36 | 63.41 | 86.49 | 1.384 | 0.6913 | 0.1801 |
| train | stable | garch | 311 | 36 | 63.41 | 95.2 | 1.606 | 0.5723 | 0.01608 |
| train | stable | targeted | 311 | 36 | 63.41 | 74.73 | 1.208 | 0.4019 | 0.08682 |
| train | transition | constant | 601 | 36 | 91.38 | 88.53 | 1.022 | 0.2579 | 0.2712 |
| train | transition | context | 601 | 36 | 91.38 | 97.17 | 1.165 | 0.3877 | 0.2013 |
| train | transition | garch | 601 | 36 | 91.38 | 90.13 | 1.02 | 0.1414 | 0.05657 |
| train | transition | targeted | 601 | 36 | 91.38 | 76.34 | 0.8717 | 0.1231 | 0.223 |
| validation | full | constant | 239 | 12 | 97.43 | 91.34 | 0.962 | 0.3473 | 0.251 |
| validation | full | context | 239 | 12 | 97.43 | 117.3 | 1.166 | 0.4184 | 0.1381 |
| validation | full | garch | 239 | 12 | 97.43 | 101.5 | 0.9877 | 0.2887 | 0.02092 |
| validation | full | targeted | 239 | 12 | 97.43 | 82.17 | 0.8482 | 0.2092 | 0.2092 |
| validation | stable | constant | 107 | 12 | 57.83 | 89.95 | 1.525 | 0.7383 | 0.1495 |
| validation | stable | context | 107 | 12 | 57.83 | 83.63 | 1.431 | 0.7383 | 0.1495 |
| validation | stable | garch | 107 | 12 | 57.83 | 102.2 | 1.798 | 0.6636 | 0.02804 |
| validation | stable | targeted | 107 | 12 | 57.83 | 77.61 | 1.352 | 0.5234 | 0.1028 |
| validation | transition | constant | 239 | 12 | 103.5 | 90.09 | 0.91 | 0.1715 | 0.251 |
| validation | transition | context | 239 | 12 | 103.5 | 110.2 | 1.08 | 0.2594 | 0.159 |
| validation | transition | garch | 239 | 12 | 103.5 | 91.02 | 0.9127 | 0.09623 | 0.01674 |
| validation | transition | targeted | 239 | 12 | 103.5 | 77.25 | 0.8029 | 0.08368 | 0.205 |
