# Power response estimation

## Riferimento congelato

Modello attivo: **dinamica ordine 4 + AR(2) a varianza costante**. La scelta privilegia
semplicita e costo predittivo; coefficienti, split e artefatti baseline non sono stati
ristimati durante la pulizia. La pagina attiva e `index.html` e la CLI espone solo
`fit` e `test`; `fit` resta disponibile per riproducibilita, non e necessario per consultare il modello.

Tutti gli esperimenti successivi, inclusa l'alternativa GARCH variance targeting,
sono nello [storico verificato](history/README.md), con codice, risultati, HTML e test.
La branch di analisi e conservata; nessun merge o riscrittura della storia.

Limiti da mantenere espliciti: SD simulata eccessiva nei lap stabili (rapporto mediano
circa1.53 sulla validation nel confronto a1000 traiettorie); potenze negative latenti corrette con clipping in uscita;
target ricostruiti dalle medie osservate, non prescrizioni esterne indipendenti;
nessuna validazione della catena verso HR ancora completata. Il viewer originale
conserva le sue 100 traiettorie latenti, con uscite aggiornate dal clipping; i confronti a1000 sono nello storico.

## Potenza negativa: decisione adottata il 17 ottobre 2026

1. **ADOTTATO: limite a zero solo sull'uscita:** P=max(0,P_latente), lasciando invariata la ricorsione AR latente.
   Scelta approvata dopo confronto su train/validation: nessun nuovo parametro, ma massa di probabilita a zero,
   media/energia in aumento e correlazione dell'uscita modificata. Non prova che gli zeri siano coasting reale.
2. **Normale condizionata a P>=0:** campionare la distribuzione predittiva troncata al limite fisico.
   Cambia media, varianza e dinamica della simulazione; richiede inizializzazione coerente e
   rivalutazione/possibile ristima. Non equivale a tagliare i valori negativi; con distribuzione
   continua non produce periodi esattamente a zero. Riferimento: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.truncnorm.html.
3. **Modello su scala positiva o a due parti:** componente zero/pedalata piu distribuzione positiva,
   oppure trasformazione positiva con AR latente. E un nuovo modello; aggiunge fitting e cambia
   la struttura additiva. Una lognormale pura non rappresenta zeri esatti. Non e il primo passo consigliato.

Prima di scegliere: quantificare quota/profondita/durata dei negativi e, dopo correzione, variazione
di media, energia, SD interna lap e zero-run; usare gli stessi numeri casuali e train/validation,
per fasce target e fase. Se il clipping altera sensibilmente il carico nei recuperi, non considerarlo
una correzione innocua. Evitare valore assoluto/riflessione: trasforma escursioni negative in potenza positiva.
Non rinormalizzare usando le medie osservate della validation. Il clipping e attivo; normale troncata e modello positivo non sono implementati.

Un solo modello per atleta:

\[
P_t=P_{target,t}+r_t+e_t,\qquad
r_t=G_n(q^{-1})\Delta P_{target,t},\qquad
e_t=c+\phi_1e_{t-1}+\phi_2e_{t-2}+\varepsilon_t.
\]

Aprire **`index.html`** in Edge o Chrome. Funziona anche senza server. Rotella per zoom, trascinamento per scorrere, barra inferiore per selezionare/spostare l'intervallo. I pulsanti Dinamica/AR aggiornano curva, residuo e metriche; il selettore permette di valutare l'intero workout o la finestra visibile.

## Comandi dalla radice del repository

```powershell
# Nuovo fit completo: dinamica n=2/3/4, scelta sul validation, AR(2) sul residuo.
# --overwrite è esplicito: sostituisce il modello e invalida i vecchi risultati test.
.venv/Scripts/python -B -m power_response_estimation fit --overwrite

# Coefficienti congelati: nessun refit, risultati nella stessa cartella.
.venv/Scripts/python -B -m power_response_estimation test --split validation
.venv/Scripts/python -B -m power_response_estimation test --split test
# Oppure entrambi:
.venv/Scripts/python -B -m power_response_estimation test --split both
```

Opzioni fit: `--input`, `--split-file`, `--orders 2 3 4`, `--loss linear|huber`, `--starts 6`, `--max-nfev 250`, `--seed 42`, `--paths 100`. LS è predefinito; Huber resta opzionale. Lo split predefinito è cronologico: 36 training, 12 validation, 12 test. `--output` è disponibile per un esperimento separato, ma non serve nel normale uso. Dipendenze nell'ambiente del repository: NumPy, pandas e SciPy.

## Significato degli interruttori

La traiettoria attiva e `max(0, target + (dinamica ? r : 0) + (AR ? contributo_AR : 0))`. Le componenti visualizzate sono latenti, prima del clipping.

- **Previsione media:** con AR attivo si mostra `E[max(0, X)] = mu Phi(mu/s) + s phi(mu/s)`, dove `mu=target+r+media_AR` e `s` e la SD marginale stazionaria AR. Con AR spento si applica il limite deterministico a zero.
- **Simulazione:** il contributo AR è la prima traiettoria casuale, fissata da seed e configurazione. Il suo RMSE non misura la previsione dei picchi osservati.
- Disattivare un termine non rifitta l'altro e non rigenera il rumore. Sono ablazioni del modello completo, non modelli alternativi ristimati.
- Il residuo aggiornato e `reale - curva attiva` dopo clipping; non coincide necessariamente con il residuo latente `reale-target-r` o con l'innovazione AR.
- La media accessoria del fit dinamico serve alla stima/selezione e non è aggiunta nella composizione finale: la media del residuo appartiene all'AR.

## Protocollo mantenuto

Target ricostruiti da `data/processed/prescribed_workouts_final/`: risultati condizionati a questa ricostruzione. Dinamica simmetrica stabile, numeratore di grado n con termine contemporaneo. Fit LS in simulazione libera, peso uguale per workout; selezione del più piccolo ordine entro un SE appaiato dal migliore RMSE di validation. AR(2) OLS con peso uguale per campione sul residuo `y-r`. Stato dinamico nullo e AR stazionario all'inizio dei tratti; nessun reset ai cambi di target/lap. Nessuna interpolazione; clipping solo sulla potenza composta in uscita.

Le predizioni non usano la potenza osservata come feedback. Gli IC dinamici sono locali, per cluster workout; gli SE AR sono OLS iid diagnostici. Il test già visto è descrittivo, non una nuova conferma indipendente. Il modello consegnato conserva esattamente i coefficienti e le simulazioni latenti del run accettato (n=4 + AR(2)), senza nuovo fitting.

## Contenuto essenziale

- `model.json`: modello completo, split/hash, candidati, selezione e statistiche dei parametri.
- `results.js`: campioni validation/test e quattro combinazioni in entrambe le modalità, leggibili dalla pagina senza server.
- `metrics.csv`, `report.md`: risultati sintetici.
- `predictions.csv`: una riga per campione valido degli split valutati, esportata automaticamente da `fit` (validation) e `test` (conserva anche gli split già valutati con lo stesso modello). Contiene split, workout, segmento, tempo in secondi, target e potenza reale, ingresso delta target, risposta dinamica, media AR, prima simulazione AR e quantili P10/P90 del solo contributo AR; tutte le potenze sono in watt.
  `predicted_mean_w` e `predicted_simulation_w` includono entrambi i contributi; `residual_mean_w` e `residual_simulation_w` sono reale meno la rispettiva predizione. `final_residual_w` è invece `reale-target-r`, il residuo modellato dall'AR. `innovation_w` è diagnostica sui residui osservati, vuota nei primi due campioni di ogni segmento. Componenti separate permettono di ricostruire le ablazioni della pagina. Nessun campione viene interpolato nei gap. Per rigenerare validation e test senza rifit: `.venv/Scripts/python -B -m power_response_estimation test --split both`.
- `cli.py`, `model.py`, `dynamics.py`, `ar.py`, `data.py`: unica pipeline; `index.html` e `app.js`: visualizzazione. ECharts locale con relativa licenza.
- `legacy.zip`: archivio recuperabile delle pipeline, documenti e risultati precedenti, non necessario per eseguire fit/test. I dati originali restano nelle loro directory.

Verifica: `.venv/Scripts/python -B -m pytest tests/test_power_response_estimation.py -q -p no:cacheprovider`.

Verificato: 144 test superati, 1 saltato nella suite completa; nel browser 192 combinazioni di workout/modalità/contributi, metriche Python/JS, finestra visibile, zoom con rotella e trascinamento. Predizioni medie e simulate identiche ai run precedenti su 91.597 campioni validation e 51.681 test.

## Archivio precedente

`legacy.zip` contiene 291 file verificati tramite SHA256, con elenco esatto in `ARCHIVE_MANIFEST.json`. Dopo autorizzazione dell'utente sono state rimosse le vecchie pipeline (`src/power_hr_eda/power_response`, `src/power_hr_eda/power_residual_ar`, `webapp/ar_validation_viewer`), i quattro script e i quattro test associati e i sette report precedenti. Prima della rimozione ogni file ? stato confrontato con la copia archiviata. I documenti metodologici in `references/`, tutti i dati e la pipeline di ricostruzione delle prescrizioni sono conservati. L'archivio non serve per eseguire il modello unificato.

## Convenzioni della correzione di uscita

Il clipping non entra nel fitting o nella ricorsione AR e non modifica le innovazioni
osservate. Si applica dopo la somma dei contributi, anche nelle ablazioni.
Le bande visualizzate sono i limiti latenti P10/P90 trasformati con max(0, P).
`ar_sample_w`, `ar_low_w`, `ar_high_w`, `ar_mean_w` restano latenti; `ar_sd_w`
e la SD marginale. `predicted_mean_w` e la media analitica dopo clipping;
`predicted_simulation_w` e la traiettoria corretta; `power_low_w`, `power_high_w`
sono limiti di potenza non negativi. Residui e metriche usano queste uscite.

Il modello numerico `model.json` resta invariato. `results.js` registra
`output_transform`; le componenti storiche, incluso il test gia visto, sono
soltanto ricomposte senza nuovi dati, refit o simulazioni. La selezione originale
dell'ordine resta precedente al clipping. Gli artefatti precedenti sono recuperabili
dal commit 51c43b0; gli hash protetti dello storico descrivono quello snapshot,
non i risultati trasformati successivamente.

Motivazione: l'analisi preliminare sui 12 workout di validation stima +1.14 W
di media e +0.56% di energia rispetto all'uscita latente; RMSE medio per workout
73.24 W invece di 73.31 W. La media e l'effetto energetico del clipping sono
analitici. Questi effetti aggregati non escludono distorsioni importanti sotto
100 W, fascia poco rappresentata. Gli zeri introdotti non identificano il coasting.
La variabilita eccessiva nei plateau e la validazione della catena verso HR
restano questioni aperte.
