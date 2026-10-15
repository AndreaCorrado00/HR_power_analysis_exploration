# Prescrizioni inferite dai lap

Dataset sintetico: non rappresenta piani originali verificati. Nessun training eseguito.

| Misura | Valore |
|---|---|
| input_files | 60 |
| exported_workouts | 60 |
| excluded_no_laps | 0 |
| source_errors | 0 |
| excluded_no_usable_laps | 0 |
| excluded_unassigned_laps | 0 |
| laps | 1521 |
| assigned_laps | 1521 |
| numeric_target_laps | 1430 |
| maximal_laps | 91 |
| unassigned_laps | 0 |
| blocks | 11 |
| measured_samples | 407236 |
| samples_with_target | 404761 |
| samples_with_prescription | 406735 |
| samples_outside_laps | 501 |

## Protocolli candidati

- multiphase_repeats_candidate: 5
- extensive_repeats_candidate: 3
- alternating_repeats_candidate: 2
- 30_15_candidate: 1

## Indicatori per lap (non mutuamente esclusivi)

- fit_average_differs_from_sample_mean: 849
- maximal_by_dataset_convention: 91
- missing_or_invalid_power_samples: 19
- outside_indicative_duration: 1058
- overlapping_categories: 24
- recording_gaps: 124
- rounded_target_outside_observed_category: 28
- shared_repeat_phase_target: 85
- timer_elapsed_difference: 147

## Interpretazione

- Media ricalcolata dai campioni del lap; avg_power FIT conservato per confronto.
- Zero incluso; valori mancanti/non finiti/negativi esclusi solo dalla media e conteggiati.
- Nessun campione filtrato, interpolato, riscalato o eliminato dal file samples.
- Estremi lap inclusivi; in caso di sovrapposizione il lap successivo possiede il campione.
- Fuori dai lap: lap_index=0 e target vuoto. Nessun riempimento dei gap.
- Durate effettive conservate; durata ideale inferita solo per sequenze ripetute.
- Target numerici: media del lap arrotondata a 5 W; mediana delle medie per fasi condivise.
- Modello potenza: rounded_observed_mean; tolleranza ripetute: 0.05.
- prescription_kind distingue power (watt), maximal (categorico) e unassigned.
- Un lap maximal e' assegnato, anche se power_target_w resta vuoto: nessun watt massimale inventato.
- Policy oltre Z6: categorical_maximal; selezione: all_laps_assigned.
- Massimale oltre 488 W e' una convenzione del dataset, non prova di sforzo fisiologicamente massimale.
- Le tolleranze sono euristiche esplicite, non stime di accuratezza o confidenza.
- Split futuri per sessione/tempo; medie e diagnostica osservate non sono input prescritti.
- Un piano inferito dalla traccia target non costituisce validazione su prescrizioni prospettiche.

## Dataset definitivo segmentato

Tutti i campioni originali conservati. Nessuna interpolazione, nessun filtro o taglio per durata minima.

{"power": 602, "hr": 571, "dynamics": 612}

Gli ID di segmento sono locali al workout e al segnale; 0 indica dato non osservato/valido. power_target_valid indica potenza misurata valida con prescrizione; dynamics_target_valid richiede anche HR valida. Queste maschere non sono garanzie di assenza di artefatti. I frammenti mantengono il lap originale: non diventano nuove ripetute. Le pause non sono potenza zero imputata. Split futuri per sessione/tempo.
