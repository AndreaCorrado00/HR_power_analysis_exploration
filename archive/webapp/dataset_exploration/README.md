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
   Il percorso iniziale è la cartella sorgente scelta con `start-athlete.ps1`
   (`dataset/` del clone se non specificata); lasciare il campo vuoto per usarla.
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
caricamento azzera selezioni e coda della sola pagina Estrazione; le copie e le
voci di ricostruzione già caricate nelle altre pagine restano disponibili.

## Indirizzo verificato

`127.0.0.1:57212`

La porta viene scelta nuovamente a ogni avvio; usare sempre anche l'indirizzo
stampato dal processo corrente.

## Elaborazione dei segmenti esportati

### Uso diretto del dataset caricato

Non è necessario esportare e reimportare uno ZIP. Caricare una volta i FIT
da una cartella della repository o da un archivio nella pagina **Estrazione
dataset**, quindi aprire una scheda attività:

- selezionare i segmenti, anche dopo aver unito lap adiacenti, e premere
  **Elabora selezionati** o **Ricostruisci selezionati**;
- premere **Ricostruisci attività completa** per usare tutti i campioni della
  sessione, indipendentemente dai lap. È disponibile anche per attività senza lap;
- in Elaborazione o Ricostruzione, **Usa segmenti in pre-esportazione** carica
  i segmenti provenienti da Estrazione attualmente in coda;
- in Ricostruzione, il selettore **Attività completa** permette di scegliere
  direttamente tra le attività del dataset caricato.

Il trasferimento crea una copia indipendente in memoria. In Elaborazione i
segmenti ricevuti sono già selezionati: scegliere i parametri e premere
**Elabora e aggiorna anteprima**. In Ricostruzione viene aperta la prima
selezione con i blocchi dai lap. Un nuovo caricamento, diretto oppure ZIP, apre
una nuova copia senza eliminare le precedenti e senza svuotare la pre-esportazione.
**Caricamenti della sessione** permette di tornare alle copie precedenti:
Ricostruzione conserva bozze, modifiche e tagli; Elaborazione conserva selezione,
parametri, anteprima e disponibilità dell’export già calcolato. Un caricamento
fallito lascia attiva la copia precedente.

Ricaricare i FIT in Estrazione non altera le copie già aperte nelle altre
pagine. Ogni selezione diretta include l'identificativo del caricamento;
richieste riferite a un caricamento precedente vengono rifiutate invece di
usare accidentalmente nuovi file con lo stesso nome.

Il percorso diretto riusa in memoria lo stesso contratto di serializzazione
e validazione degli ZIP, senza scrivere file intermedi. Fitting, media mobile
e algoritmo di ricostruzione non cambiano. Le normalizzazioni sono scelte
nella pagina di Elaborazione e non vengono ereditate da Estrazione.
Il manifest registra `loaded_source`, sorgente e identità dell'attività.
Lo SHA-256 identifica l'archivio di campioni generato in memoria, non il FIT
originale. Le attività complete usano `selection_kind=whole_activity` e
`first_lap=last_lap=0` come marcatori di assenza di selezione lap.
I timestamp vengono ordinati, quelli non validi esclusi e i duplicati rimossi
conservando una sola osservazione; i conteggi sono registrati nel manifest.
Potenza o HR assenti sono rappresentate da valori mancanti. Nessuna
interpolazione o normalizzazione implicita viene aggiunta. I dati raw restano
immutati; tutte le copie in memoria richiedono export per essere conservate
dopo la chiusura o il riavvio del servizio.

Aprire **Elaborazione dataset**, scegliere `dataset_segments.zip`, usare
**Seleziona tutti** oppure selezionare singoli segmenti. Questa pagina importa
i CSV e il manifest, senza richiedere i FIT originali. Il caricamento è separato
da quello della pagina di estrazione. È mantenuto un solo dataset di elaborazione
per caricamento nel processo locale; importarne un altro conserva gli
identificativi e i dati precedenti fino al riavvio del servizio.

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

## Ricostruzione allenamenti

Aprire un’attività dal dataset FIT già caricato in Estrazione, oppure importare
uno ZIP di segmenti v1/v2. La pagina inizializza **un rettangolo per lap** con la
media della potenza osservata; i lap senza campioni validi restano senza target.
È una ricostruzione modificabile, non la prova della prescrizione del coach né
un modello fisiologico. Potenza e frequenza cardiaca originali sono conservate.

### Lavorare sul grafico

- Rotellina: scorrimento nel tempo. **Ctrl + rotellina** (anche Cmd su Mac): zoom
  attorno al puntatore. Trascinare lo sfondo per spostare la vista; sono disponibili
  anche frecce, barra orizzontale, Zoom +/− e **Mostra tutto**.
- Trascinare il bordo superiore per cambiare i watt, quelli laterali per cambiare
  la durata. Un confine condiviso modifica entrambi i blocchi adiacenti.
  Trascinare il corpo di un blocco per spostarlo orizzontalmente mantenendone la
  durata: si adattano solo la fine del precedente e l’inizio del successivo.
  Il movimento non può eliminare un vicino, lasciare buchi o attraversare un
  taglio esplicito. I confini esterni già coincidenti con quelli della porzione
  restano fissi. Le porzioni senza target lasciate da eliminazioni manuali non
  vengono riempite implicitamente da uno spostamento.
  Durante il trascinamento sono mostrati watt, durata e confini.
- **Aggiungi**: trascinare da inizio a fine intervallo. L’altezza del puntatore
  all’inizio imposta il target, poi correggibile dal bordo superiore. Il nuovo
  intervallo sostituisce le porzioni sovrapposte e conserva quelle esterne.
  Non è consentito attraversare un taglio esplicito.
- Clic: selezione di un blocco. **Maiusc + clic**: selezione di una sequenza.
  **Selezione rettangolare**: trascinare sul grafico per selezionare tutti i
  blocchi intersecati dalla porzione temporale, indipendentemente dalla potenza.
  I comandi della selezione permettono di unire o eliminare intervalli;
  **Valori precisi** apre solo i tre campi del singolo blocco selezionato.
  Non c’è una tabella completa da compilare.
- **Dividi rettangolo**: cliccare dentro un intervallo per dividerlo.
  **Identifica ripetute** conserva il numero dei blocchi selezionati e applica
  durata ON/OFF e potenza ON/OFF, con `P_ON > P_OFF >= 0`. Il primo blocco è ON
  se la sua potenza attuale è maggiore o uguale a quella del secondo, altrimenti
  è OFF; la fase riconosciuta viene mostrata prima dell’applicazione. I blocchi
  successivi alternano le due fasi. L’inizio resta fisso e l’inizio del vicino
  successivo viene adattato alla nuova fine. L’operazione viene rifiutata se
  cancella il vicino, attraversa/sposta un taglio o lascia un buco a fine porzione.
  Nessun vincolo permanente: tutti i blocchi restano modificabili e unibili.
- **Annulla ultima modifica** ripristina anche inserimenti, eliminazioni e tagli
  (fino a 50 modifiche). Le operazioni grafiche usano i dati già caricati:
  non richiedono una nuova proposta o un nuovo trasferimento del segnale.

### Tagli e salvataggio

**Taglia** seguito da un clic produce due segmenti distinti nella pre-esportazione.
Se il taglio cade dentro un rettangolo, lo divide anche nell’editor: le due
porzioni hanno un confine fisso e indipendente. Unioni e identificazione delle
ripetute non possono attraversarlo. Rimuovere il taglio riabilita il confine.
Due tagli permettono di isolare un artefatto; **Rimuovi** nella pre-esportazione
esclude la porzione. **Aggiorna pre-esportazione** sostituisce le voci della stessa
sorgente con la bozza corrente e tutti i suoi tagli: eventuali esclusioni dalla
coda vanno riconfermate. Modifiche successive rendono obsolete le voci in coda e
impediscono l’export finché non vengono aggiornate o rimosse.

La coda distingue **Estrazione dataset** e **Ricostruzione allenamenti**, oltre
allo stato In coda / Esportato. L’export misto produce un unico ZIP scaricabile,
anche archiviato nella destinazione `HR_POWER_EXPORTS`, se configurata.
Il download è il salvataggio persistente: ricaricare la pagina del browser elimina
la coda e le bozze del frontend; riavviare il servizio elimina anche le copie
backend. Cambiare pagina, attività o caricare un nuovo ZIP/FIT nelle pagine di
Ricostruzione ed Elaborazione conserva il lavoro della sessione.

La pre-esportazione può contenere ricostruzioni di caricamenti diversi. Ogni voce
mantiene l’identificativo della propria copia: nomi CSV uguali non si sovrascrivono
e una modifica rende obsolete solo le voci della stessa copia e sorgente.
L’export raccoglie tutte le copie in un unico ZIP. Per export con più copie,
`source_dataset_id` e `source_csv_file` identificano la sorgente di ogni segmento;
il manifest conserva i manifest e gli SHA-256 dei singoli archivi sorgente.
Lo SHA-256 dell’aggregato identifica i descrittori delle copie, come dichiarato
da `sha256_scope`, non un inesistente ZIP sorgente unico.

Elaborazione non usa la coda di ricostruzione: il suo export riguarda il
caricamento selezionato. Tornando a una copia precedente si può esportare la
sua anteprima senza ricalcolarla, purché i parametri non siano stati cambiati.

Riaprendo una ricostruzione si ripristinano i rettangoli salvati senza ricalcolarli,
anche per gli archivi della precedente euristica SSE/mediana. I vecchi vincoli
ON/OFF non vengono più applicati dall’editor: le geometrie restano identiche ma
liberamente modificabili. Il manifest sorgente preserva i metadati storici;
i nuovi salvataggi dall’editor hanno `constraints: []`.
I vecchi ZIP che contengono solo `first_lap`/`last_lap` non permettono di ricavare
confini interni mancanti: aprire il FIT originale oppure disegnare i blocchi
manualmente. Anche le attività senza lap consentono la costruzione manuale.

### Convenzioni scientifiche e riproducibilità

L’inizializzazione `lap-mean-v1` è una convenzione ingegneristica del progetto:

1. Usa la **media aritmetica non pesata dei campioni originali** del lap, inclusi
   gli zeri. Esclude dal calcolo i valori mancanti, non finiti o negativi;
   riporta conteggi validi/non validi per lap nella risposta e il totale nella
   pagina. Il formato d’importazione rifiuta i valori infiniti. Arrotonda il
   target a 0.1 W. Nessuna interpolazione o ricampionamento.
2. Al caricamento FIT, la correzione `midpoint-gaps-v1` assegna metà di ogni
   buco fra lap alla coda del precedente e metà alla testa del successivo:
   il confine comune è `(fine_precedente + inizio_successivo) / 2`, anche
   frazionario. L’ultimo lap termina alla fine del supporto dell’attività.
   È un’assunzione di partizionamento richiesta per l’editor, non evidenza di
   misurazioni durante eventuali interruzioni. Il primo inizio resta invariato.
   Le medie vengono calcolate sui campioni assegnati ai confini corretti.
   I confini sono semiaperti `[inizio,fine)`: un campione sul confine appartiene
   solo al lap di destra, anche esportando separatamente lap adiacenti.
   Timestamp FIT originali, confini prima della correzione, origine temporale
   e metodo sono preservati in `boundary_adjustment` e nei riferimenti sorgente.
   Per sovrapposizioni FIT resta la convenzione precedente: fine del lap sinistro
   all’inizio del successivo. Gli ZIP con lap non ancora corretti vengono corretti
   all’importazione in Ricostruzione; le ricostruzioni già salvate restano intatte.
3. Il supporto dell’attività termina all’ultimo timestamp più il passo mediano
   dei timestamp validi unici (1 s con un solo campione). Non si creano campioni.
   Un singolo lap selezionato conserva il proprio confine corretto, senza
   ricalcolarlo dal passo del sottoinsieme: `sample_support_end` e `sample_step`
   lo preservano nei trasferimenti, negli ZIP e dopo i tagli.
4. La media mobile centrata `[t−2.5,t+2.5)` resta **solo un riferimento visivo**.
   Il filtro conserva le convenzioni della pagina di elaborazione, incluse
   finestre troncate ai gap superiori a 1.5 volte il passo mediano e propagazione
   dei valori mancanti. Non decide i confini né i target; non c’è più lo slider
   di sensibilità. Un lap può comprendere un gap: il suo target riassume solo
   i campioni effettivamente presenti, mentre il segnale mostra l’interruzione.
   Il target resta un riferimento editoriale anche se il lap contiene un gap;
   il segnale misurato conserva sempre i campioni mancanti e le interruzioni.

Gli export di Estrazione e i trasferimenti diretti salvano `laps` con indice,
confini locali, timestamp FIT originali e flag `partialStart`/`partialEnd`.
I tagli di ricostruzione ritagliano e ribasano i confini, mantenendo le origini e
propagando i flag anche dopo esportazioni successive. Elaborazione conserva
questi metadati. Gli archivi di ricostruzione v2 contengono:

- CSV con timestamp e segnali originali, tempo locale da zero,
  `source_elapsed_seconds` e colonna distinta `power_target_w` (W);
- `intervals.csv` con i rettangoli finali;
- manifest con provenienza, SHA-256 e manifest sorgente, metodo di inizializzazione
  per segmento, blocchi iniziali e finali, confini ed esclusioni. I risultati
  di “Identifica ripetute” sono normali rettangoli, senza vincoli persistenti.

`supportEnd` e `sourceStep` conservano il supporto temporale dopo un taglio,
senza ristimarlo da pochi campioni. Un taglio fra campioni ribasa il tempo al
primo campione conservato, mantenendo nel manifest il taglio richiesto. Un taglio
nelle ripetute conserva i rettangoli ritagliati. La potenza obiettivo resta
mancante dove la potenza originale è mancante/negativa o manca un rettangolo.
Il campo storico `sensitivity` resta leggibile per compatibilità con vecchi
archivi, ma non influenza la nuova inizializzazione.

Nella modellazione `power_w` resta l’ingresso misurato; gli split di validazione
devono raggruppare per attività originale anche dopo tagli ed export misti.

Verifiche: test di medie e confini dei lap, valori mancanti/zeri, gap,
trasferimento diretto e ZIP, tagli e riapertura, ricostruzioni pregresse,
vincoli ON/OFF, inserimento e annullamento, scorrimento/zoom e coda condivisa.
