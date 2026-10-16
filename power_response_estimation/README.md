# Power response estimation

## Esperimento GARCH(1,1) — branch analysis/ar-garch-11

Aprire **`index.html`** per confrontare simulazioni libere con varianza costante o GARCH.
Aprire **`garch.html`** per la previsione a un passo, la varianza condizionata,
le innovazioni standardizzate, ACF/ARCH-LM e metriche di incertezza.
Entrambe le pagine funzionano offline con ECharts locale; nessuna immagine statica aggiuntiva.

```powershell
# Stima solo omega, alpha, beta sul training del modello congelato; valuta entrambi gli split.
.venv/Scripts/python -B -m power_response_estimation fit-garch
# Sostituzione esplicita di un fit GARCH già presente:
.venv/Scripts/python -B -m power_response_estimation fit-garch --overwrite
# Valutazione riproducibile senza fitting:
.venv/Scripts/python -B -m power_response_estimation test-garch --split both
```

Equazioni: `epsilon_t = sqrt(h_t) z_t`, `h_t = omega + alpha epsilon_(t-1)^2 + beta h_(t-1)`.
Fonte: Bollerslev (1986), DOI `10.1016/0304-4076(86)90063-1`.
Gaussian QML con 6 partenze e peso uguale per campione; `omega > 0`, `alpha,beta >= 0`,
`alpha+beta <= 1-1e-6`. Nessun rifit della dinamica o dell'AR, nessuna covariata aggiunta.
Omega/h in W², alpha/beta adimensionali. Le innovazioni di training derivano dalla stessa
decomposizione congelata. All'inizio dei tratti reali h è inizializzata alla varianza
incondizionata; nessun reset ai cambi lap/target. La simulazione congiunta AR/GARCH usa
un warm-up deterministico nella durata e seed fisso, senza residui osservati.

La vista a un passo usa soltanto il passato osservato, con le stesse medie per le due varianti.
La simulazione libera non può sapere quando si verificherà un episodio osservato di alta varianza.
Le metriche principali sono NLL, copertura/ampiezza P10–P90 e interval score all'80%;
il RMSE della media non misura il beneficio del GARCH. Validation/test rimangono descrittivi
perché già esaminati. La baseline è l'AR originale a varianza costante.

Artefatti separati: `garch_model.json`, `garch_results.js`, `garch_predictions.csv`,
`garch_metrics.csv`, `garch_summary.csv`, `garch_diagnostics.csv`, `garch_report.md`.
`garch_evaluation.json` registra hash del codice e degli output dell'ultima valutazione;
gli hash in `garch_model.json` conservano invece la provenienza del fit originale.
Il modello contiene hash della baseline, split, versioni, seed, tutte le partenze e convenzioni.
Il report documenta anche persistenza, disponibilità degli IC e condizione del quarto momento.
Gli artefatti originali `model.json`, `results.js`, `predictions.csv`, `metrics.csv`, `report.md`
non vengono sovrascritti dai comandi GARCH. Se la baseline cambia, la valutazione GARCH viene rifiutata.

Test: `.venv/Scripts/python -B -m pytest tests/test_power_response_garch.py tests/test_power_response_estimation.py tests/test_power_response_estimation_core.py -q -p no:cacheprovider`.

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

La curva attiva è `target + (dinamica ? r : 0) + (AR ? contributo_AR : 0)`.

- **Previsione media:** il contributo AR è la sua media stazionaria `c/(1-phi1-phi2)`.
- **Simulazione:** il contributo AR è la prima traiettoria casuale, fissata da seed e configurazione. Il suo RMSE non misura la previsione dei picchi osservati.
- Disattivare un termine non rifitta l'altro e non rigenera il rumore. Sono ablazioni del modello completo, non modelli alternativi ristimati.
- Il residuo aggiornato è `reale - curva attiva`. Con solo la dinamica attiva coincide con `e=reale-target-r`; con simulazione AR attiva è un errore fra realizzazione osservata e simulata, **non** l'innovazione AR.
- La media accessoria del fit dinamico serve alla stima/selezione e non è aggiunta nella composizione finale: la media del residuo appartiene all'AR.

## Protocollo mantenuto

Target ricostruiti da `data/processed/prescribed_workouts_final/`: risultati condizionati a questa ricostruzione. Dinamica simmetrica stabile, numeratore di grado n con termine contemporaneo. Fit LS in simulazione libera, peso uguale per workout; selezione del più piccolo ordine entro un SE appaiato dal migliore RMSE di validation. AR(2) OLS con peso uguale per campione sul residuo `y-r`. Stato dinamico nullo e AR stazionario all'inizio dei tratti; nessun reset ai cambi di target/lap. Nessuna interpolazione o clipping.

Le predizioni non usano la potenza osservata come feedback. Gli IC dinamici sono locali, per cluster workout; gli SE AR sono OLS iid diagnostici. Il test già visto è descrittivo, non una nuova conferma indipendente. Il modello consegnato conserva esattamente i coefficienti e le simulazioni del run accettato (n=4 + AR(2)), senza nuovo fitting.

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
