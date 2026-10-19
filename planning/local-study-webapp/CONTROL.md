# Controllo del perimetro

Stato al 18 ottobre 2026: implementazione autorizzata dall'utente, esecuzione inline.
Nessun fitting o ristima autorizzato all'agente.

## Decisioni approvate il 18 ottobre 2026

- D1: congelare le regole AR, parametrizzandole sulla FTP dell'atleta. Soglie
  di zona scalate con rapporto FTP/325; target osservati restano in W con
  arrotondamento storico a 5 W, durate e tolleranze del riconoscimento invariate.
  FTP mancante permette import/ispezione ma blocca la ricostruzione definitiva.
- D2: ordine 2 + AR(2), P1D/REML congelati. B e HR0 solo dal train: nessuna
  finestra HR validation, calibrazione o uso del valore iniziale heldout.
- D3 e D4 approvate come proposte in SPEC.
- Fit giÃ  effettuati utilizzabili come riferimenti locali read-only dei test,
  senza copiare risultati nella suite nÃ© ristimarli.
- Ruling operativo: lavorare nella branch dedicata giÃ  richiesta e creata,
  senza ulteriore worktree: il task deve archiviare anche dati locali ignorati.
- Il registro persistente Ã¨ questo documento; i task seguono PLAN, senza una
  seconda copia di stato temporanea. Review finale indipendente prevista.

Preflight interfacce: T2 fornisce forward e fitting esplicito a T6/T8; T3
fornisce revisioni immutabili a T4/T5; T5 fornisce manifest/hash al worker T6;
T7 pubblica versioni complete per T8; T8 congela snapshot per T9/T10.
Nessuna dipendenza richiede esecuzione del fitting durante lo sviluppo.

## Autorizzazioni giÃ  espresse

- Branch dedicata: creata `feature/local-study-webapp`.
- Preparare piano completo e persistente: autorizzato.
- Riutilizzare nucleo, conservare ultimi modelli: richiesto.
- Non ristimare nulla: vincolante anche per test e verifiche dell'agente.
- Primo fitting su dataset nuovo: azione riservata all'utente.

## Decisioni risolte

D1-D4 sono approvate come riportato sopra. D3: tempo trascorso, previsione
originale invariata; diagnostica per tratti con reinizializzazione dai soli
riferimenti train. D4: train prima della mezzanotte locale scelta, validation
dalla data compresa; fuso e confine persistiti.

## Fuori perimetro

- Fitting avviato dall'agente, anche solo di prova o sintetico.
- Migrazione automatica dei dati storici nel nuovo atleta.
- Nuovi modelli, nuove covariate, retuning sui risultati heldout.
- Ricerca di lag post hoc, interpolazione sensori o ricostruzione a posteriori
  di una prescrizione presentata come previsione originale.
- Login, cloud, deployment pubblico, Docker obbligatorio, app desktop nativa.
- Formati generici oltre FIT/ZIP per attivitÃ  e JSON/CSV v1 per prescrizioni.
- Ottimizzazione dell'allenamento, diagnosi, ranking fisiologico degli atleti.
- Aggiornamento automatico del modello, eliminazione fisica di storico/raw,
  ripresa automatica di job interrotti, redesign delle formule.

## Regola operativa prima di ogni task

1. Leggere solo task corrente, interfacce dipendenti e decisioni pertinenti.
2. Verificare autorizzazione, branch e cambiamenti locali; non ripetere inventari
   dell'intero repository senza nuova evidenza.
3. Dichiarare file da toccare e criterio di completamento del task.
4. Se servono file o scelte fuori task, registrare la necessitÃ  e chiedere
   estensione; non implementarla contestualmente.
5. Eseguire verifiche consentite; segnare quelle non eseguite e il motivo.
6. Aggiornare la tabella sotto con risultato, evidenza e soli scostamenti approvati.

## Avanzamento al 19 ottobre 2026

| Task | Stato | Evidenza |
|---|---|---|
| Pianificazione | Approvata | SPEC, PLAN e decisioni utente |
| T1 Archivio | Verificato | 20135 voci, 1486897092 byte; ARCHIVE_REPORT.md |
| T2 Nucleo | Implementato, forward verificato | Config/provenienza congelate; nessuna ristima |
| T3 Atleti/import | Implementato e testato | FIT sintetici, ZIP, hash, revisioni, ownership |
| T4 Eleggibilita/storico | Implementato e testato | FTP esplicita, segnali e gap |
| T5 Esperimenti/preflight | Implementato e testato | Confine temporale, conteggi, supporto HR |
| T6 Job identificazione | Implementato, test con stub | Retry, interruzione, errori; fitting reale non eseguito |
| T7 Risultati/versioni | Implementato e testato | Snapshot, validation, residui, parametri |
| T8 Prescrizioni/previsioni | Implementato e testato | Range espliciti, Monte Carlo, snapshot |
| T9 Confronti | Implementato e testato | Tre confronti, aderenza, gap, immutabilita |
| T10 Longitudinale/atleti | Implementato | Timeline e confronto matematico di due versioni |
| T11 Consegna | Verifiche automatiche eseguite | VERIFICATION.md; verifica visuale browser non disponibile |

I moduli sono consolidati rispetto ai nomi indicativi del piano: repository.py
contiene storage e validazione degli artefatti; HistoryPage e PlannerPage
implementano storico e preparazione. Nessuna estensione scientifica.
Le checklist originali di PLAN descrivono i criteri: questa tabella e
VERIFICATION riportano gli esiti effettivi, senza certificare prove non eseguite.

## Gestione delle modifiche

Ogni modifica concordata deve riportare data, richiesta, decisione, task/file
coinvolti, effetti scientifici e verifica aggiunta. Aggiornare SPEC e PLAN prima
di eseguire il nuovo scope. Non usare una spunta come prova di un test: registrare
comando, esito e artefatto essenziale. Non dichiarare completa la validazione
del fitting reale sulla base degli stub.
