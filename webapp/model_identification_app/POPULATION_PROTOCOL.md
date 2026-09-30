# Parametri dell'atleta e previsione HR

Protocollo v1, approvato nella conversazione del 29 settembre 2026.

## Obiettivo e dominio

La popolazione è quella dei parametri tra segmenti dello stesso atleta, non tra
atleti. La pagina opera su una singola run P1D `estimated_equilibrium`, protocollo
`segment_v2`. Non mescola strutture, inizializzazioni o run. Nessuna interpretazione
fisiologica dei parametri. Input: fit train e covarianze salvate, split congelato,
potenza dei segmenti test; HR test serve esclusivamente a confronto e metriche.

## Modello a due stadi

theta_j = theta_sub + nu_j, nu_j ~ N(0, Omega).
theta_hat_j | theta_j ~ N(theta_j, S_j), dove S_j è la covarianza locale del fit.
Quindi theta_hat_j ~ N(theta_sub, Omega + S_j).

Media e covarianza multivariata sono stimate con REML, profilando la media GLS.
Omega = A A' garantisce semidefinitezza positiva; la scala numerica interna è
invertita prima di pubblicare i risultati. Due inizializzazioni deterministiche
e confronto con Omega=0. Nessuna garanzia di ottimo globale. CI95 della media:
Wald, condizionati alle covarianze stimate, senza incertezza di Omega.

Fonte metodologica: modello normale di effetti casuali multivariati,
https://wviechtb.github.io/metafor/reference/rma.mv.html . Implementazione Python
locale; non è una replica di un modello fisiologico pubblicato né una stima
non lineare mixed effects congiunta sui segnali.

Unità: K bpm/W, L e tau secondi, B bpm. Omega ha prodotti delle rispettive unità.
Gaussianità assunta sulla scala originale; istogrammi e Q-Q plot ne consentono
la verifica descrittiva. Le correlazioni delle stime tra segmenti sono distinte
dalle correlazioni degli errori di stima entro un fit e da quelle di Omega.

## Identificabilità e selezione

I risultati originali non vengono modificati. Per ciascuna stima si registrano
esclusioni per fit fallito, rango non pieno, covarianza non valida, SE non valida,
bound attivo, RSE oltre soglia o correlazione locale assoluta oltre soglia.
Soluzioni multistart equivalenti con parametri diversi escludono il vettore.
Soglie iniziali conservative e configurabili: RSE 100%, correlazione 0.98;
near-bound è segnalato, esclusione opzionale. Sono scelte operative, non soglie
universali di identificabilità. Un parametro fissato esplicitamente nei bounds
ha varianza zero e non viene trattato come una stima precisa.

Le distribuzioni marginali mostrano tutti i valori e quelli affidabili; REML
usa solo vettori completi affidabili per preservare la covarianza congiunta.
Sono richiesti almeno max(5, p+2) vettori, p numero di parametri liberi: controllo
minimo numerico, non garanzia di sufficiente potenza statistica. Se non bastano,
nessun riempimento o fissaggio arbitrario. Tutte le esclusioni restano visibili.

S_j è una stima locale di Wald: autocorrelazione, non linearità e selezione dei
fit possono distorcere i risultati. L'indipendenza tra segmenti è un'assunzione;
segmenti della stessa attività producono un avviso, non un nuovo livello random.
La selezione può restringere la popolazione ai segmenti identificabili.

## Previsione congelata sul test

tau dx/dt + x = K [P(t-L)-P0]; HR_hat = B+x; x(0)=0, HR_hat(0)=B.
Si assume equilibrio iniziale. La traiettoria centrale usa theta_sub.
Nessun valore HR del test, inclusa HR(0), inizializza o modifica la traiettoria.
P0 è la media della potenza in [-10,0) quando la run richiede pre-window,
altrimenti il primo campione di potenza. Si usa lo stesso ZOH del simulatore.
Le pre-window non sono previste né valutate. Nessuna interpolazione dei gap.

Campionamento congiunto da N(theta_sub, Omega), seed e numero persistenti.
La normale può uscire dal dominio: vengono accettati solo campioni nei bounds
configurati, con quota di accettazione esplicita. L senza limite superiore
configurato non è limitato alla durata test (un ritardo più lungo è simulabile).
La fascia 2.5%-97.5% è quindi CONDIZIONATA al dominio ammissibile: non è una
normale non troncata, né un intervallo predittivo completo di HR. Non include
rumore residuo o incertezza dei parametri di popolazione. Se entro 20*n estrazioni
non si ottengono n campioni validi, nessuna fascia viene pubblicata.

Metriche per segmento: MAE, RMSE, bias, SD residui e copertura della fascia;
baseline di riferimento HR costante = B_sub. HR mancante resta mancante e viene
contata; non modifica le previsioni. Fallimenti di potenza/tempo vengono riportati.
Il confronto principale è la traiettoria ai parametri medi; la fascia aggiunge
informazione sulla variabilità, non promette un miglioramento dell'errore medio.
Holdout per attività preferito; split per segmento esplicitamente etichettato.
Soglie scelte sul train: cambiarle dopo aver consultato il test rende esplorativa
la valutazione ripetuta. Val non viene utilizzato da questa procedura.

## Persistenza e verifiche

Ogni analisi conserva config, split, hash dei risultati sorgente, versione,
ambiente/codice, esclusioni, stime e traiettorie. Gli snapshot precedenti restano
in runs/<id>/population; analysis.json indica l'ultima analisi. Replay della run
non riutilizza analisi precedenti. PDF e ZIP incorporano l'analisi salvata senza
ricalcoli o refit. Verifiche: REML su caso analitico, esclusioni e parametri fissi,
assenza di dipendenza da HR test, integrazione API/persistenza/export, build UI
e controllo visivo del PDF.
