# Confronto esplorativo della calibrazione iniziale di B

## Obiettivo e protocollo

Analisi autorizzata della run esistente, senza modifiche alla web app. Si confrontano finestre iniziali di 10, 30, 60, 120 e 180 secondi, mantenendo congelati K = 0.30108101976632484 bpm/W, tau = 50.75993501410485 s e L = 0 s. Non si introducono covariate o nuovi stati. La stima e una regressione scalare derivata algebricamente dal modello gia implementato; non e una nuova struttura dinamica.

Input: serie temporali e predizioni del JSON di review nella cartella superiore. La dipendenza affine da B consente di ricalibrare esattamente le traiettorie salvate senza rieseguire il fitting di popolazione:

```bash
w(t) = 1 - exp(-t / tau)
a(t) = HR_predetta_originale(t) - w(t) * B_originale
B_non_vincolato(T) = somma[w(t) * (HR_osservata(t) - a(t))] / somma[w(t)^2]
# Le somme usano solo HR finite e 0 <= t < T.
B(T) = clip(B_non_vincolato(T), 60, 200)
HR_predetta_T(t) = a(t) + w(t) * B(T)
```

I limiti 60 e 200 bpm sono dedotti dai record originali con calibration.at_bound, poiche il manifest del fitting non e disponibile nel percorso locale atteso. Con questi limiti, tutte le traiettorie originali a 10 secondi sono riprodotte entro 5.7e-14 bpm; sono verificate anche MAE, RMSE e bias originali. Non sono limiti fisiologici universali.

HR iniziale, riferimento P0, risposta alla potenza e parametri dinamici restano quelli della run. Dopo la calibrazione B resta costante; non si reimposta lo stato sulla HR osservata al termine della finestra. La HR successiva viene utilizzata soltanto per calcolare gli errori. Si assume che un B costante descriva il segmento; B e un livello matematico riferito a P0, non HR a riposo.

Tutte le alternative vengono valutate sugli stessi campioni con tempo >= 180 s e HR finita. Si confronta quindi lo stesso tratto di ciascun segmento, non lo stesso orizzonte dalla fine della calibrazione. Il dataset contiene 53 segmenti con predizione, appartenenti a 21 attivita; il tempo finale minimo e 335 s. Nessuno richiede una regola per segmenti sotto 180 s. Gli 8 segmenti originali senza predizione sono esclusi, senza tentare di correggerli.

## Risultati

Le prime tre colonne di errore riportano mediane tra segmenti, in bpm. Per la colonna attivita si aggregano prima SSE e N dei segmenti della stessa attivita, quindi si calcola la mediana degli RMSE delle 21 attivita.

| Calibrazione (s) | RMSE | MAE | Bias assoluto | RMSE attivita | Migliorati / peggiorati / invariati rispetto a 10 s |
|---|---|---|---|---|---|
| 10 | 25.70 | 25.37 | 25.37 | 29.31 | 0 / 0 / 53 |
| 30 | 16.83 | 15.96 | 15.86 | 16.20 | 38 / 12 / 3 |
| 60 | 13.24 | 12.63 | 12.63 | 15.55 | 40 / 12 / 1 |
| 120 | 9.09 | 7.91 | 7.43 | 10.46 | 45 / 7 / 1 |
| 180 | 7.12 | 5.75 | 4.77 | 7.36 | 46 / 6 / 1 |

Il 90esimo percentile degli RMSE scende da 72.89 a 10.27 bpm. La mediana della deviazione standard campionaria dei residui resta circa 4.2 bpm: il miglioramento riguarda soprattutto il livello. Le stime ai limiti passano da 6 a 2.

Tra 120 e 180 s, la variazione assoluta di B ha mediana 4.39 bpm e 90esimo percentile 7.42 bpm. La stima non e quindi universalmente stabilizzata a 120 s. La finestra da 180 s e la migliore tra quelle provate secondo le metriche aggregate; non e dimostrato che sia ottimale oltre questa griglia o per ogni singolo segmento. Nessuna finestra e stata selezionata retrospettivamente per singolo segmento.

## Segmenti brevi e possibile seguito

Per un'applicazione causale, una regola adattiva dovrebbe utilizzare solo il prefisso gia osservato, per esempio una durata minima e un controllo della stabilita delle stime successive di B. Stabilita apparente non implica correttezza, e un limite raggiunto puo produrre falsa stabilita. Soglie, durata minima, numero di controlli e trattamento dei limiti non sono stati scelti o sperimentati qui.

Se il segmento termina prima della fine della calibrazione, non esiste una coda di previsione autonoma da valutare. Va riportato come non valutabile per quel protocollo, senza classificare il fitting iniziale come predizione. Una regola basata sulla durata totale puo essere usata in un benchmark retrospettivo, ma non rappresenta un arresto online quando la durata futura non e nota.

Questa analisi e esplorativa sul test gia ispezionato. Una nuova run con altro seed, dopo aver congelato il protocollo, valutera la robustezza allo split; non costituira una conferma su dati mai visti. K e tau sono rimasti fissi in questo confronto, ma B puo anche assorbire errori della dinamica: il miglioramento non prova la correttezza fisiologica dei parametri.

## Riproduzione e artefatti

```bash
python reports/P1D_first_full_dataset_run/B_calibration_comparison/analyze.py
```

- `analyze.py`: analisi standalone con verifiche di riproduzione e separazione tra calibrazione e valutazione.
- `summary.json`: aggregati, stabilita di B, SHA256 del JSON sorgente, versione NumPy e assunzioni.
- `per_segment.csv`: 265 righe, una per segmento e finestra, con B, metriche e durata.

Gli output vengono scritti soltanto in questa sottocartella. Nessuna modifica a sorgenti della web app o al JSON originale.
