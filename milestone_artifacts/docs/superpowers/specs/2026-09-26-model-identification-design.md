# Identificazione HR–Power: specifica concordata

Autorizzazione: conversazione del 26 settembre 2026. L'utente autorizza la
costruzione della SPA e assume equilibrio iniziale; il recupero della storia
dal FIT è rinviato. Nessuna nuova covariata o interpretazione fisiologica.

## Perimetro

SPA locale Vue/ECharts con backend Python/SciPy in
`webapp/model_identification_app`. Quattro pagine: dataset, identificazione,
analisi e confronto. I dati raw restano immutati. Implementazione isolata in
questa directory, documentazione progettuale in docs; nessuna modifica alla
precedente app. Esecuzione nella workspace richiesta dall'utente.

Import di ZIP con CSV/manifest e CSV singoli o multipli, da repository o upload.
Dataset persistenti rinominabili. Sottoinsiemi G1/G2 e UtD/DtU/Ambigui, anche
combinati; attributi sconosciuti espliciti. Durata = ultimo meno primo tempo,
SD campionaria (non definita con un solo segmento). Split deterministico
70/10/20, seed 42, per segmento o attività. Nessuno split di campioni. In caso
di segmenti sovrapposti della stessa attività impedire split per segmento;
usare split per attività. Percentuali richieste ed effettive visibili.

## Contratto scientifico P1D v1

Modello richiesto dall'utente, non rivendicato come replica di uno specifico
articolo: tau dx/dt + x = K (P(t-L)-P0), HRhat = HR0+x.
P0=P(0), HR0=HR(0), x(0)=0 e P(t<0)=P0. Tre parametri K [bpm/W], L [s], tau [s].
Assunzione esplicita di equilibrio iniziale, nessuna stima aggiuntiva dell'offset.
Selezione esplicita di colonne originali o medie mobili (solo se disponibili).
Nessun preprocessing aggiuntivo. Potenza mantenuta costante tra campioni
(zero-order hold); integrazione esatta del primo ordine e ritardo continuo,
senza arrotondare L a campioni e senza interpolare i dati osservati.

Least squares TRF, loss lineare/SSE, Jacobiano numerico a 3 punti, tolleranze
1e-8, max_nfev=500 di default. Bounds editabili, default K=[1e-6,5],
L=[0,120], tau=[0.01,1800]; sono limiti numerici, non intervalli fisiologici.
Multistart deterministico (8 inizializzazioni, seed configurabile), punti
iniziali e soluzioni salvati. Una stima indipendente per segmento train.

Metriche in-sample: RMSE, SSE, bias, SD campionaria dei residui, ACF lag1
sum(e_centered[1:]*e_centered[:-1])/sum(e_centered**2).
Cov = SSE/(N-3) inv(J'J), calcolata via SVD equivalente quando rango pieno;
SE, CI95 simmetrici non troncati e RSE. Covarianza non disponibile in caso di
rango insufficiente. Segnalare bounds attivi, condizionamento, autocorrelazione,
dispersione multistart, input costante e irregolarità/gap. Non eliminare anomalie
automaticamente; campioni non finiti/tempi non crescenti impediscono quel fit.
Le CI sono locali e condizionate a P0/HR0; autocorrelazione, bounds e cattiva
identificabilità ne limitano l'interpretazione. Non inferire capacità predittiva.
Validation/test sono soltanto assegnati e non usati. Baseline statica e
validazione fuori campione rinviate esplicitamente da questo esperimento.

## Persistenza e interfacce

Storage locale sotto l'app, percorso opzionale da CLI. JSON atomici, copie
immutabili dei CSV, hash SHA256 e manifest sorgente. Run asincrone a singolo
worker; manifest salvato prima del fit, aggiornamento stato/progresso persistito.
Al riavvio run incomplete marcate interrotte, risultati parziali recuperabili.
Manifest: snapshot dataset/split, filtri, colonne, modello/versione/equazione,
assunzioni, bounds, solver, seed, multistart, ambiente e hash del codice.
Nome leggibile: UTC__dataset__modello__split__seed__id.json.
Eliminazione esplicita: conservare solo manifest in archived_manifests,
rimuovere risultati della run, mantenere dataset necessari alla riproduzione.
Riesecuzione da manifest conservando impostazioni e split originali.

Registry backend con contratto metadata/config/fit e registry frontend per
analisi/confronto modello-specifici. P1D è l'unico modello iniziale. Confronto
tra due run, parametri soltanto se nome/unità compatibili; mostrare differenze
di dataset/split e campioni, senza sostenere confronti predittivi.
Grafici train paginati, tutti accessibili: HR osservata/prevista e potenza su
asse separato sopra, residui sotto. Boxplot con outlier e numerosità.

## Verifiche

Risposta analitica a gradini con ritardo frazionario e tempi irregolari;
recupero parametri sintetici; covariance/rango, input costante e bounds.
Import ZIP/CSV reali, filtri, gruppi, split ripetibile e sovrapposizioni.
API end-to-end: manifest prima del fit, solo train, recupero dopo riavvio,
rinomina senza modificare run storiche, replay e archiviazione solo manifest.
Build frontend, test delle trasformazioni grafiche e smoke test browser.
