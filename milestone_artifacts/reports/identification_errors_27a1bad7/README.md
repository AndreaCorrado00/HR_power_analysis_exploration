# Diagnostica errori identificazione

Run `27a1bad774ee41779fdc42cde0110869`; manifest `webapp\model_identification_app\storage\runs\20260928T210437Z__Dataset-importato__p1d__raw__70-10-20__s42__n8-f42__27a1bad7.json`.
34 fallimenti su 92 record train. Tutti bloccati dal controllo di finitezza prima del fitting; nessuna valutazione fuori campione.

CSV: inventario completo con conteggi verificati sui blob originali (SHA-256 verificato). JSON: record falliti salvati, senza alterazioni.

Grafici: selezione intenzionale di un caso con un solo dato potenza mancante (106) e un caso con entrambi i segnali incompleti (002); non rappresentano una selezione statistica. Linee viola: tempi con almeno un dato mancante. Zoom sul primo campione mancante, +/- 1 minuto. Nessun filtro, interpolazione, rifitting o modifica dei dati.

Il messaggio "Servono almeno 4 osservazioni finite nel segmento" copre sia meno di 4 campioni sia qualsiasi valore non finito: qui tutti i record hanno oltre 4 campioni.
