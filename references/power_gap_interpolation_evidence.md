# Buchi di potenza: evidenza empirica e proposta

Analisi del 2026-10-11 sul dataset `prescribed_workouts_v3_verified`.
Richiesta: formulare una proposta basata sui dati, misurando l'effetto
dell'interpolazione. Nessuna modifica a FIT, prescrizioni o campioni esportati.

Aggiornamento dopo finalizzazione: il dataset corrente e'
`prescribed_workouts_final`, con gli stessi campioni osservati e le annotazioni
di segmentazione. I riepiloghi e il PDF di questa analisi sono conservati sotto
`reports/prescription_diagnostics/power_gap_interpolation_benchmark` e
`reports/prescription_diagnostics/power_gap_interpolation_findings`.
Le finestre simulate e le directory esplorative originali sono state rimosse.
I comandi sotto rigenerano l'esperimento sul dataset finale in directory nuove;
i manifest archiviano la provenienza della precedente esecuzione.

## 1. Che cosa sono i buchi osservati

Sono stati riletti tutti i 60 FIT e confrontati i buchi con gli eventi `timer`
di arresto e ripartenza. L'intervallo di pausa e' [stop, start); si contano
gli istanti nominali a 1 Hz mancanti che ricadono in tale intervallo.
La potenza durante una pausa non viene assunta uguale a zero.

- 295 buchi delimitati da campioni validi: 13.117 secondi mancanti.
- 248 buchi si sovrappongono a pause registrate del timer.
- 12.658 secondi mancanti ricadono nelle pause: **96,50%** del totale delimitato.
- 47 buchi senza sovrapposizione a pause: **179 secondi**, in 6 allenamenti.
- Altri 280 secondi mancanti sono ai margini dei buchi che includono pause.
- 5 tratti mancanti all'inizio/fine non hanno entrambi gli estremi e non sono
  candidati a interpolazione; sono esclusi dal denominatore del 96,50%.

'Nessuna pausa registrata' non identifica automaticamente la causa del dropout.
Questi dati sostituiscono la precedente ipotesi basata sui soli estremi a zero:
la presenza delle pause e' ora documentata dai FIT.

## 2. Esperimento controllato

Si nascondono porzioni di segnale realmente osservate, mantenendone la potenza
come verita' di confronto. Non e' possibile misurare direttamente l'errore
all'interno di un buco reale, dove la verita' non e' disponibile.

- 139.096 finestre simulate nei 60 allenamenti, seed 3252026.
- Durate guida: 1, 2, 5, 10, 15, 30, 60, 120 secondi; inoltre tutte le durate
  effettive dei buchi delimitati <=120 s presenti nel dataset.
- Ogni finestra e i 5 campioni esterni su ciascun lato devono essere finiti,
  non negativi e campionati senza interruzioni a 1 Hz.
- Finestre non sovrapposte all'interno di ogni coppia allenamento/durata;
  massimo 80 per durata guida e 25 per le altre durate, campionate con seed fisso.
  Finestre di durate diverse possono sovrapporsi: non sono repliche indipendenti.
- Primi 40 allenamenti cronologici separati dagli ultimi 20; le regole non sono
  state ottimizzate sui 20 successivi, sui quali sono riportati i risultati sotto.
  Non e' stato addestrato un modello, ne' selezionata una soglia tramite fitting.
- Metodi: retta fra campioni precedente e successivo; mantenimento dell'ultimo
  valore come confronto semplice. Nessun filtro sulla potenza originale.
- MAE medio calcolato prima per allenamento, poi con uguale peso per allenamento.
  Intervalli al 95% tramite 1.000 bootstrap di sessioni, non di singoli campioni.
- La 'stabilita'' e' un criterio diagnostico fissato prima di leggere i risultati:
  range complessivo <=20 W sui 5 valori prima e 5 dopo il buco. Non usa valori
  nascosti; non e' una soglia fisiologica o una garanzia di ricostruzione.

Sono inoltre conservati analoghi dei buchi reali a durata esatta e stesso
contesto (stesso lap numerico, estremi zero/nonzero, stabilita'). Alcuni contesti
hanno pochi analoghi: `matching_workouts` e `matching_windows` consentono di
verificarlo. Questi errori non sono errori osservati dentro i buchi reali.

## 3. Errore sui 20 allenamenti successivi

| Secondi nascosti | MAE lineare W [IC95%] | MAE ultimo valore W | MAE lineare nello stesso lap numerico W |
|---|---:|---:|---:|
| 1 | 21,4 [19,3-23,9] | 26,1 | 21,0 |
| 2 | 23,3 [21,4-25,6] | 30,4 | 22,1 |
| 5 | 32,0 [29,3-35,2] | 44,2 | 29,8 |
| 10 | 38,2 [34,6-42,4] | 50,7 | 34,4 |
| 15 | 44,8 [40,6-49,4] | 60,7 | 38,2 |
| 30 | 53,1 [47,9-59,0] | 69,5 | 41,4 |
| 60 | 66,1 [59,9-73,0] | 78,3 | 46,6 |
| 120 | 71,9 [65,7-79,3] | 86,5 | 50,6 |

Il vantaggio della retta rispetto all'ultimo valore si ripete nei primi 40
allenamenti (per 5/60/120 s: 35,6/73,0/80,1 W contro 46,5/87,2/94,2 W).
Questo confronto non rende la retta una ricostruzione fedele del profilo.

Nei test a 5 s la retta conserva il **38% della variazione totale**; a 60 s il
**6%**. La metrica e' somma delle differenze assolute fra campioni consecutivi,
estremi inclusi, ricostruita / osservata, aggregata sulle finestre. Non misura
la percentuale di energia o ampiezza del segnale conservata e comprende anche
la variabilita' di misura. Mostra direttamente quanto viene appiattita la traccia
osservata che l'utente vorrebbe riprodurre.

Nei tratti con stesso lap numerico ed estremi stabili il MAE scende a 5,5 W
(1 s), 5,3 W (2 s), 9,7 W (5 s). I campioni sono pero' limitati: rispettivamente
36, 35 e 26 finestre, in 17, 14 e 14 allenamenti. A 60 e 120 s restano solo
5 e 4 finestre, insufficienti per una regola affidabile generalizzata.

Applicando ai buchi REALI il filtro 'nessuna pausa + stesso lap numerico +
estremi stabili + <=5 s' restano **2 buchi, 7 secondi complessivi**:
250518083010 (3 s) e 250629084934 (4 s), entrambi con estremi zero.
La regola piu' stretta <=2 s non seleziona alcun buco reale.
Quindi una interpolazione selettiva aggiungerebbe pochissima informazione qui.

## 4. Quanto costa eliminare porzioni

Separando a ogni buco della potenza, senza concatenare, si ottengono 355 tratti
continui. Sono preservati tutti i 406.404 campioni validi con prescrizione
(numerica o massimale); 501 campioni fuori lap non entrano nel denominatore.
I tratti possono contenere parti di lap: vanno conservati ID e offset originali,
senza chiamare questi frammenti lap completi.

| Strategia diagnostica | Tratti | Campioni validi prescritti conservati |
|---|---:|---:|
| Tutti i tratti | 355 | 406.404 (100%) |
| Tratti con almeno 30 campioni | 313 | 405.919 (99,88%) |
| Tratti con almeno 60 campioni | 301 | 405.425 (99,76%) |
| Tratti con almeno 120 campioni | 273 | 403.025 (99,17%) |
| Una porzione per attivita', piu' lap completi poi piu' campioni | 60 | 194.720 (47,91%) |

Le prime quattro strategie mantengono rappresentati tutti i 60 allenamenti.
La soglia in tabella e' un numero di campioni a 1 Hz, non la differenza fra
timestamp estremi (che vale n-1 secondi). Sono sensibilita', non tagli applicati.
Le vecchie soglie di separazione 60/120 s conservavano buchi interni alle finestre:
non dimostravano continuita' o interpolabilita' di quelle porzioni.

## 5. Proposta motivata dai risultati, da implementare separatamente

1. **Dataset di riferimento senza interpolazione della potenza.** Conservare
   i campioni misurati, gli zeri e i missing originali; marcare i buchi associati
   a pause tramite eventi FIT. Le pause non sono potenza mancante da inventare.
2. **Mantenere tutti i 355 tratti continui**, collegati alla sessione, ai lap e
   alla prescrizione originali, con offset e confini espliciti. Nessuna
   concatenazione che faccia sembrare adiacenti tratti separati. Lo split futuro
   resta per sessione/tempo: i frammenti dello stesso workout non vanno separati
   fra training e test.
3. **Preservare anche i tratti brevi nel dataset master.** La tabella permette
   di scegliere successivamente una durata minima in funzione delle finestre
   richieste dal modello; 30 s non e' qui una soglia scientificamente ottimizzata.
4. **Nessuna regola automatica di interpolazione fino a 1-2 minuti.** Il costo
   in errore e appiattimento e' misurato. Un'eventuale copia interpolata per
   esigenze tecniche deve avere maschera dei valori sintetici e non usarli come
   verita' misurata nel training o nella valutazione.
5. L'opzione molto selettiva <=5 s con contesto stabile puo' restare un confronto
   opzionale; in questo dataset riguarda appena 7 s e non giustifica una pipeline
   di riempimento estesa. L'utilita' di ricostruire quei punti e' una scelta di
   costo/beneficio, non un fatto determinabile dai soli dati.

Questa proposta modifica la precedente raccomandazione generica di conservare
una sola porzione e separare a 60 s: l'evidenza mostra che conservare tutti i
tratti validi evita una perdita ampia senza introdurre potenza artificiale.

## 6. Limiti e riproduzione

Il test misura l'errore su dati osservati nascosti artificialmente. Le assenze
reali non sono casuali; i tratti integri possono differire dai buchi reali,
soprattutto dalle pause. Non si puo' dedurre che la potenza in una pausa fosse
uguale alla retta, a zero o alla media del lap. Nessuna metrica qui identifica
una soglia universale di errore accettabile per la futura rete.

```powershell
.venv/Scripts/python -B scripts/benchmark_power_gap_interpolation.py
.venv/Scripts/python -B scripts/report_power_gap_interpolation.py
.venv/Scripts/python -B -m pytest tests/test_gap_interpolation_benchmark.py tests/test_prescription_gaps.py -q -p no:cacheprovider
```

Gli output devono essere nuovi; il benchmark accetta `--output` per un'altra
destinazione. Il report usa le directory canoniche indicate qui sotto.

Artefatti:
- `reports/power_gap_interpolation_benchmark/`: finestre, metriche per durata e
  contesto, buchi reali con pause, intervalli timer, analoghi e manifest.
- `reports/power_gap_interpolation_findings/`: confronto della conservazione,
  tratti candidati, grafici PNG e PDF a 2 pagine con esempi al percentile 50/90
  dell'errore, scelti automaticamente.

Verifiche: 8 test superati su casi analitici e diagnosi dei buchi; nessun uso
dei campioni nascosti per stabilire il contesto; maschere della durata esatta;
assenza di sovrapposizione entro sessione/durata e di sessioni comuni fra i due
periodi; hash dei FIT, del dataset e degli output; controllo visivo dei grafici.
