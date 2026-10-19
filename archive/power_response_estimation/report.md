# Power response estimation

Modello condiviso: risposta dinamica di ordine **4** + AR(2). LS predefinito, Huber opzionale. Target ricostruiti: risultati condizionati al dataset.

## Selezione sul validation

| Ordine | RMSE medio W | Delta dal migliore W |
| --- | ---: | ---: |
| 2 | 73.570 | 0.257 |
| 3 | 73.512 | 0.199 |
| 4 | 73.314 | 0.000 |

La selezione usa target + r + media accessoria del fit. Nelle ablazioni la media del residuo appartiene invece all’AR: disattivarlo rimuove anche quella media. Non avviene alcun rifit.

## Valutazione delle quattro combinazioni

RMSE medio per workout della **previsione media**, senza feedback osservato. Gli errori della prima traiettoria casuale sono separati in `metrics.csv` e nella pagina.

| Split | Dinamica | AR | RMSE medio W | MAE medio W | Bias medio W |
| --- | --- | --- | ---: | ---: | ---: |
| validation | False | False | 77.574 | 52.054 | 0.062 |
| validation | False | True | 77.596 | 52.138 | -0.816 |
| validation | True | False | 73.270 | 49.560 | 0.013 |
| validation | True | True | 73.238 | 49.495 | -1.064 |
| test | False | False | 77.588 | 49.028 | 0.396 |
| test | False | True | 77.599 | 49.086 | -0.362 |
| test | True | False | 74.627 | 47.307 | 0.404 |
| test | True | True | 74.601 | 47.261 | -0.512 |

## Interpretazione e controlli

Parametri: rango Jacobiano 10/10; raggio spettrale 0.920646. Stime, IC locali per cluster workout, poli/zeri e tentativi multistart sono in `model.json` e nella pagina.
Confrontare transitori e plateau: un buon RMSE non rende il residuo automaticamente indipendente dal target. Gli intervalli sono locali, non prova di ripetibilità fisiologica.
Nel modo simulazione il residuo visualizzato è reale − traiettoria simulata: non coincide con l’innovazione AR. Le innovazioni osservate sono salvate nei dati della pagina come diagnostica separata.
Il vecchio test è già stato esaminato: il confronto è descrittivo. Coefficienti sempre stimati sul training, senza refit su train+validation.

## Uso della pagina

Aprire `index.html`. Rotella per zoom, trascinamento per scorrere, barra inferiore per selezionare/spostare l’intervallo. I quattro pannelli condividono il tempo. Interruttori dinamica/AR e modalità media/simulazione aggiornano curve, residui, RMSE, MAE e bias. Scegliere metriche dell’intero workout o della finestra visibile.
La stessa realizzazione AR rimane fissa cambiando contributi e zoom. Nessuna linea attraversa gap reali. Le bande P10–P90 sono puntuali, senza incertezza parametrica; clipping a zero sulla sola uscita, anche sui limiti della banda. La previsione media e la media analitica dopo clipping; i contributi e le innovazioni restano latenti.

Codice, modello, pagina, risultati e questo report stanno nella stessa cartella. Comandi e convenzioni in `README.md`.
