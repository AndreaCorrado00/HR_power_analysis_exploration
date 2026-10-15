# GRU v3: confronto di capacita con budget temporale

Protocollo approvato nella conversazione: GRU(32) e GRU(64 -> 32), finestra
causale di **60 s**, **20 epoche per fold**, sei fold. Questa scelta sostituisce
le proposte intermedie di 50 epoche e finestre 30/120 s.

## Esperimento

Le due reti sono gia implementate in `gru/model.py`: strati GRU unidirezionali
seguiti da un'uscita lineare scalare. Non viene introdotto un nuovo modello
bibliografico; si confronta la capacita delle due architetture del protocollo v2.
GRU(32) ha 3.489 parametri e GRU(64 -> 32) ne ha 22.497.

Input: prescrizione numerica normalizzata e flag is_maximal. Per i massimali
l'ingresso numerico normalizzato resta neutro; non si inventa una prescrizione.
Target: potenza reale anche nei massimali. Adam, learning rate 0,001, MSE,
nessun weighting, oversampling o arresto anticipato. Seed 42, CPU, quattro thread.
Batch training 256; batch di sola inferenza 1024. Il maggiore batch di training
cambia il percorso di ottimizzazione rispetto a v2: entrambe le reti ripartono
da zero e condividono le nuove impostazioni.

Si riusa `data/processed/gru_dataset_v2/manifest.json`: 48 workout development,
sei fold 40/8 con shuffle seed 42, ultimi 12 workout riservati al test temporale.
Nessun nuovo split e nessuna duplicazione dei campioni. Scaler fit solo sul train
di ciascun fold; masking, campioni e ponderazione invariati. Le metriche train e
validation vengono calcolate in eval a ogni epoca, dopo denormalizzazione.

Il confronto usa RMSE medio per workout OOF, metriche aggregate in watt,
massimali/non massimali e transizioni. La baseline numerica resta la prescrizione
sui soli campioni non massimali. Una riduzione dell'errore di training senza
miglioramento OOF indica adattamento in-sample senza beneficio predittivo;
un input identico non puo produrre traiettorie differenti in un modello deterministico.
L'epoca migliore viene selezionata dalla validation e le metriche CV sono stime
di tuning. Il test finale resta escluso dalla selezione.

## Velocita e ripresa

Benchmark di un'epoca completa sul fold 1 reale, CPU con quattro thread,
batch 256/1024 e finestra 60 s (include metriche train/validation, esclude
checkpoint e grafici): GRU(32) 31,34 s training + 6,66 s valutazione = 38,00 s;
GRU(64 -> 32) 165,73 s + 23,50 s = 189,22 s. La proiezione sulle due reti,
sei fold e 20 epoche e circa 7,6 ore di calcolo, soggetta al carico hardware.
Questo corregge la precedente estrapolazione da 30 s: il completamento delle
20 epoche entro cinque ore non e garantito e puo richiedere --resume.
I microbenchmark brevi risultano piu ottimistici e non sono usati come garanzia.

La CLI accetta --windows e --architectures; senza filtri conserva la griglia
originale di 16 configurazioni. Il sottoinsieme viene congelato in experiment.json
e ripristinato con --resume. Comparazione e congelamento considerano solo le
configurazioni selezionate, e il congelamento richiede tutti i fold completi.

Il batch di valutazione e separato da quello di training; il refresh della barra
dei batch e limitato dalla frequenza di tqdm. I log riportano train_seconds,
evaluation_seconds ed epoch_seconds (quest'ultimo comprende i salvataggi).
Best e last sono gli unici checkpoint; metriche, curve e stato RNG sono conservati.

--max-hours 5 indica un budget **per invocazione**, riutilizzato automaticamente
alla ripresa e modificabile esplicitamente. Il controllo avviene tra i batch di
training e inferenza e prima delle epoche/fold. Si riserva fino a un minuto per
l'arresto. E un limite cooperativo: operazioni di I/O, preparazione dati e report
non sono interrompibili, quindi non garantisce un cutoff esatto al secondo.

Se scade durante un'epoca, resta valido last.pt dell'ultima epoca completata;
l'epoca parziale viene rieseguita ripristinando RNG e optimizer. Se non esiste
ancora un checkpoint, il fold riparte dal seed originale. Lo storico delle epoche
completate non si perde. status.json dichiara complete=false e reason=time_budget;
nessuna selezione finale viene prodotta da una CV incompleta. execution_limits.json
registra il budget operativo separatamente dall'identita scientifica della run.

I risultati v2 non vengono modificati. Il nuovo codice cambia l'hash di identita:
i vecchi checkpoint v2 non possono essere ripresi con questo codice. Il nuovo
esperimento usa reports/gru_v3 e riparte da zero.

## CLI dalla root del repository (PowerShell)

Avvio completo, 2 architetture x 6 fold x 20 epoche:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --dataset data/processed/gru_dataset_v2 --output reports/gru_v3 --windows 60 --architectures 32 64x32 --epochs 20 --batch-size 256 --eval-batch-size 1024 --learning-rate 0.001 --seed 42 --device cpu --threads 4 --max-hours 5
```

Ripresa con le stesse impostazioni e un nuovo budget di cinque ore:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v3 --resume
```

In alternativa, selezione esplicita di un checkpoint esistente (riprende anche
il resto dell'esperimento):

```powershell
.venv/Scripts/python -B scripts/train_gru.py --cv --output reports/gru_v3 --resume reports/gru_v3/configurations/w060_gru32/fold_01/checkpoints/last.pt
```

Dopo CV completa e revisione dei risultati, refit sui 48 e test sui 12:

```powershell
.venv/Scripts/python -B scripts/train_gru.py --evaluate-test --dataset data/processed/gru_dataset_v2 --frozen-config reports/gru_v3/frozen_config.json --output reports/gru_v3_test --max-hours 5
```

Refit esplicito sull'intero dataset a configurazione congelata (nessun test indipendente residuo):

```powershell
.venv/Scripts/python -B scripts/train_gru.py --fit-all --dataset data/processed/gru_dataset_v2 --frozen-config reports/gru_v3/frozen_config.json --output reports/gru_v3_all --max-hours 5
```

Per riprendere i refit, usare lo stesso mode/output con --resume.

## Verifica

Suite eseguita: `pytest tests -q --ignore=tests/_generated --ignore=tests/test_prescription_plot_gaps.py`:
117 passed, 1 skipped. Il test plotting escluso ha un problema fontTools/Windows
preesistente. Verificati subset CLI, batch inference, riuso e override del budget,
ripresa esatta dopo interruzione in training e validation, refit congelato e
flusso originale delle 16 configurazioni. Il training completo reale non e stato avviato.
