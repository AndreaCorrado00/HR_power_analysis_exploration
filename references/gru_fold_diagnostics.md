# Diagnostiche descrittive train/validation GRU

Protocollo approvato il 2026-10-12 per `reports/gru_v1/w030_gru32/fold_01`:
12 workout train, 6 validation, contesto causale 30 s. Nessun retraining, nessun
uso del test finale, nessuna modifica al codice GRU congelato nei checkpoint.

Implementazione: `src/power_hr_eda/gru_diagnostics.py`; CLI:

```powershell
.venv/Scripts/python -B scripts/gru_fold_diagnostics.py --run reports/gru_v1/w030_gru32/fold_01
```

Output: sottocartella `diagnostics/` del run. Rifiuta directory esistenti;
per ripetere usare `--output` con un nuovo percorso. Report con 7 figure PNG,
riepiloghi per split/workout, eventi, lap originali, frammenti e statistiche
per finestra. Manifest con split, hash sorgenti del manifest del dataset,
hash del run, codice diagnostico e tabella dei lap.

## Definizioni

- Stessa maschera del training: potenza reale finita >=0, segmento valido,
  prescrizione numerica valida oppure massimale. Zeri e campioni validi durante
  pause mantenuti. Nessun filtro, interpolazione o rimozione di anomalie.
- Verifica dello scaler salvato rispetto al fitting sui soli workout train.
  Le diagnostiche operano direttamente in W/W², senza fitting sulla validation.
- Varianza di popolazione (`ddof=0`) globale, per workout e nelle finestre
  causali da 30 campioni a 1 s; ciascun endpoint compare una volta.
- Finestre con contesto abbreviato ai confini separate dalle complete. Nessuna
  finestra attraversa gap, campioni invalidi, cambi di timer o segmento.
- Prescrizione dinamica: almeno un cambio numerico o del flag massimale con
  entrambi i lati dentro la finestra. Il cambio al bordo sinistro non conta.
- Stabilità reale: deviazione standard <=20 W; sensibilità a 10 e 30 W.
  Stabilità della prescrizione non implica stabilità della potenza reale.
  Una finestra con un solo campione ha SD=0: le abbreviate non sono aggregate
  alle complete nella classificazione. Soglie descrittive, non fisiologiche.
- Transizioni: cambi della prescrizione nello stesso segmento continuo;
  frequenza per ora osservata (numero campioni validi /3600). Ampiezza numerica
  solo se entrambe le prescrizioni sono numeriche. Massimali: ingresso/uscita
  categorici, senza attribuzione di watt.
- Fasi: lap originali e loro `duration_s`; frammenti definiti dai confini
  lap-segmento. Durata frammento = numero campioni validi x1 s. I gap non creano
  nuovi lap. Durata originale e durata osservata non sono intercambiabili.
- Massimale: flag della prescrizione. Alta potenza: valore reale >325, >390,
  >488 W; categorie sovrapponibili. Riportare anche distribuzione della potenza
  reale all'interno dei massimali.
- Baseline `P_hat=P_prescritta`, nessun fitting, RMSE per campione e per workout.
  Massimali esclusi e copertura esplicita. RMSE globale calcolata su tutti i
  residui numerici, distinta dalla media delle RMSE dei workout.

Le prescrizioni sono inferite dalla stessa traccia reale. Questa baseline è
una ricostruzione condizionata, non misura aderenza a piani indipendenti. Il suo
errore sui soli campioni numerici non è direttamente comparabile all'errore GRU
che include anche massimali. Le differenze train/validation sono descrittive:
non dimostrano da sole una causa del divario predittivo.
