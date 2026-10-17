# Intercetta casuale per lap e AR(2)

P=target+G(delta target)+m+b_lap+w. Risposta ordine4 e m congelati; b_lap iid N(0,sigma_b²), indipendente da w.
w AR(2) stazionario senza intercetta, innovazioni iid N(0,sigma_e²). sigma_e e SD innovazioni, non SD marginale w.
Lap identificati da lap_index dei file, diversi fra workout. Offset condiviso fra frammenti dello stesso lap;
w continuo ai confini lap e indipendentemente reinizializzato ai gap reali. Nessuna interpolazione o clipping della potenza.
Famiglia: modello lineare misto con correlazione AR, Pinheiro e Bates2000; implementazione specializzata gaussiana.
Fit ML marginale ESATTO: integra b, include stato iniziale AR stazionario, usa Woodbury e sufficienti cross-prodotti.
Parametri: sigma_e e sigma_b in W, PACF k1/k2 adimensionali; phi1=k1(1-k2),phi2=k2.
4 partenze; sigma_b² puo essere zero. Media residua m fissa al valore del precedente AR: confronto isolato delle covarianze.
Scala numerica del parametro sigma_b² basata sul train. Likelihood pesata per campione.
Confronto interno lap_zero: stesso fit con sigma_b=0; riferimento equivalente alla scala unica gaussiana precedente.
Train36 workout per fitting; validation12 per predizione marginale libera, senza conoscere offset/medie osservate.
Nessun fit/posterior offset sulla validation. Gli offset mostrati sono estrazioni casuali, NON stime dei lap reali.
1000 traiettorie/workout, seed SHA256('lap-ar:'+workout), stessi numeri casuali per le due varianti.
Media libera=target+G+m, invariata; bande=P10-P90 marginali, non simultanee. NLL qui e congiunta marginale/workout,
non la NLL un passo dei precedenti file: non confrontare colonne con significato diverso.
Metriche aggregate con peso uguale per workout; SD interna lap con stesso protocollo precedente (min30campioni,
stabile dopo30s da lap/cambio target/segmento). Pesi uguali per lap nel riepilogo SD.
Confini lap: salvati salti reali e simulati per verificare discontinuita da offset indipendenti.
Potenza negativa: quota delle simulazioni, senza correzione. Non e nuova evidenza fisiologica.
Profilo likelihood a sigma_b fissato con ristima altri parametri: diagnostica, non IC chi-quadro al bordo.
Incertezza dei parametri non propagata nelle bande; nessun IC Wald per varianza al bordo o confondimento con persistenza.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.lap_random_ar_run

## Esito

Validation: delta interval score random-zero=-0.0000 W; miglioramenti superiori a0.01 W in 0/12 workout. Differenze inferiori a0.01 W considerate trascurabili. SD offset stimata=0.000000 W; SD marginale w=92.676 W; SD innovazioni=56.672 W. Una stima al bordo zero significa che il fit non richiede un effetto casuale lap aggiuntivo rispetto all’AR.


| split | mode | model | workouts | coverage80 | width80_w | interval_score80_w | joint_nll_per_sample | negative_probability |
|---|---|---|---|---|---|---|---|---|
| train | free | lap_random | 36 | 0.8552 | 237 | 333.4 | 5.412 | 0.03034 |
| train | free | lap_zero | 36 | 0.8552 | 237 | 333.4 | 5.412 | 0.03034 |
| validation | free | lap_random | 12 | 0.8889 | 237.1 | 301.3 | 5.298 | 0.03199 |
| validation | free | lap_zero | 12 | 0.8889 | 237.1 | 301.3 | 5.298 | 0.03199 |

| split | phase | model | laps | workouts | real_sd_median_w | sim_sd_median_w | median_ratio | fraction_below_p10 |
|---|---|---|---|---|---|---|---|---|
| train | full | lap_random | 601 | 36 | 84.41 | 92.19 | 1.116 | 0.4077 |
| train | full | lap_zero | 601 | 36 | 84.41 | 92.19 | 1.116 | 0.4077 |
| train | stable | lap_random | 311 | 36 | 63.41 | 89.86 | 1.429 | 0.7331 |
| train | stable | lap_zero | 311 | 36 | 63.41 | 89.86 | 1.429 | 0.7331 |
| train | transition | lap_random | 601 | 36 | 91.38 | 89.34 | 1.028 | 0.2612 |
| train | transition | lap_zero | 601 | 36 | 91.38 | 89.34 | 1.028 | 0.2612 |
| validation | full | lap_random | 239 | 12 | 97.43 | 92.56 | 0.9731 | 0.3473 |
| validation | full | lap_zero | 239 | 12 | 97.43 | 92.56 | 0.9731 | 0.3473 |
| validation | stable | lap_random | 107 | 12 | 57.83 | 91.04 | 1.547 | 0.7383 |
| validation | stable | lap_zero | 107 | 12 | 57.83 | 91.04 | 1.547 | 0.7383 |
| validation | transition | lap_random | 239 | 12 | 103.5 | 90.85 | 0.912 | 0.1757 |
| validation | transition | lap_zero | 239 | 12 | 103.5 | 90.85 | 0.912 | 0.1757 |

| sigma_b | converged | nll_per_sample | delta_total_nll |
|---|---|---|---|
| 0 | True | 5.457 | 0 |
| 5 | True | 5.457 | 20.69 |
| 10 | True | 5.457 | 56.5 |
| 20 | True | 5.457 | 130.1 |
| 40 | True | 5.458 | 299.8 |
| 80 | True | 5.459 | 643.3 |

## Limite della ricostruzione target

Il manifest originale usa rounded_observed_mean, arrotondamento 5 W. Alcune ripetute condividono target ricavati dalle medie osservate. Nei 1158 lap train/validation con target e media numerici (senza soglia di durata), il 97.41% ha media osservata entro2.5 W dal target; differenza assoluta mediana 1.307 W. La ricostruzione assorbe quindi parte dello scostamento che b_lap dovrebbe rappresentare. sigma_b=0 non prova assenza di offset rispetto a prescrizioni esterne indipendenti; il risultato vale condizionatamente ai target ricostruiti. Non si modifica la pipeline target in questo esperimento.

## Come interpretare pagina e risultati

- SD offset lap: se zero, il contributo b e inattivo; le curve con/senza offset devono coincidere salvo precisione numerica.
- SD marginale w descrive la dispersione stazionaria delle oscillazioni; SD epsilon descrive i nuovi shock a un passo.
  Sono grandezze diverse e non vanno confuse con la SD campionaria di un lap finito.
- Media libera invariata: E[b]=E[w]=0; non si utilizzano le medie osservate dei lap per spostare la previsione.
- Il grafico inferiore mostra b e w della medesima traiettoria superiore. Non sono stime degli stati reali della validation.
- Bande P10-P90: dispersione fra traiettorie a tempo fisso. Il rapporto SD nel riepilogo lap misura invece la variabilita
  nel tempo dentro ogni lap. Un rapporto mediano maggiore1 indica oscillazioni simulate troppo grandi.
- Coverage attesa80%; un valore maggiore non e automaticamente migliore: controllare ampiezza e interval score.
- Confronto interno lap_random/lap_zero usa gli stessi numeri casuali; differenze inferiori0.01W di score sono trascurabili.
  I riferimenti precedenti hanno seed diversi: piccole differenze di bande possono essere Monte Carlo.
- Profilo likelihood: delta NLL positivo peggiora il fit rispetto all'ottimo; il profilo non e un IC al bordo zero.
- Negative probability e la quota media simulativa di potenze negative, non una correzione applicata al segnale.
- Il risultato non identifica offset rispetto a prescrizioni esterne indipendenti, perche i target qui sono ricostruiti
  dalle medie osservate. Non sostituire i modelli precedenti se non si osserva un miglioramento fuori dal fitting.

