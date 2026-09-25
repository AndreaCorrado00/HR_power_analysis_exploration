# Dataset Exploration

SPA Vue locale per ispezionare serie di potenza e frequenza cardiaca nei file
FIT, selezionare lap o blocchi di lap contigui ed esportare serie temporali
riproducibili.

## Avvio

Dal root del repository:

```powershell
.\webapp\dataset_exploration\start.ps1
```

Il processo seleziona una porta libera e stampa l'indirizzo corrente. I FIT
sorgente sono letti senza essere modificati.

## Uso

1. Usare **Sfoglia cartelle / ZIP** per navigare sul PC e dentro gli archivi,
   spuntare i FIT desiderati oppure importare la cartella e le sottocartelle.
   Il percorso iniziale è `dataset/cleaned_only_road_activieties.zip`.
   La spunta **Seleziona tutti i FIT** seleziona o deseleziona i file della
   cartella visualizzata; la selezione parziale è indicata sulla spunta.
2. Indicare, se necessario, la durata massima in ore e caricare il dataset.
3. La griglia separa le attività con lap utilizzabili da **Esclusi
   dall'estrazione**. Ogni esclusione riporta il motivo.
4. Attivare facoltativamente W/kg, % FCmax o % FC di soglia nella sezione di
   caricamento, dichiarando i rispettivi parametri.
5. Aprire una scheda per usare lo zoom temporale. Ogni lap è inizialmente un
   segmento: si possono unire segmenti adiacenti e annullare ogni unione.
6. Selezionare uno o più segmenti risultanti e aggiungerli alla coda di
   esportazione.
   Nel grafico dell'attività, l'arancione indica i lap selezionati e il verde
   quelli già aggiunti alla coda. Le aree seguono i confini temporali dei lap.
7. Aprire **Pre-esportazione** per controllare grafici, durata e campioni di
   tutti i segmenti accodati, rimuoverli oppure esportarli insieme.
8. Indicare facoltativamente una destinazione ZIP. Se la destinazione non è
   scrivibile, il browser scarica lo ZIP.

Errori e messaggi di esito compaiono in popup in basso a destra, anche sopra
le finestre aperte. Si chiudono automaticamente oppure con il pulsante ×.

Lo ZIP contiene un CSV per segmento e `manifest.json`. I CSV conservano
timestamp originale, tempo relativo da zero, potenza e frequenza cardiaca
misurate ed eventuali colonne normalizzate. Il manifest dichiara sorgenti,
lap, unità, formule e parametri di normalizzazione.

Gli ZIP vengono letti senza estrarli su disco. Lo ZIP di esempio contiene
131 voci marcate come collegamenti simbolici: il loro contenuto è il percorso
del FIT originale, non un FIT binario. Per queste voci viene letto il target
locale; se manca, l'attività viene esclusa con un messaggio specifico. Uno ZIP
con i FIT incorporati è invece autonomo. Il caricamento conserva in memoria
le attività decodificate per grafici, anteprime ed esportazione; un nuovo
caricamento azzera selezioni e coda di esportazione della sessione precedente.

## Indirizzo verificato

`127.0.0.1:57212`

La porta viene scelta nuovamente a ogni avvio; usare sempre anche l'indirizzo
stampato dal processo corrente.

## Elaborazione dei segmenti esportati

Aprire **Elaborazione dataset**, scegliere `dataset_segments.zip`, usare
**Seleziona tutti** oppure selezionare singoli segmenti. Questa pagina importa
i CSV e il manifest, senza richiedere i FIT originali. Il caricamento è separato
da quello della pagina di estrazione. È mantenuto un solo dataset di elaborazione
per processo locale; importarne un altro invalida l'identificativo precedente.

La finestra è **3 secondi di default**, con **5 e 10 secondi** come sole
alternative. Un'unica finestra viene applicata a tutti i segmenti selezionati e
a entrambi i segnali. Peso (kg), FC massima e FC di soglia (bpm) sono riferimenti
globali fissi, dichiarati dall'utente; ciascuna normalizzazione è facoltativa.

Premere **Elabora e aggiorna anteprima**, scegliere il segmento da controllare
e confrontare originali e medie nel grafico con zoom. Le unità normalizzate sono
disponibili nel grafico quando attivate. Cambiare parametri o selezione invalida
l'anteprima e richiede una nuova elaborazione prima di **Esporta ZIP**.
Il download si chiama `dataset_segments_processed.zip`.

### Contratto scientifico e formato v2

- Per il campione a tempo `t`, media aritmetica dei valori osservati in
  `[t-W/2, t+W/2)`. A 1 Hz questo include esattamente 3, 5 o 10 campioni nelle
  finestre interne. Con W=10, l'intervallo semiaperto seleziona cinque campioni
  precedenti, quello corrente e quattro successivi: l'asimmetria di mezzo
  campione è dichiarata e uguale per potenza e HR.
- Il passo di riferimento è la mediana delle differenze temporali del segmento.
  Un gap `dt > 1.5 * passo_mediano` interrompe il blocco di calcolo. Con un solo
  campione si usa 1 secondo come riferimento per la sola diagnostica dei bordi.
- Le finestre vengono troncate ai bordi dei segmenti e dei blocchi. La colonna
  `ma_sample_count` indica i campioni osservati nella finestra. `ma_incomplete`
  indica che il supporto temporale richiesto supera quello del blocco, assumendo
  che ogni campione copra mezzo passo mediano prima e dopo il timestamp.
- Nessuna interpolazione, ricampionamento, rimozione di outlier o eliminazione
  degli zeri. Un dato mancante propaga un valore mancante nella media di quel
  segnale; l'altro segnale viene calcolato indipendentemente. I timestamp non
  crescenti e le incongruenze tra CSV e manifest sono errori espliciti di import.
- Le colonne misurate restano `power_w` e `heart_rate_bpm`; le medie sono
  `power_ma_w` e `heart_rate_ma_bpm`. Identificativi, timestamp, tempo relativo e
  altre colonne sorgente sono conservati.
- Normalizzazioni: `power_w_kg = power_w / weight_kg`,
  `hr_pct_max = 100 * heart_rate_bpm / hr_max_bpm`,
  `hr_pct_threshold = 100 * heart_rate_bpm / hr_threshold_bpm`.
  Le stesse formule applicate alle medie producono `power_ma_w_kg`,
  `hr_ma_pct_max`, `hr_ma_pct_threshold`. Riferimenti attivi finiti e positivi.
- Reimportare un export v2 rimuove le precedenti colonne derivate e ricalcola
  sempre dagli originali, evitando filtraggi o normalizzazioni cumulativi.
- Il manifest v2 registra parametri, formule, unità, convenzioni, versione
  dell'algoritmo, data UTC, SHA-256 dello ZIP importato e manifest sorgente.
  L'importazione legge formati v1/v2 senza estrazione su disco, con limiti di
  256 MiB per ZIP, 512 MiB espansi e 10.000 voci.

È preprocessing offline, non un modello fisiologico: la media usa campioni
successivi e attenua le transizioni. Nei futuri esperimenti predittivi evitare
finestre attraverso confini training/test e mantenere la HR misurata come
riferimento separato dalla HR smussata. Non deduplicare automaticamente campioni
condivisi da segmenti distinti: il raggruppamento per attività resta disponibile
per costruire split senza leakage.
