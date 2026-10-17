# Confronto della varianza: train e validation

Fit solo train; validation fuori dal fitting. Test escluso: non caricato e non valutato.
Le osservazioni dell'utente che motivano questo confronto non provengono dal test.
Media dinamica e AR congelati. Baseline costante e GARCH originale congelati.
Variance targeting: omega=(1-alpha-beta)*mean(epsilon_train²), Gaussian QML multistart.
Contesto (nuova proposta esplorativa, non modello ciclistico pubblicato):
log(h/W²)=b0+b1*target/100W+b2*abs(ultimo salto)/100W*exp(-eta/30s).
Coefficienti adimensionali, segni liberi; fit Gaussian QML. 30 s fissati prima del fit.
Nessun salto iniziale inventato: transiente nullo fino alla prima variazione nel segmento.
Reset ai gap reali; innovazioni disponibili dopo p campioni; nessun collegamento ACF/ARCH fra gap.
Simulazioni gaussiane libere: 1000 traiettorie per segmento, seed SHA256(workout:segment), nessun feedback osservato.
GARCH inizializzato con warm-up stazionario; contesto/costante con stato AR stazionario per h iniziale.
Gli intervalli sono quantili marginali 10%-90%, non bande simultanee per intere traiettorie.
Metriche aggregate: media con peso uguale per workout, anche nelle fasce; numerosita riportate.
Jump: ampiezza dell'ultimo salto (<25,25-75,75-150,>=150 W); fase: primi30s o plateau.
La fascia del salto persiste fino al salto successivo: non classifica l'intero workout.
Intervalli di confidenza parametrici non stimati; resta da valutare stabilita tra workout e sensibilita ai30s.
ARCH p-value nominali, diagnostici; nessuna selezione tramite significativita multipla.
Fonti: Engle1982 doi:10.2307/1912773; Francq et al.2011 Merits and Drawbacks of Variance Targeting;
Gneiting e Raftery2007 doi:10.1198/016214506000001437.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.variance_comparison

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

## Validation: confronto appaiato delle bande libere

| model | delta_score_vs_constant | improved_workouts | workouts |
|---|---|---|---|
| garch | 10.47 | 1 | 12 |
| targeted | -13.37 | 9 | 12 |
| context | -1.088 | 7 | 12 |

Variance targeting: persistenza=0.984662; varianza incondizionata=3180.462 W?; fattore quarto momento gaussiano=1.003983. Quarto momento non finito nel modello: cautela sulle code e sulla stabilita Monte Carlo.

Parametri del contesto [b0,b1,b2]: [6.989297577059605, 0.4938885749314982, 0.0036019737422567535].

## Validation per fase e salto

| band | model | workouts | n | coverage80 | width80_w | interval_score80_w |
|---|---|---|---|---|---|---|
| plateau | constant | 12 | 33997 | 0.8913 | 234.3 | 295.8 |
| plateau | context | 12 | 33997 | 0.8752 | 222 | 290.5 |
| plateau | garch | 12 | 33997 | 0.9083 | 255.4 | 307 |
| plateau | targeted | 12 | 33997 | 0.8554 | 194.4 | 281.5 |
| start | constant | 12 | 49211 | 0.8935 | 234.3 | 294.1 |
| start | context | 12 | 49211 | 0.878 | 215.5 | 285.6 |
| start | garch | 12 | 49211 | 0.91 | 255.7 | 305.4 |
| start | targeted | 12 | 49211 | 0.8572 | 194.2 | 278.5 |
| transition | constant | 12 | 8388 | 0.8112 | 234.4 | 377.8 |
| transition | context | 12 | 8388 | 0.8255 | 261.2 | 390.4 |
| transition | garch | 12 | 8388 | 0.8485 | 255 | 380.5 |
| transition | targeted | 12 | 8388 | 0.7507 | 194.3 | 382.1 |

| band | model | workouts | n | coverage80 | width80_w | interval_score80_w |
|---|---|---|---|---|---|---|
| 0-25 | constant | 3 | 2509 | 0.9002 | 234.2 | 269.7 |
| 0-25 | context | 3 | 2509 | 0.8845 | 209.2 | 257.2 |
| 0-25 | garch | 3 | 2509 | 0.9218 | 257.7 | 283.2 |
| 0-25 | targeted | 3 | 2509 | 0.8639 | 193.7 | 252.5 |
| 150+ | constant | 9 | 14706 | 0.8737 | 234.4 | 322.8 |
| 150+ | context | 9 | 14706 | 0.8755 | 258.7 | 332.3 |
| 150+ | garch | 9 | 14706 | 0.8943 | 255.4 | 331.7 |
| 150+ | targeted | 9 | 14706 | 0.8191 | 194.3 | 314.2 |
| 25-75 | constant | 8 | 13058 | 0.906 | 234.2 | 284.6 |
| 25-75 | context | 8 | 13058 | 0.8966 | 218 | 274.4 |
| 25-75 | garch | 8 | 13058 | 0.9187 | 255 | 296.8 |
| 25-75 | targeted | 8 | 13058 | 0.8772 | 194.5 | 266.1 |
| 75-150 | constant | 9 | 12111 | 0.8408 | 233.9 | 332.1 |
| 75-150 | context | 9 | 12111 | 0.8387 | 239.4 | 341.7 |
| 75-150 | garch | 9 | 12111 | 0.8637 | 256.2 | 337.7 |
| 75-150 | targeted | 9 | 12111 | 0.8035 | 194.7 | 327.6 |
| unknown | constant | 12 | 49211 | 0.8935 | 234.3 | 294.1 |
| unknown | context | 12 | 49211 | 0.878 | 215.5 | 285.6 |
| unknown | garch | 12 | 49211 | 0.91 | 255.7 | 305.4 |
| unknown | targeted | 12 | 49211 | 0.8572 | 194.2 | 278.5 |

## ARCH-LM validation dopo standardizzazione

P-value nominali <0.05; conteggi diagnostici, non corretti per confronti multipli.

| model | lag | significant | workouts |
|---|---|---|---|
| constant | 5 | 12 | 12 |
| constant | 15 | 12 | 12 |
| constant | 30 | 12 | 12 |
| context | 5 | 12 | 12 |
| context | 15 | 12 | 12 |
| context | 30 | 12 | 12 |
| garch | 5 | 7 | 12 |
| garch | 15 | 4 | 12 |
| garch | 30 | 3 | 12 |
| targeted | 5 | 10 | 12 |
| targeted | 15 | 5 | 12 |
| targeted | 30 | 4 | 12 |

La riduzione globale delle bande va verificata sulle transizioni: una copertura inferiore all’80% indica sottocopertura. Il contesto non sostituisce automaticamente la memoria degli errori: osservare la diagnostica standardizzata. Le fasce con pochi workout non consentono conclusioni altrettanto robuste. Il viewer arrotonda a 0.001 W/W² (ACF a 6 decimali); CSV e metriche conservano la precisione originale.
