# AR(2) congelato + GARCH(1,1)

Fit della sola varianza sul training; validation e test già esaminati sono descrittivi. Risposta dinamica, AR, split e artefatti originali invariati. Nessuna covariata aggiunta.

| name | estimate | unit | se_cluster | ci95_local |
|---|---|---|---|---|
| omega | 52.95 | W² | None | None |
| alpha | 0.1557 | 1 | None | None |
| beta | 0.8399 | 1 | None | None |

Persistenza α+β: 0.995566; varianza incondizionata: 11942.134 W².
Training: 36 workout, 260281 innovazioni. Avvisi: ['High persistence: sensitivity to initialization and long forecast horizon']. La routine non riporta IC locali quando rileva persistenza elevata o stime al bordo; None significa non stimato, non incertezza nulla. Gli IC locali cluster workout, quando disponibili, sono condizionati alla media congelata; non includono incertezza della dinamica/AR né della ricostruzione target.

## Lettura dei risultati

- test: ΔNLL a un passo = -0.304; Δinterval score a un passo = -36.31 W; Δinterval score libero = 10.40 W. Delta = GARCH − costante: negativo favorisce GARCH.
- validation: ΔNLL a un passo = -0.251; Δinterval score a un passo = -31.16 W; Δinterval score libero = 11.37 W. Delta = GARCH − costante: negativo favorisce GARCH.

Controllo del quarto momento gaussiano: 3α²+2αβ+β² = 1.039622; non è <1, quindi il quarto momento incondizionato non è finito nel modello stimato. La varianza incondizionata resta finita perché α+β<1. Questo segnala code marginali molto pesanti e cautela nell’interpretare diagnostiche dei quadrati e simulazioni finite.

Valutare separatamente uso aggiornato e simulazione libera. Una migliore NLL condizionata non giustifica automaticamente la sostituzione della simulazione AR. Copertura diversa dall’80% nominale indica calibrazione ancora imperfetta; persistenza e incertezza richiedono cautela. Non è stato imposto un ulteriore vincolo sul quarto momento e non è stato aggiunto un modello di contesto.

## Metriche fuori training

Medie con peso uguale per workout. NLL e interval score: minore è meglio; copertura nominale 0.80. Le due modalità rispondono a domande diverse e non vanno confrontate fra loro.

| split | mode | model | workouts | n | nll | coverage80 | width80_w | interval_score80_w |
|---|---|---|---|---|---|---|---|---|
| test | conditional | constant | 12 | 51563 | 5.286 | 0.9308 | 144.5 | 187.2 |
| test | conditional | garch | 12 | 51563 | 4.982 | 0.8939 | 107.3 | 150.9 |
| test | free | constant | 12 | 51681 | nan | 0.8847 | 230 | 311.9 |
| test | free | garch | 12 | 51681 | nan | 0.9005 | 251.8 | 322.3 |
| validation | conditional | constant | 12 | 91442 | 5.293 | 0.9251 | 144.5 | 188.2 |
| validation | conditional | garch | 12 | 91442 | 5.042 | 0.8848 | 110.4 | 157.1 |
| validation | free | constant | 12 | 91597 | nan | 0.8795 | 229.8 | 300.1 |
| validation | free | garch | 12 | 91597 | nan | 0.8945 | 251.7 | 311.5 |

Conditional: media AR usa residui osservati fino a t−1; h_t usa solo ε fino a t−1. Primi due campioni esclusi. Bande Gaussiane a un passo. La media è identica fra varianza costante e GARCH. Free: nessun feedback osservato; P10/P90 empirici delle traiettorie, non bande sulla media. 100 traiettorie, seed 42; quantili soggetti a errore Monte Carlo. La baseline free mantiene esattamente le simulazioni esistenti. Nessun clipping.

## ARCH sulle innovazioni standardizzate

| split | model | lag_s | significant_fdr | workouts |
|---|---|---|---|---|
| test | constant | 5 | 12 | 12 |
| test | constant | 15 | 12 | 12 |
| test | constant | 30 | 12 | 12 |
| test | garch | 5 | 5 | 12 |
| test | garch | 15 | 1 | 12 |
| test | garch | 30 | 2 | 12 |
| validation | constant | 5 | 12 | 12 |
| validation | constant | 15 | 12 | 12 |
| validation | constant | 30 | 12 | 12 |
| validation | garch | 5 | 4 | 12 |
| validation | garch | 15 | 4 | 12 |
| validation | garch | 30 | 3 | 12 |

FDR sui workout×lag separatamente per modello. P-value e statistiche completi in garch_diagnostics.csv. Riduzione dei rigetti non dimostra adeguatezza delle code Gaussiane: leggere anche copertura e score.

## Protocollo

ε_t=√h_t z_t; h_t=ω+α ε²_(t−1)+β h_(t−1), z Gaussiani standard nella simulazione. ω in W², α/β adimensionali. QML gaussiana, peso per campione, 6 partenze SLSQP, vincoli positività/stazionarietà. Nessuna selezione sul test. La distribuzione Gaussiana è una scelta iniziale da verificare.
h iniziale = ω/(1−α−β) per ogni tratto valido reale, nessun reset ai lap/target. Simulazione congiunta AR/GARCH: warm-up 4146 s, almeno 2000 s e decadimento atteso <1e−8, rifiutata se richiede oltre 100000 s. Le traiettorie sono autonome: non riproducono intenzionalmente il timing degli episodi osservati di alta varianza.

[Bollerslev (1986)](https://doi.org/10.1016/0304-4076(86)90063-1). Hash, versioni, partenze e parametri in garch_model.json. Comandi e pagina HTML in README.md.
