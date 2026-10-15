# AR del residuo di potenza

## Aggiornamento: simulazione libera dell'intero workout

Su richiesta dell'utente, la nuova modalita genera il residuo rumoroso per
tutta la sessione senza aggiornarsi con residui misurati. La storia AR continua
attraverso i cambi di target e lap. **Nessun transitorio al cambio lap viene
modellato**; i campioni vicini ai cambi restano nel fit, senza esclusioni.
La prescrizione viene semplicemente sommata al residuo generato.

```powershell
.venv/Scripts/python -B scripts/power_residual_ar.py simulate --paths 100 --seed 42 --analyze
```

Legge `--from-run reports/power_residual_ar`, eredita split e ordine selezionato
(p=2 nella prima esecuzione) e scrive in una nuova cartella
`--output reports/power_residual_ar_simulation`. Non riottimizza p e non modifica
la precedente analisi. I coefficienti sono ristimati sul training con la nuova
continuita, con hold-back minimo p soltanto dopo interruzioni reali. Per la
validation usa il fit training; per il test descrittivo il refit train+validation.
Il test precedente e gia stato visto: non e un nuovo test indipendente.
Il comando richiede che il test originale sia completato e verificato; rifiuta
run con test ancora chiuso, per non aggirare il congelamento della selezione.

Assunzioni esplicite della generazione:

- Innovazioni iid gaussiane con varianza stimata; parametri costanti.
- Stato iniziale campionato dalla distribuzione stazionaria del modello,
  calcolata con l'equazione discreta di Lyapunov; serve un AR stabile.
- Nessun feedback dai residui osservati, neppure per inizializzare. Tutti i
  campioni validi sono simulati, inclusi quelli iniziali.
- Reset soltanto ai confini di disponibilita/continuita del dataset: gap,
  pause o segnali/target invalidi; nessun reset ai lap o ai target numerici.
- La maschera di disponibilita e il target inferito provengono dal dataset
  osservato: la generazione non prova una previsione prospettica del piano.
- Seed riproducibile, 100 traiettorie di default. Viene mostrata sempre la
  prima, non quella piu simile ai dati. P10-P90 puntuali, senza incertezza
  parametrica e senza garanzia simultanea sull'intera sessione.
- Nessun clipping: eventuale potenza negativa resta visibile e quantificata
  come limite dell'AR gaussiano.

L'RMSE della traiettoria casuale non misura la capacita di ricreare esattamente
i picchi osservati. Sono riportati separatamente RMSE/MAE della previsione
media e della prima simulazione, dispersione, ACF e copertura delle bande.
`simulation.py` genera le traiettorie; `simulation_run.py` orchestra la nuova
analisi. `fit.py` rimane autonomo. La modalita precedente, descritta di seguito,
resta disponibile per riprodurre la valutazione a origini mobili.

---

Analisi di `e(t) = power_w(t) - power_target_w(t)` sul dataset finale dei 60
workout prescritti. Protocollo con validation approvato il 2026-10-13.
Il dataset viene letto, mai riscritto; hash SHA256 verificati prima e dopo
ogni fase. Nessuna dipendenza nuova: NumPy, pandas e Matplotlib gia presenti.

## Pipeline e comandi

Dalla radice del repository, usando l'ambiente esistente:

```powershell
# 1. Congela split e configurazione; ACF/PACF soltanto sul training.
.venv/Scripts/python -B scripts/power_residual_ar.py diagnose

# 2. Dopo aver visto i grafici: fit su training e valutazione su validation.
#    Per l'esecuzione iniziale le ACF/PACF hanno suggerito p=1 e p=2.
.venv/Scripts/python -B scripts/power_residual_ar.py fit --p 1 2 --analyze

# 3. Solo dopo la selezione: refit train+validation e test finale.
.venv/Scripts/python -B scripts/power_residual_ar.py test --analyze
```

`--p` accetta uno o piu interi. Se omesso usa `diagnostics/candidates.json`.
`--analyze` aggiunge diagnostica delle innovazioni e pochi grafici: ACF/PACF,
prestazioni per workout/orizzonte e tre esempi prefissati. Senza il flag vengono
comunque salvati coefficienti, IC, metriche e selezione.

Tutti i comandi accettano `--output` (default `reports/power_residual_ar`).
`diagnose` accetta `--input`, `--train-count`, `--validation-count`, `--max-lag`
e `--max-order`. Per ripetere l'esperimento usare una nuova directory di output;
non sovrascrivere gli artefatti originali. Una volta aperto il test la directory
non accetta altri fit o altri test. Creare una nuova directory non rende
scientificamente nuovo un test gia visto: non usarlo per ulteriori scelte.

L'entry point equivalente, con `src` nel `PYTHONPATH`, e
`python -m power_hr_eda.power_residual_ar`.

## Separazione delle responsabilita

- `data.py`: lettura, segmentazione in memoria e split per workout.
- `diagnostics.py`: ACF/PACF per tratto, sintesi e candidati esplorativi.
- **`fit.py`: fit AR autonomo**, senza I/O, split, validation o grafici.
- `validation.py`: previsioni causali e metriche con coefficienti fissi.
- `plots.py`: sole figure; `cli.py`: orchestrazione e tracciabilita.

API del fit: `fit_ar(segments, p, hold_back)` restituisce un `ARModel`.
Ogni elemento di `segments` deve esporre un array `residual` finito e gia
continuo; l'API non interpreta timestamp. La pipeline garantisce questa
precondizione tramite `segment_frame`. `hold_back` deve essere almeno `p`.
`ARModel.to_dict()` / `from_dict()` permettono il riuso del modello salvato.

## Modello, assunzioni e fitting

`e_t = c + sum(phi_j * e_(t-j), j=1..p) + epsilon_t`.
Predizione della potenza: `P_target(t) + e_hat(t)`.

- Passo 1 s; `c` in watt, `phi_j` adimensionali, varianza in W^2.
- Un solo insieme di coefficienti per atleta, condiviso tra workout.
- Stima OLS con intercetta sul residuo originale. Non si sottrae la media
  del tratto prima del fit: richiederebbe anche osservazioni future.
- Le righe di regressione dei tratti si possono impilare; i segnali non si
  concatenano mai prima della costruzione dei lag.
- AIC e BIC derivano dalla likelihood gaussiana condizionale con varianza
  MLE `SSE/n`; numero parametri `p+2` (lag, intercetta, varianza).
- Stabilita: tutte le radici di `z^p - phi_1*z^(p-1) - ... - phi_p`
  dentro il cerchio unitario. Un eventuale fallimento e riportato, non corretto
  imponendo vincoli o cambiando modello dopo aver visto il test.
- Gli errori standard OLS assumono innovazioni iid omoschedastiche: sono
  diagnostici, non intervalli robusti alle differenze tra workout.

Fonti metodologiche (modello AR standard, non un nuovo modello fisiologico):
[AutoReg / OLS condizionale e hold_back](https://www.statsmodels.org/stable/generated/statsmodels.tsa.ar_model.AutoReg.html),
[PACF Yule-Walker](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.pacf.html).
L'implementazione NumPy evita di aggiungere statsmodels all'ambiente.

## Tratti e diagnostica

Campione valido: potenza finita e >=0, target numerico finito, timer non in
pausa, ID segmento potenza e lap validi. Confine a ogni passo temporale diverso
da 1 s, cambio segmento, target o lap, e ai campioni invalidi. Gli zeri validi
restano. I target massimali categorici senza watt non entrano nel residuo.
Non si richiede HR valida: questa analisi riguarda solo potenza e target.

Non si interpolano, filtrano o eliminano transitori. Tutti i tratti validi
sono inventariati. Per ACF/PACF servono almeno 4 campioni; massimo lag per
tratto `min(60, floor(n/2)-1)`. I tratti costanti hanno correlazioni indefinite
e vengono segnalati. Per il fit servono piu di `hold_back` campioni.

ACF centrata per tratto, autocovarianze con denominatore comune n; PACF con
ricorsione Levinson-Durbin (Yule-Walker non corretta per il lag). Sintesi:
mediana tra tratti entro workout, poi mediana e P10-P90 tra workout. Ogni
figura per workout mostra anche tutte le singole curve; i valori integrali
sono in `segment_curves.npz`, nello stesso ordine delle righe di `segments.csv`.
Il supporto varia col lag ed e riportato nel CSV di sintesi.

Euristica per pochi candidati: AR(1), ultimo lag <=20 con mediana tra workout
del rapporto `|PACF|/(1.96/sqrt(n)) >= 1`, e il lag successivo (entro 20).
Il rapporto viene prima sintetizzato per workout con mediana tra tratti.
La soglia e solo un riferimento nominale da rumore bianco; non e un test
simultaneo ne una prova che tutti i tratti seguano lo stesso processo.
Le immagini vanno lette prima del fit; gli ordini si passano esplicitamente
alla CLI. In questa esecuzione l'euristica e l'ispezione hanno indicato 1 e 2.

## Split e protocollo di valutazione

Ordine crescente del primo timestamp UTC registrato, non random split:

- primi 36 workout: training e ACF/PACF;
- successivi 12: validation per scegliere p;
- ultimi 12: test finale, aperto solo dopo la selezione.

L'inventario iniziale legge solo il primo timestamp dei workout e gli hash
di tutti i file; non usa i valori del test per la diagnostica o il fitting.
Gli ID e le date esatti sono salvati in `split.csv`/`split.json`.

Supporto comune congelato a `hold_back=20` (default `max_order`): ogni ordine
usa gli stessi endpoint, anche quando p e minore. I primi 20 campioni di ogni
tratto sono storia disponibile, non punti valutati. I segmenti piu brevi
restano documentati ma non producono righe di fit.

Per ogni p: AIC/BIC training; RMSE, MAE e bias per workout, distinti tra
training e validation. Media delle metriche a peso uguale per workout; il fit
OLS pesa invece ugualmente ogni campione. Scelta: minimo RMSE medio di
validation a h=1, parita esatta risolta con p minore. MAE e IC restano
informazioni di supporto. Nessun obbligo che il modello batta la baseline.

Dopo il congelamento, stesso p e supporto vengono ristimati sui 48 workout
di training+validation; il test valuta soltanto questo modello e la baseline
`P_hat=P_target`. Non riporta il test di tutti i candidati.

Previsioni a origini mobili:

- h=1 s: usa esclusivamente i p residui osservati prima dell'endpoint;
- h=10/30 s: parte dal passato osservato all'origine e ricorre per h passi,
  senza sostituire valori futuri misurati dentro la ricorsione.

AR e baseline sono confrontati sugli stessi endpoint per ogni orizzonte.
L'insieme degli endpoint puo diminuire all'aumentare dell'orizzonte. Nessuna
previsione attraversa la fine del tratto; il modello non e valutato ai cambi
o durante le pause. Non e una simulazione dell'intero workout senza misure.

## Limite scientifico principale

`P_target` e inferita dalla stessa traccia di potenza, come documentato in
`references/prescribed_dataset_final.md`. Anche con split corretti, questa
valutazione e condizionata al target ricostruito. Non dimostra previsione
prospettica rispetto a un piano realmente disponibile prima del workout.
Target costante e buona previsione a 1 s non provano stazionarieta, rumore
bianco o adeguatezza dell'AR a orizzonti lunghi. Le innovazioni e le differenze
tra workout devono essere considerate nell'interpretazione finale.

## Verifica

```powershell
.venv/Scripts/python -B -m pytest tests/test_power_residual_ar.py -q
```

I test coprono segmentazione senza alterazioni, supporto comune, recupero
di un AR sintetico, IC, causalita delle previsioni ricorsive, metriche in W,
pesi per workout, split e ciclo CLI con congelamento del test. Un test
specifico verifica che tratti di innovazioni troppo brevi non interrompano
un fit valido quando viene richiesto `--analyze`.
