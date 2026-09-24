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

1. Inserire il percorso di una directory contenente file `.fit`. Sono accettate
   directory e file raggiunti tramite collegamenti simbolici.
2. Indicare, se necessario, la durata massima in ore e caricare il dataset.
3. La griglia separa le attività con lap utilizzabili da **Esclusi
   dall'estrazione**. Ogni esclusione riporta il motivo.
4. Aprire una scheda per usare lo zoom temporale, selezionare un lap e unire
   lap immediatamente contigui.
5. Attivare facoltativamente W/kg, % FCmax o % FC di soglia dichiarando i
   rispettivi parametri.
6. Visualizzare l'anteprima e indicare una destinazione ZIP. Se la destinazione
   non è scrivibile, il browser scarica lo ZIP.

Lo ZIP contiene un CSV per segmento e `manifest.json`. I CSV conservano
timestamp originale, tempo relativo da zero, potenza e frequenza cardiaca
misurate ed eventuali colonne normalizzate. Il manifest dichiara sorgenti,
lap, unità, formule e parametri di normalizzazione.

## Indirizzo verificato

`127.0.0.1:53057`

La porta viene scelta nuovamente a ogni avvio; usare sempre anche l'indirizzo
stampato dal processo corrente.
