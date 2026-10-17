# Varianza iniziale/finale delle innovazioni AR

Modelli congelati; train e validation separati, test escluso. Stessi eventi osservati da tau0 a120s senza nuovi salti/gap.
Finestre0-19 e100-119s. A ogni tau si centra l'errore sulla media FRA eventi, non sulla media temporale della finestra.
Pooled: varianza campionaria fra tutti gli eventi a tau fisso, poi media sui20 tau per finestra.
Stratified: centratura separata per direzione e ampiezza (<25,25-75,75-150,>=150 W), somma SSE/somma gradi di liberta;
celle originarie con meno2 eventi escluse anche da tutti i bootstrap; celle ricampionate con meno2 eventi escluse dalla varianza.
La composizione iniziale/finale e identica. Eventi ammissibili e contribuenti distinti nella tabella.
Up/down: sensibilita descrittiva per direzione. Eventi hanno ugual peso prima della correzione dei gradi di liberta.
10000 bootstrap con ricampionamento di workout interi, mantenendo abbinamento iniziale/finale e tutte le dipendenze interne.
IC95% percentile del rapporto; p unilaterale approssimato da distribuzione bootstrap centrata di log(rapporto),
H0 rapporto=1 contro rapporto>1. Non e un test esatto; pochi workout e code pesanti limitano la calibrazione.
Workout trattati come cluster indipendenti: eventuale dipendenza fra sessioni non modellata.
Leave-one-workout-out per sensibilita. Analisi per direzione secondarie, nessuna correzione multipla: IC e robustezza hanno priorita.
Finestre suggerite dal grafico gia osservato: approfondimento sui dati esistenti, non conferma indipendente.
Un risultato positivo supporta una differenza iniziale/finale, non monotonicita, forma esponenziale o causalita del salto.
Fonte per inferenza cluster: Cameron & Miller2015 doi:10.3368/jhr.50.2.317; statistica specifica adattata a questa analisi.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.transition_variance_test

## Proposta da testare, non implementata ne fittata

Estensione esplorativa del GARCH con due scale di varianza note dal target:
v(tau)=v_P*[1+kappa*I(0<=tau<T)], h_t=v(tau_t)*g_t,
g_t=(1-alpha-beta)+alpha*[epsilon_(t-1)^2/v(tau_(t-1))]+beta*g_(t-1).
v_P>0 in W², kappa>=0 adimensionale, alpha,beta>=0,alpha+beta<1; E[g]=1 sotto le assunzioni gaussiane.
Innovazione epsilon_t=sqrt(h_t)*z_t con z indipendente N(0,1). Dinamica ordine4 e AR congelati.
Input aggiuntivi solo derivati dal target: eta dall'ultimo salto. Ai gap eta non nota: inizializzazione da dichiarare separatamente,
senza inventare un salto. T=30s candidato fissato dal protocollo precedente, NON stimato o dimostrato dal test iniziale/finale.
Scopo: separare scala plateau e maggiorazione transiente dalla persistenza stocastica g.
Fitting eventuale Gaussian QML solo train; prima verificare varianza plateau e transiente empirica e identifiabilita.
Confronto validation con GARCH targeted (kappa=0) e scala a due livelli senza GARCH (g=1).
Metriche: SD interna lap, coverage/interval score per fase, NLL a un passo; simulazione autonoma senza feedback osservato.
Non imporre esponenziale o asimmetria salita/discesa da questi risultati: analisi direzionali secondarie e campione piccolo.
Questa e una proposta specifica del progetto, non una dinamica fisiologica o un modello ciclistico validato.

| split | mode | eligible_events | contributing_events | workouts | early_variance | late_variance | early_sd | late_sd | variance_ratio | ci95_low | ci95_high | p_one_sided_approx | bootstrap_valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train | pooled | 176 | 176 | 36 | 3709 | 2486 | 60.9 | 49.86 | 1.492 | 1.063 | 2.128 | 0.0137 | 10000 |
| train | stratified | 176 | 176 | 36 | 3593 | 2496 | 59.94 | 49.96 | 1.439 | 1.034 | 2.032 | 0.0193 | 10000 |
| train | up | 90 | 90 | 33 | 3850 | 2676 | 62.05 | 51.73 | 1.439 | 0.9601 | 2.317 | 0.06829 | 10000 |
| train | down | 86 | 86 | 30 | 3499 | 2295 | 59.15 | 47.91 | 1.524 | 0.9893 | 2.375 | 0.0321 | 10000 |
| validation | pooled | 67 | 67 | 12 | 3133 | 1734 | 55.98 | 41.64 | 1.807 | 0.9989 | 3.504 | 0.0457 | 10000 |
| validation | stratified | 67 | 66 | 12 | 3094 | 1736 | 55.63 | 41.67 | 1.782 | 0.9389 | 3.465 | 0.05169 | 10000 |
| validation | up | 36 | 36 | 10 | 4042 | 1771 | 63.58 | 42.09 | 2.282 | 1.198 | 4.387 | 0.0023 | 10000 |
| validation | down | 31 | 31 | 11 | 2059 | 1675 | 45.38 | 40.93 | 1.229 | 0.7057 | 2.41 | 0.2705 | 10000 |

## Sensibilita leave-one-workout-out

| split | mode | min | max |
|---|---|---|---|
| train | down | 1.396 | 1.676 |
| train | pooled | 1.384 | 1.605 |
| train | stratified | 1.34 | 1.553 |
| train | up | 1.308 | 1.651 |
| validation | down | 0.9961 | 1.672 |
| validation | pooled | 1.366 | 2.417 |
| validation | stratified | 1.309 | 2.428 |
| validation | up | 1.619 | 3.058 |
