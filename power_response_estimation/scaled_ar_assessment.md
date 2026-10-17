# Esito del confronto D R D

Questa specifica versione a due scale non viene promossa rispetto ai modelli precedenti.
Sulla validation l'interval score libero passa da 301.11 W (scala unica ristimata) a
301.90 W (due scale); migliora soltanto in 5 workout su 12. La banda media aumenta
da 237.03 a 239.16 W, con copertura 88.85% e 89.04%, rispetto all'80% nominale.

Nei 107 lap con parte stabile valutabile, il rapporto mediano SD simulata/reale
passa da 1.544 a 1.533. La sovradispersione dei plateau rimane praticamente invariata.
Il precedente GARCH variance targeting aveva rapporto 1.352 e interval score libero
286.52 W; ha comunque il limite di sottocopertura nelle transizioni gia documentato.

Il fit train converge alle stesse soluzioni dalle tre partenze. SD marginali:
92.68 W per la scala unica, 92.06 W base e 103.59 W transizione per le due scale.
La NLL a un passo validation migliora lievemente (5.2947 -> 5.2858), senza beneficio
nel criterio principale delle evoluzioni libere e della variabilita interna ai lap.

Questo risultato riguarda la parametrizzazione a due scale, soglia30s e media
residua congelata; non confuta la famiglia generale di covarianza D R D.
Non vengono introdotte altre covariate, effetti per lap o nuove forme di varianza
per compensare il risultato negativo. Nessun modello originale viene sostituito.

Tabelle riproducibili: scaled_ar_summary.csv, scaled_ar_lap_summary.csv e
scaled_ar_metrics.csv. Metodo in scaled_ar_report.md; pagina scaled_ar.html.
