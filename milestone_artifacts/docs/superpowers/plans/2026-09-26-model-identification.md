# Model Identification Implementation Plan

> Esecuzione inline autorizzata dall'utente: costruire l'app concordata.

**Goal:** identificare P1D sui segmenti train con run persistenti riproducibili.
**Architecture:** Vue + ECharts, API FastAPI, moduli numerici e storage JSON.
**Tech Stack:** Python, NumPy, SciPy, FastAPI, Vue, TypeScript, ECharts.
**Spec:** docs/superpowers/specs/2026-09-26-model-identification-design.md

## Vincoli globali

Equilibrio iniziale approvato; tre soli parametri; train-only. CSV immutati;
filtri G/classi espliciti; nessuna modifica all'app di esplorazione.
L'autorizzazione a iniziare supera ulteriori passaggi di approvazione del piano.

## Task e verifica

- [x] 1. Test numerici, poi `backend/models/p1d.py`: risposta esatta ZOH,
  ritardo continuo, multistart e covariance con diagnostica di identificabilità.
  Test: confronto con somma analitica di gradini, recupero parametri noti,
  degenerazione e CI. Interfacce `simulate(t,p,hr0,theta)`, `fit(t,p,hr,config)`.
- [x] 2. Test import/split, poi `backend/datasets.py` e `backend/storage.py`:
  CSV/ZIP, hash/provenienza, filtri, rinomina, split per segmento/attività.
  Test: gruppi misti, overlap, percentuali invalide, reload su stesso storage.
- [x] 3. Test ciclo run/API, poi `backend/runs.py`, `backend/app.py`:
  worker seriale, manifest atomico anticipato, fit solo train, replay,
  interruzioni e archiviazione. Test usando TestClient e directory temporanee.
- [x] 4. `src/pages/*`, `src/models/*`, componenti grafici, stili e bootstrap:
  quattro pagine, proprietà prima del lancio, tutti i fit e boxplot, confronto.
  Test trasformazioni boxplot e build TypeScript/Vite; controllo browser.
- [x] 5. README, avvio PowerShell, verifica completa e revisione finale.

## Casi da coprire

ZIP malevoli/duplicati e path unsafe; filtri senza risultati; split piccoli;
parametri non identificabili; fallimento di un segmento senza perdita della run;
riavvio durante fit e cancellazione con manifest conservato; cambiamenti al
dataset dopo una run; manifest replay con codice differente segnalato.

## Comandi

`.venv/Scripts/python -m pytest webapp/model_identification_app/tests`
e `npm run build`, `npm test` dalla directory dell'app. Suite Python repository
con basetemp dedicata se le directory temporanee preesistenti sono inaccessibili.

## Esito della verifica (26 settembre 2026)

85 test Python passati, 1 saltato nella suite del repository; 13 dei test
riguardano la nuova app. 5 test frontend passati; build TypeScript/Vite riuscita.
Revisione indipendente: risolti bypass overlap in assenza di activity_id e race
Windows tra download e aggiornamento manifest. Nessuna modifica fuori scope.
Browser UI non verificabile: nessun browser disponibile tramite il connettore;
verificati in alternativa i componenti Vue (jsdom), la build e le API reali.
Warning non bloccanti: deprecazione httpx del TestClient upstream; bundle ECharts
oltre 500 kB minificati. La build è locale e non richiede CDN.

Prova dati reali in storage separato: import 215 segmenti G1/G2, filtro G1 UtD
56 segmenti (56.732 ± 12.023 s). Lo split per segmento è rifiutato correttamente
per sovrapposizioni presenti nei sorgenti. Tre segmenti reali della stessa
attività, split per attività, sono tutti assegnati a train (un solo gruppo,
validation/test vuoti dichiarati): tre fit completati e recuperati al riavvio.
La prova verifica l'integrazione e non è una valutazione scientifica del dataset.
Residui autocorrelati/disaccordo multistart rilevati e riportati, senza nasconderli.
