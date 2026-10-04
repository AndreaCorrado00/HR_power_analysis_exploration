# Snapshot dello studio ? 4 ottobre 2026

Branch: `milestone/2026-10-04-hr-power`.

Il codice ? nella radice della branch. Questa cartella conserva report, esplorazioni,
documenti e storage scientifico che erano in parte ignorati da Git.
`inventory.json` registra percorsi originari, dimensioni e SHA-256 delle copie verificate.
Cache, ambienti, log, installazioni e storage usa-e-getta dei test non sono inclusi.
I raw esterni in `dataset/` non sono copiati; i blob importati nello storage sono inclusi.
Non si presume che tutti gli esperimenti storici abbiano ancora tutti gli artefatti:
lo snapshot preserva quanto presente, senza ricostruire risultati gi? eliminati.

## Consultazione e ripristino

Consultare questa branch in un checkout separato, senza cambiare lo storage di un
servizio attivo. Per l'app di identificazione passare a `start.ps1 -Storage` il
percorso assoluto di `milestone_artifacts/webapp/model_identification_app/storage`
(o una sua copia di lavoro). Le dipendenze Python e la build frontend vanno preparate
come descritto nel README dell'app. Verificare gli hash prima di un ripristino.

La run `8dc6d46a06e6496aab0ba80040ba56ad` era attiva durante la copia: questo ? uno
snapshot parziale per file, non un checkpoint atomico n? una promessa di ripresa.
Il suo storage originale ? rimasto attivo e non ? stato sostituito dalla copia.
Al riavvio su una copia l'app pu? segnalarla come interrotta; la riesecuzione
riparte dalle impostazioni salvate. Non copiare questi risultati sopra la run viva.
