# Esperimento comune potenza–HR, 17 ottobre 2026

Scope approvato: ristima sui 60 workout prescribed, split cronologico comune
42 train / 9 validation / 9 test, pagina HTML locale e Monte Carlo. Riordino
della repository e test sul campo sono successivi. Test retrospettivo già
consultato storicamente, non una nuova conferma indipendente. Target ricostruiti
dalle medie osservate, non prescrizioni esterne indipendenti.

## Dati e split

Fonte immutata: data/processed/prescribed_workouts_final/samples/*.csv.gz.
Ordinamento per primo timestamp UTC, poi workout ID. Split a livello attività.
Hash delle sorgenti e appartenenze persistiti nel manifest. Nessuna interpolazione,
filtro o resampling. Riutilizzo dei tratti validi di power_response (campioni
consecutivi a 1 s, pause/gap/target mancanti interrompono il tratto; nessun reset
ai lap o ai cambi target). Potenza stimata su tutti questi tratti.
Per HR: tratti di durata almeno 300 s, come soglia del dataset HR precedente.
Nel train, HR mancante interrompe il tratto e la soglia si riapplica; fuori train
HR serve solo al confronto, non modifica tratti, inizializzazione o simulazione.
Esclusioni e copertura sono quantificate, non interpretate fisiologicamente.

## Modelli congelati prima del test

Potenza: P=max(0,target+G_n(q^-1) delta(target)+e), n in {2,3,4};
e_t=c+phi1 e_(t-1)+phi2 e_(t-2)+epsilon_t. Pipeline esistente del progetto,
non nuova replica bibliografica. Fit dinamico LS a peso uguale per workout,
6 start, 250 valutazioni; ordine selezionato sulla validation con regola
un SE appaiato esistente. AR(2) OLS sui residui train; stato iniziale stazionario,
clipping solo in uscita. Baseline: target. Unità W, tempo s.

HR: tau dx/dt+x=K(P(t-L)-P0), HR=B+x; fitting train con HR iniziale osservata,
x(0)=HR(0)-B. P1D già implementato, adattamento del progetto, nessuna nuova
replica bibliografica rivendicata. K bpm/W, L/tau s, B bpm. Bounds ripresi
dalla run dello stesso atleta a6c56bc0: K [1e-6,5], L [0,30], tau [.01,1800],
B [60,200]. Ricerca profile_multistart 301x141, 8 raffinamenti + 8 start,
500 valutazioni, seed 42, LS TRF. Fit indipendente per tratto train.
REML multivariata a due stadi con covarianze locali dei fit, screening esistente
RSE 100%, correlazione .98, esclusione bound/ambiguità. Nessun allentamento
automatico delle soglie se insufficienti. Dipendenza tra tratti dello stesso
workout resta un limite del modello REML esistente.

Predizione HR: modalità esistente population_B_P0_mean_HR0:
A=media train(B-K_pop P0), B=A+K P0; HR0=media HR iniziali dei tratti train.
Nessuna HR di validation/test usata, nemmeno al tempo zero. Nessuna selezione
tra modalità che richiedono osservazioni HR future. Baseline statica OLS
HR=beta0+beta1 P stimata sui medesimi campioni HR train, peso per campione.
Confronti: HR da potenza reale, da prescrizione diretta e da potenza simulata.

Monte Carlo: 1000 traiettorie AR, parametri HR congiunti N(media,Omega),
accettati entro bounds con limite 20*1000 estrazioni; seed 42, stream separati.
Indipendenza assunta tra rumore potenza e parametri HR. Parametri HR costanti
nel tratto, reset soltanto ai confini dichiarati. A e HR0 restano fissi;
non si simulano rumore HR residuo né incertezza delle medie, di A/HR0 o dei
coefficienti potenza. Fasce puntuali 2.5–97.5% di variabilità parziale, non
intervalli predittivi completi né simultanei. Centro catena: media Monte Carlo.

## Verifiche e restituzione

MAE, RMSE, bias (osservato-predetto), SD residui, copertura e larghezza fasce.
Metriche HR sull'intero tratto e separatamente primi 180 s/coda >=180 s,
quest'ultima per confronto con il protocollo HR esistente. Aggregati per
workout con peso uguale; conteggi e fallimenti sempre visibili. Metriche potenza
su tutti i tratti validi; confronto catena su supporto HR comune dichiarato.
Pagina offline con selettori split/workout/tratto, zoom, serie complete,
residui e metriche. Artefatti nuovi separati dagli esperimenti precedenti.

## Piano operativo

1. Test e implementazione adattatore dati, split, QC e manifest con hash.
2. Ristima potenza tramite CLI esistente in output dedicato; fit HR resumibili
   per tratto, REML e baseline, nessun riuso di stime storiche.
3. Test di equivalenza simulatore/assenza feedback; Monte Carlo e metriche
   validation, congelamento modello, poi test descrittivo.
4. HTML locale, report, verifiche numeriche e browser; rendicontazione limiti.

Componenti nuovi: experiments/prescribed_joint/{data,run,simulation,viewer}.py,
index.html, app.js; tests/test_prescribed_joint.py. Output in results/.
Si riutilizzano power_response_estimation e backend HR senza modificarli.
