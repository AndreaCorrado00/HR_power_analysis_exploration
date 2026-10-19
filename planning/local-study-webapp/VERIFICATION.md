# Verifica della consegna - 19 ottobre 2026

Branch: `feature/local-study-webapp`. Scope e decisioni: SPEC.md e CONTROL.md.

## Verifiche automatiche

- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --tb=short`:
  **30 passed**, un warning di deprecazione Starlette/httpx esterno.
- Da study_app/frontend, con Node locale: `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`: exit 0.
- `node node_modules/vitest/vitest.mjs run`: **6 passed**, due file.
- `node node_modules/vite/bin/vite.js build`: exit 0; bundle 720.95 kB,
  gzip 248.14 kB. Warning dimensione chunk ECharts, non errore.
- Server loopback 8770: `/api/health` ok, fitting `explicit_user_action_only`;
  `/api/athletes` lista vuota alla consegna. Nessun modello operativo importato.

La discovery pytest e limitata alla suite nuova. Le guardie nei test impediscono
l'accesso agli ottimizzatori e al fitting, inclusi i minimi quadrati. I job sono
verificati con stub; i modelli sintetici hanno parametri assegnati esplicitamente.
I FIT sintetici passano attraverso il parser FIT reale. I test coprono import,
revisioni, ownership, split, supporto osservato HR, errori/retry/interruzione dei
job, integrita degli artefatti, prescrizioni, snapshot e confronto prospettico.
Un controllo locale legge risultati storici archiviati e confronta il solo
forward numerico: nessun risultato storico copiato nella suite.

La revisione indipendente ha individuato tre problemi corretti e coperti da test:
revisioni dataset duplicate negli import successivi; preflight senza campioni HR
osservati in validation; chiave di idempotenza riusata nel retry dell'interfaccia.

## Conservazione dello studio

20135 voci archiviate, 1486897092 byte; verifica finale: zero destinazioni mancanti.
Hash dei due artefatti congelati identici al manifest precedente allo spostamento:

- HR: `d4c694952215e7b5c87d14f7b7833a438646a70a7a5374a09a1f7c4f95cfc2db`
- Power: `13a0b2096eabe2816d943f4886ffa7ff6e4928de06471397aef56f20eaca39c2`

Dettagli e limiti dei link storici: ARCHIVE_REPORT.md. I file prima ignorati
restano locali e ignorati; lo staging dell'archivio include soltanto i file gia
tracciati e il README di archivio. Lo storage operativo e escluso da Git.

## Limiti dichiarati

- **Nessun fitting o refitting eseguito**, neppure sintetico. La prima
  identificazione reale e riservata all'utente su un nuovo dataset. I test con
  stub non certificano convergenza o identificabilita sul futuro atleta.
- Verifica visuale delle sei sezioni nel browser **non eseguita**: il servizio
  di controllo UI non espone browser disponibili; apertura Edge/IAB non riuscita.
  I test dei componenti, il typecheck e la build non sostituiscono questa prova.
- Nessuna verifica di riavvio dei vecchi launcher archiviati, che conservano
  percorsi/link originali; l'archivio non viene usato dal runtime nuovo.

Avvio e workflow sono documentati in ../../study_app/README.md. La previsione
salvata precede l'esecuzione; diagnostica con potenza reale e previsione a priori
restano distinte. B/HR0 sono train-only e non calibrati sulla validation.

Staging verificato: 483 file storici gia tracciati spostati; nessun nuovo raw,
risultato storico ignorato, storage o dipendenza binaria aggiunto. Il controllo
whitespace segnala soltanto una riga vuota finale in frozen/power/ar.py,
preservata intenzionalmente per mantenere identico il nucleo congelato.
