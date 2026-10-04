# Evidenze della milestone del 4 ottobre 2026

`summary.json` riassume l'analisi salvata della run seed 52 e lo stato della
successiva identificazione seed 60. Non esegue fitting né modifica le sorgenti.
Gli errori sono mediane non pesate tra i segmenti test con predizione riuscita,
valutate dopo 180 secondi di calibrazione iniziale. I fallimenti sono contati
separatamente; la baseline disponibile è HR costante pari al B del segmento.

Per rigenerare gli aggregati dalla radice del repository:

```powershell
.\.venv\Scripts\python.exe scripts/summarize_current_study.py
```

Occorre lo storage locale delle due run, con l'analisi di popolazione seed 52
in modalità `local_B_180s`. Gli hash nel riepilogo identificano gli esatti file
letti: se l'analisi salvata viene sostituita dall'app, una nuova esecuzione può
produrre altri risultati. La copia seed 52 della milestone resta nella branch
`milestone/2026-10-04-hr-power`, sotto `milestone_artifacts/`. Il riepilogo non
confronta le predizioni delle due run e non anticipa conclusioni sulla ripetibilità.

## Dipendenze conservate

Le cartelle `reports/activity_split_simulation/` e
`reports/timestamp_gap_distribution/`, con gli script Python nella cartella
`reports/`, documentano la preparazione del dataset corrente: esame dei gap,
separazione dei segmenti e confezionamento dello ZIP per l'app. Sono conservate
come dipendenze dello studio, insieme ai dati sorgente locali e ai blob immutabili.
Non rigenerare i dati durante una run.

## Archiviazione e pulizia

Gli esperimenti precedenti, i loro report, i documenti di pianificazione e
l'esplorazione storica sono consultabili nella branch milestone, commit `c95496e`.
Lì `milestone_artifacts/inventory.json` elenca 2.143 copie con SHA-256 verificati
anche sui byte registrati in Git; le conversioni dei fine riga sono disabilitate
per gli artefatti. La run seed 60 era ancora attiva durante quella copia, che
quindi è parziale e non costituisce un checkpoint atomico.

Su `main` il registro conserva le due run e i rispettivi dataset. Sono stati
rimossi i vecchi risultati, gli archivi dei manifest e dataset dismessi, gli
storage temporanei dei test e i due generatori di report specifici della run
`00e47e9c`. I test automatici, il codice riutilizzabile, i raw e il contenitore
condiviso dei blob sorgente sono conservati. Le eliminazioni dello storage
ignorato da Git sono operazioni locali: un altro checkout non le replica da solo.
