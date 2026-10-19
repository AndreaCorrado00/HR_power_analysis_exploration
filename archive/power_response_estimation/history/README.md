# Storico degli esperimenti sulla varianza

Il riferimento attivo e **dinamica ordine 4 + AR(2) a varianza costante**.
Gli altri tentativi sono conservati in [variance_experiments.zip](variance_experiments.zip),
con inventario e SHA256 in [variance_experiments_manifest.json](variance_experiments_manifest.json).
Lo ZIP include codice, dati derivati, report, pagine HTML, ECharts locale, test e
snapshot dei file baseline da cui dipendevano gli esperimenti. Non include i dati
raw/processati sorgente, che restano nelle directory originali del repository.
`legacy.zip`, nella directory superiore, e lo storico precedente e resta invariato.

| Esperimento | Report nello snapshot | Esito principale |
|---|---|---|
| Eteroschedasticita e intervalli | `diagnostics/report.md`, `diagnostics/interval_report.md` | Dipendenza dei quadrati e differenze fra contesti; non garantisce migliori simulazioni libere |
| AR + GARCH originale | `garch_report.md` | Migliora previsione condizionata, peggiora score libero |
| GARCH variance targeting / varianza contestuale | `variance_report.md` | Targeting migliore score libero tra i tentativi; limiti su transizioni e code. Conservato come alternativa, non attivo |
| SD interna ai lap | `lap_variability_report.md` | Sovradispersione dei tratti stabili |
| Profili e test dopo i salti | `transition_report.md`, `transition_test_report.md` | Indicazione di varianza iniziale maggiore, validation imprecisa |
| Scala marginale del residuo + AR normalizzato | `scaled_ar_report.md`, `scaled_ar_assessment.md` | Due scale non risolvono la sovradispersione |
| Offset casuale per lap + AR | `lap_ar_report.md` | Varianza offset stimata zero; target ricostruiti dalle medie limitano identificazione |

Tutti i percorsi della tabella sono relativi a `power_response_estimation/` dentro
lo ZIP. I commit antecedenti alla pulizia restano nella branch `analysis/ar-garch-11`;
il commit esatto dello snapshot e registrato nel manifest.

## Verifica e ripristino

Verifica senza modificare i file attivi:

```powershell
.venv/Scripts/python -B power_response_estimation/history/archive_tools.py verify
```

Per consultare le vecchie pagine, estrarre lo ZIP **in una directory separata**:

```powershell
Expand-Archive -LiteralPath power_response_estimation/history/variance_experiments.zip -DestinationPath tmp/variance-history
```

Aprire per esempio `tmp/variance-history/power_response_estimation/variance.html`.
Le pagine sono offline e non richiedono i dati sorgente.
Per rieseguire le analisi, lo snapshot deve avere alla propria radice la stessa
directory `data` con i file sorgente e gli hash attesi, e un ambiente compatibile
con `requirements.txt` e con le versioni registrate nei modelli/manifest.
Eseguire i comandi dei report dalla radice dello snapshot, non dalla directory attiva.
Lo ZIP non rende portabili gli hash dei vecchi manifest attraverso trasformazioni
dei file o cambi di newline: conserva invece i byte esatti di questo workspace.

`archive_tools.py prune` e un'operazione di manutenzione della pulizia, non un comando
di analisi. Rimuove solo membri esplicitamente indicati nel manifest, dopo verifica
dello ZIP e dei byte correnti, senza cancellazioni ricorsive. Non usarlo per eliminare
nuovi esperimenti. L'archivio esistente non viene sovrascritto da `create`.

La pulizia riduce i file operativi, non riscrive la storia Git e non riduce gli
oggetti gia conservati nella directory `.git`.
