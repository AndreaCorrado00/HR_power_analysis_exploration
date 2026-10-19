# Studio HR / Power — guida locale

## Avvio

Windows, Python 3.14 e Node.js >=22.12 con npm per il setup frontend. Le versioni
Python runtime sono in requirements.txt; quelle frontend sono nel package-lock.
Il launcher può riutilizzare il Node del runtime Codex quando disponibile.

```powershell
.\study_app\start.ps1              # frontend già compilato in questa workspace
.\study_app\start.ps1 -Setup       # installa dipendenze e compila, nessun fitting
.\study_app\start.ps1 -Port 8775   # porta alternativa
```

URL predefinito http://127.0.0.1:8770. Solo loopback, nessun servizio cloud.
Ctrl+C ferma il server; se un job è attivo il processo attende il worker.
Un arresto forzato marca il job interrotto al riavvio, senza ripresa automatica.
Un secondo server sullo stesso storage è rifiutato.

## Primo utilizzo

1. Aggiungere atleta: nome, cognome, età, FTP opzionale. L'età si riferisce alla
   data di inserimento, non implica una data di nascita stimata.
2. Importare FIT, più FIT o ZIP di FIT. Lo storico conserva originali, missing,
   pause e anomalie. I duplicati per hash non duplicano l'attività. Un file
   diverso con la stessa data iniziale è segnalato come conflitto e non sostituisce
   l'originale; non viene scelta automaticamente una delle due registrazioni.
3. La FTP serve per la ricostruzione congelata dei target. Senza FTP si può
   ispezionare il workout ma non identificarne il modello. Dopo una modifica FTP,
   usare **Prepara nuova revisione con FTP attuale**. Nessun fitting in questa fase.
4. Creare esperimento con data/fuso. Prima delle 00:00 della data = train;
   dalla data compresa = validation; attività intere secondo inizio registrazione.
   Leggere supporto, esclusioni e assunzioni, poi avviare esplicitamente il fit.
5. Consultare versioni e validation. Se la popolazione non è identificabile,
   il fallimento e la diagnostica sono conservati; nessun fallback o retuning.
6. Preparare allenamento, scegliere modello, risolvere i range, simulare e
   salvare la previsione PRIMA della sessione. Nessun modello storico preinstallato.
7. Importare il FIT reale e associarlo alla previsione. I tre confronti restano
   separati; creare un nuovo modello in futuro non cambia le verifiche precedenti.

## Protocollo congelato

Potenza: dinamica ordine 2 + AR(2), clipping soltanto in uscita. HR: P1D con
ritardo e popolazione multivariata REML dei parametri tra tratti dello stesso
atleta. Le impostazioni esatte sono in scientific/frozen_config.json.

**B=A+K·P0; A e HR0 sono esclusivamente riferimenti train. Nessuna finestra HR
validation, nessuna HR iniziale heldout, nessuna calibrazione post hoc.**

Regole AR: riferimento FTP 325 W; soglie di zona scalate con FTP/325. Membership
valutata sulla scala di riferimento con rounding storico. Durate, pattern,
tolleranze e arrotondamento del target osservato a 5 W restano invariati.
Non si trasferiscono i 60 ID selezionati storicamente ai nuovi atleti.
La prescrizione ricostruita non è una prescrizione originale conosciuta a priori.

La validation della catena con target ricostruiti è retrospettiva. Una verifica
è prospettica solo se modello e previsione precedono la sessione e i dati non
sono stati usati da quella versione; la data d'import non basta. Le impronte
dei FIT della selezione storica nota impediscono di presentarli come test vergine.
La conoscenza umana di altri dati non è automaticamente rilevabile dal software.

Il modello viene stimato solo dopo il comando dell'utente. Non è stata eseguita
alcuna ristima durante lo sviluppo. Il primo fit reale e la sua validità sul
nuovo atleta restano da verificare dall'utente.

## Prescrizioni

CSV UTF-8: esattamente `duration_s,target_w`, una riga per blocco, watt assoluti
e durata intera positiva. Ripetizioni espanse nel CSV. Gli esempi scaricabili
sono in `examples/`.

JSON: `schema_version: 1`, `name`, `blocks`. Blocco:
`{"duration_s":300,"target":{"kind":"constant","watts":150}}`.
Ripetizione: `{"repeat":3,"blocks":[...]}`. Profondità massima 2.
Range: `{"kind":"range","low_w":180,"high_w":220}`; l'editor richiede centro,
profilo a punti `[tempo_s,watt]` o scenari nominati. I profili coprono 0–durata
e sono lineari fra i punti; questa interpolazione riguarda la prescrizione,
non i sensori. Per più range, gli scenari hanno gli stessi nomi e valori
espliciti. Nessuna distribuzione probabilistica è dedotta da un range.

MC predefinito 1000 traiettorie, seed 42, fasce puntuali 95%. I toggle P/HR sono
indipendenti e non rigenerano simulazioni. Fasce di variabilità parziale:
AR potenza e parametri HR; escluse incertezza A/HR0/medie/coefficienti potenza
e rumore residuo HR. Leggere copertura insieme a larghezza.

Limiti operativi: attività FIT/ZIP (2 GiB caricati, 10 GiB espansi, 20000 entry);
ZIP senza link, cifratura, archivi annidati o file diversi da FIT. Prescrizione
massimo 24 ore, 20000 blocchi espansi, 10 scenari e 1000 traiettorie. Il budget
locale è 20 milioni di campioni × traiettorie complessivi: sopra questo limite
la richiesta è rifiutata con indicazione di ridurre durata/scenari/traiettorie,
mai ridotta implicitamente. Nessun import ZWO/TCX/GPX o conversione %FTP.

## Allineamento e metriche

Origine: primo timer start, altrimenti primo campione; tempo trascorso. Nessun
lag ottimizzato su HR. La previsione salvata prosegue invariata. Per diagnostica
da P reale, pause/gap interrompono i tratti e le ripartenze usano A/HR0 train;
le reinizializzazioni sono elencate. I cambi di blocco non resettano gli stati.

MAE, RMSE, bias osservato-predetto, SD residui, copertura/larghezza. Validation:
intero tratto, primi 180 s e coda senza calibrazione; media per workout con
peso uguale. Metriche zoom chiaramente separate da quelle globali.
Nel confronto, potenza prescritta/reale, lavoro sul solo supporto continuo a 1 s,
durata, copertura e scostamenti per blocco descrivono l'aderenza; nessuna soglia
automatica aderente/non aderente. Contesto osservato conservato senza covariate.

## Dati e ripristino

`storage/` è escluso da Git, con indice SQLite e cartelle UUID per atleta.
Artifact JSON con hash e revisioni; originali in raw/<sha256>/source.fit.
Lo storage storico è soltanto in archive: la nuova app non lo carica.
Nessun endpoint cancella modelli, raw o previsioni. Snapshot completati immutabili;
anagrafica modificabile con registro revisioni. Verifica degli hash prima dell'uso.
File orfani da crash restano non indicizzati e non visibili come completati.

Backup: arrestare il servizio e copiare l'intera `storage/`, inclusa study.sqlite3.
Ripristinare a servizio fermo, senza sovrapporre due storage. Non salvare una
sola copia del DB senza gli artefatti. I test scrivono solo in tmp/study-test-*;
il runtime operativo non contiene atleti o risultati di prova.

## Verifiche senza fitting

```powershell
.venv/Scripts/python.exe -B -m pytest study_app/tests -q -p no:cacheprovider
cd study_app/frontend
npm.cmd test
npm.cmd run build
```

La suite blocca gli stimatori e `numpy.linalg.lstsq`. Usa FIT sintetici validi,
parametri sintetici prefissati e job stub. Un test opzionale legge un risultato
storico locale per confrontare il forward HR; non copia risultati nella suite.
Non eseguire indiscriminatamente i test sotto archive, che includono fitting.
La verifica visuale nel browser controllato non è stata possibile nella sessione
di sviluppo: nessun browser disponibile tramite l'integrazione. Test componenti
Vue in jsdom e build sono distinti da tale verifica.
