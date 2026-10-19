# Rifinitura delle attività complete — protocollo 2026-09-29

Decisione approvata: applicare a tutte le attività dello ZIP originale,
senza modificare i FIT né l'export CSV originale. Nessuna identificazione o
valutazione fuori campione fa parte di questa trasformazione.

## Ordine delle operazioni

1. Verificare hash dell'archivio originale e di ciascun CSV nell'export.
2. Escludere l'intera attività se almeno una distanza tra timestamp consecutivi
   è strettamente maggiore di 10 s, prima di qualsiasi taglio. Vale anche per
   possibili pause: non si attribuisce una causa ai salti. Esattamente 10 s è ammesso.
3. Calcolare le posizioni sulla durata temporale originale, senza iterare le
   percentuali dopo un taglio. Se manca P o HR nel primo 10%, eliminare tutto
   fino all'ultimo dato mancante in quella coda; nell'ultimo 10%, eliminare
   dal primo dato mancante fino alla fine. Estendere il taglio fino a trovare
   entrambi i segnali validi. I punti esattamente al 10% o 90% sono interni.
4. Riempire i salti temporali rimasti inserendo righe al passo nominale di 1 s.
   Le altre covariate restano vuote nelle nuove righe: non vengono inventate.
5. Riempire gli altri valori mancanti di P/HR come descritto sotto.
6. Azzerare elapsed_seconds sul primo campione conservato; mantenere timestamp
   assoluti, source_elapsed_seconds e source_row_index (indice originale base 0).

## Interpolazione stocastica locale

Metodo adattato per questo dataset, non replica di un metodo pubblicato e non
affermazione di ricostruzione fisiologica. Si assume che la variabilità locale
nelle vicinanze sia indicativa di quella non osservata. Non è verificabile
direttamente nel buco e non garantisce preservazione della distribuzione reale.

Per ciascun segnale separatamente, il trend è la retta tra le due osservazioni
valide ai lati del buco. Le finestre di riferimento si estendono a sinistra e
destra delle ancore per una durata pari all'intervallo tra ancore meno 1 s.
Usano solo valori originariamente osservati, mai valori già imputati; si fermano
al primo dato mancante o all'estremo. Finestre accorciate sono segnalate.

Da ciascuna finestra con almeno 3 campioni si sottrae una retta OLS.
Si ricampionano i residui mediante blocchi circolari, scegliendo casualmente
finestra e origine. Lunghezza blocco: radice quadrata arrotondata del numero
di campioni mancanti, limitata alla lunghezza della finestra più breve.
È una scelta euristica fissata, non ottimizzata sui risultati del fitting.

Per buchi di almeno 3 campioni si rimuovono media e trend dei residui generati
e se ne normalizza la deviazione standard a quella dei residui di riferimento,
quando la varianza generata è non nulla. Si sommano al trend tra le ancore.
Per 1–2 campioni non si impongono simultaneamente trend e varianza campionaria;
il limite è segnalato. Senza una finestra di almeno 3 campioni si usa il solo
trend e si marca insufficient_reference. Valori sintetici negativi sono
troncati a zero, con conteggio esplicito. Ogni limitazione è registrata.

Non si garantiscono autocorrelazione, estremi, correlazione P–HR o identità
della distribuzione. Si registrano deviazione standard e ACF lag 1 dei residui
di riferimento e generati per consentirne l'ispezione. L'uguaglianza della
deviazione standard imposta non è una validazione dell'accuratezza.
Seed base 42; seed per evento derivato da hash FIT, segnale e tempo originale,
per indipendenza dall'ordine di elaborazione.

## Tracciabilità e verifiche

Flag per riga: activity_modified, activity_trimmed, timestamp_inserted,
power_imputed, hr_imputed. Il flag di attività è ripetuto su tutte le sue righe;
quelli di imputazione individuano soltanto le celle sintetiche. Manifest con
hash, parametri, conteggi e qualità ricalcolata; qualità/conversione originali
restano come provenienza. metadata/activity_audit.json elenca anche gli esclusi
e gli intervalli responsabili; metadata/interpolation_events.json descrive
ogni buco ricostruito. Sono conservate le identità originali delle attività.

Verifiche: soglie e code su casi controllati; riproducibilità a seed fisso;
immutabilità delle sorgenti; nessuna modifica ai valori osservati conservati;
segnali risultanti finiti; compatibilità con il lettore ZIP dell'app.
I valori sintetici non sono misure: non usarli come ground truth per metriche
di predizione. Il dataset rifinito non certifica la validità del modello.

Riproduzione dalla radice repository:

```
.venv/Scripts/python.exe scripts/refine_activities.py
```

Il comando rifiuta di sovrascrivere un output esistente; usare `--output` per
una ripetizione. L'output contiene CSV e metadati, non FIT riscritti.
