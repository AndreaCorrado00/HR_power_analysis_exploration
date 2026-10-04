# Parametri dell'atleta e previsione HR

Protocollo storico v1, approvato nella conversazione del 29 settembre 2026.

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


## Protocollo v2 - inizializzazione osservata e B locale (30 settembre 2026)

Estensione approvata: scelta nella pagina Popolazione, persistita in
`config.prediction_mode`. Il fitting train non cambia. Le analisi storiche senza
questo campo mantengono il protocollo v1 (`legacy_power_only`); la UI propone
`observed_hr` per nuove analisi.

- `observed_hr`: K,L,tau,B congiunti di popolazione; HR(0) osservata e
  x(0)=HR(0)-B_pop. Nessun fitting sul segmento test.
- `local_B_10s`: K,L,tau congiunti di popolazione, B escluso da REML e dalle
  statistiche di popolazione. Con questi parametri fissi si stima B locale in
  bpm per minimi quadrati limitati ai bounds B originali, su campioni HR finiti
  in [0,10 s). HR(0) viene osservata, x(0)=HR(0)-B_locale. La traiettoria risulta affine
  in B con sensibilita 1-exp(-t/tau), quindi si usa la soluzione analitica
  vincolata. Non si assume che la media HR della finestra sia un equilibrio.

Questa e una calibrazione proposta nel progetto, non una replica bibliografica.
P0 e gestione della potenza restano quelli della run. La pre-window [-10,0)
per P0 e distinta dalla finestra [0,10) di calibrazione. Nessuna nuova covariata.
La HR iniziale deve essere finita; calibrazione locale con almeno tre campioni
finiti, sensibilita non nulla e segmento con dati a t>=10 s. Nessun fallback.
Il livello B resta riferito a P0: non rappresenta una HR a riposo.

In modalita locale lo screening marginale e le correlazioni locali usano solo
K,L,tau e la sottomatrice della covarianza originale. I controlli globali di
rango e ambiguita multistart del fit originale restano conservativi: escludere
B dalla popolazione non rende automaticamente identificabile il fit train.

Entrambe le nuove modalita sono valutate solo a t>=10 s, senza reset dello
stato e senza usare HR futura. Baseline costante pari al B usato. Per confronti
usare l'intersezione dei segmenti previsti con successo, riportando i fallimenti.
I primi 10 s nei grafici sono inizializzazione/calibrazione, non validazione.
Split congelato, nessun utilizzo della validation per questa procedura.

Per ogni estrazione K,L,tau si ricalibra B sulla stessa finestra. Le fasce sono
condizionate ai dati iniziali: non includono rumore HR, incertezza della media
di popolazione ne l'incertezza residua di B. La SE locale di B usa una formula Wald
condizionata a HR(0), K,L,tau, con varianza residua SSE/(n-1); autocorrelazione,
bounds e HR(0) rumorosa ne limitano la validita. Segnalati bounds attivi,
CI con semiampiezza oltre |B| e sensibilita massima nella finestra inferiore
al 50% (criterio operativo di finestra breve, non soglia fisiologica).

Verifiche: recupero sintetico di B, indipendenza dalla HR successiva, mancanti,
bounds, L fissato, persistenza API, UI e report. Decisioni e parametri di
calibrazione vengono salvati insieme alle predizioni.

## Revisione descrittiva delle predizioni (1 ottobre 2026)

Ogni giudizio manuale è associato a ID analisi e ID segmento: non valutata,
positiva o negativa. Le negative possono avere più etichette descrittive;
le note libere descrivono quanto osservato, senza attribuire cause fisiologiche.
Le etichette sono: ritardo della HR osservata rispetto alla prevista,
sovrastima sistematica, sottostima sistematica, HR osservata piatta,
escursioni previste eccessive, divergenza progressiva, transizioni o recuperi
mal riprodotti. Non è prevista l'etichetta «HR prevista troppo piatta».

Il salvataggio esplicito conserva giudizio, etichette, note e data UTC in
`runs/<run>/population/<analysis>.reviews.json`, separato dallo snapshot
scientifico immutabile. Una nuova analisi parte senza giudizi; quelli precedenti
restano conservati. Le richieste con ID analisi superato sono rifiutate.
La classificazione non modifica fitting, metriche, screening o split.
Le bozze non salvate sono recuperate tramite sessionStorage quando si naviga
tra le pagine nella stessa sessione browser; non sono incluse negli export
finché non viene premuto «Salva osservazione».

Ogni metrica di errore usa min e max finiti dell'intero test set dell'analisi
salvata: minimo verde, massimo rosso, interpolazione RGB lineare. Il bias usa
il valore assoluto per il colore ma conserva il segno (osservata meno prevista).
Parità completa e valori mancanti sono neutri. La scala è relativa: il verde
non certifica una previsione accettabile. La copertura resta descrittiva.

Pagina e export condividono colori, legenda e avvisi calcolati dai bounds
salvati e dal protocollo predittivo. Un parametro è fisso solo se i bounds
inferiore e superiore coincidono, non perché la varianza stimata sia zero.
Con L=0 si esplicita la forma senza ritardo. B resta un livello riferito a P0,
costante nel segmento, senza interpretazione di HR a riposo. Si distinguono
B di popolazione, B locale calibrato e inizializzazione storica all'equilibrio.

Gli export JSON e PDF della revisione sono salvati in `runs/<run>/exports/`
e scaricabili. Il JSON conserva analisi, provenienza, serie numeriche, giudizi
e convenzioni; il PDF comprende solo analisi dei parametri e predizioni,
con etichette, note e tracce HR/potenza/residui. Nessun refit all'esportazione.
Gli assi temporali mostrano durate hh:mm:ss, anche oltre 24 ore; i valori
numerici delle serie JSON rimangono in secondi.

## Protocollo v2.1 - scelta della calibrazione in inferenza (1 ottobre 2026)

Decisione approvata: l'identificazione train resta invariata, con K, L, tau e B
identificati sull'intero segmento disponibile. La scelta 10/180 secondi riguarda
soltanto B locale in inferenza, dopo aver stimato i parametri di popolazione.
Non si modifica il fitting train, lo split o i dati sorgente.

La pagina Popolazione offre `local_B_10s` e `local_B_180s`; per nuove analisi
senza risultati salvati propone 180 s. Le analisi gia salvate mantengono la loro
modalita. L'assenza di prediction_mode continua a significare legacy_power_only
per compatibilita con le analisi e i client storici.

Con T pari a 10 o 180 s si applica la medesima calibrazione analitica del
protocollo v2 usando soltanto i campioni HR finiti in [0,T), con K,L,tau fissi,
HR(0) osservata e bounds B della run. B resta costante per il resto del segmento;
nessun reset dello stato a T e nessun utilizzo della HR successiva nella previsione.
Le estrazioni per le fasce ricalibrano B sulla stessa finestra T. Un segmento
senza campioni a t>=T viene segnalato come fallito, senza accorciare la finestra
automaticamente. Restano necessari almeno tre campioni HR finiti nella finestra,
HR(0) finita e sensibilita non nulla; non si introducono interpolazioni.

Metriche e fascia di calibrazione dei grafici iniziano rispettivamente a T e
in [0,T); durata e campioni di calibrazione sono salvati insieme alle predizioni.
JSON, revisione e PDF dichiarano la durata selezionata. observed_hr conserva il
protocollo precedente, con valutazione da 10 s. Per confrontare finestre diverse
occorre ricalcolare le metriche su una coda comune (per esempio t>=180 s): i
riepiloghi standard delle due modalita usano tratti diversi e non sono direttamente
un confronto a parita di campioni.

La scelta di 180 s deriva dal confronto esplorativo documentato in
`milestone_artifacts/reports/P1D_first_full_dataset_run/B_calibration_comparison/README.md`
nella branch `milestone/2026-10-04-hr-power` (commit `c95496e`), non da
una nuova fonte bibliografica o da una garanzia di robustezza su altri dati.
Le assunzioni e i limiti della calibrazione e delle fasce restano quelli di v2.
