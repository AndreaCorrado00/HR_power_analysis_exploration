# AR validation viewer

Visualizzatore minimale, in sola lettura, dei 12 workout di validation della
simulazione libera AR. Non esegue fitting e non modifica dati o risultati.

## Avvio dal PC

```powershell
.\webapp\ar_validation_viewer\start.ps1
# Oppure:
.venv/Scripts/python -B webapp/ar_validation_viewer/server.py --port 8767
```

Aprire `http://127.0.0.1:8767`. Il server ascolta su `0.0.0.0` e stampa gli
indirizzi della rete locale; per usarlo solo sul PC, passare
`-BindAddress 127.0.0.1` a `start.ps1`. Porta configurabile con `-Port`.
Non viene configurato inoltro porte Internet o modificato il firewall.
Il servizio non ha autenticazione ed e destinato alla rete locale fidata.
Ctrl+C nel terminale del server lo arresta.

Input predefinito: `reports/power_residual_ar_simulation/`. Per cambiarlo,
usare `-RunDirectory` nello script PowerShell o `--run` nel comando Python.
Il manifest determina l'elenco di validation; il test non e esposto dall'API.

## Uso

- Frecce in alto: un workout alla volta, in ordine del manifest.
- Rotella sui primi due grafici: zoom temporale sincronizzato.
- Trascinamento nel grafico: spostamento temporale sincronizzato.
- Barra inferiore: selezione e spostamento dell'intervallo comune.
- Cursore: tooltip con valori al campione e lettura nella fascia inferiore.
- **Intero workout**: ripristina l'intera durata.

Le serie sono visualizzate senza smoothing o decimazione. Le interruzioni
rimangono separate; i cambi di lap non introducono reset o transitori aggiunti.

## Definizioni scientifiche

Primo pannello: potenza reale, prescritta e prima traiettoria simulata salvata.
Secondo: `e_reale=P_reale-P_prescritta`, `e_sim=P_sim-P_prescritta`.
Terzo: ACF reale e mediana con fascia empirica puntuale P10-P90 delle simulazioni.
Asse indipendente dei ritardi da 1 a 60 secondi (ridotto se i tratti sono brevi);
resta riferito all'intero workout anche durante lo zoom temporale.
Le traiettorie sono rigenerate in memoria con modello training, seed e numero
 di percorsi del manifest; la prima deve coincidere con quella salvata.
Nessun fit aggiuntivo. Cache in memoria per workout fino al riavvio del server.
ACF biased centrata separatamente in ogni tratto e aggregata per energia:
nessuna coppia attraversa gap, pause, cambi di lap o prescrizione. I tratti
con lunghezza <= ritardo sono esclusi; ACF a varianza nulla non definita.
La stessa segmentazione è applicata a reale e simulazioni, senza cambiare
la generazione continua ai cambi di lap. Il tooltip riporta le coppie valide.
La fascia non include incertezza dei parametri, non è una banda simultanea
e non costituisce un test formale. L'ACF normalizzata non valuta l'ampiezza.

I valori `z=(e-mu_AR)/sigma_e_AR` restano nel tooltip e nella lettura inferiore.

`mu_AR` e `sigma_e_AR` sono media e deviazione standard **stazionarie del
residuo** ricavate da `train_model.json`, tramite l'equazione di Lyapunov gia
usata dal simulatore. Non si usa la SD delle innovazioni e non si normalizza
separatamente sul workout di validation. La scala e comune a tutte le sessioni;
media e SD sono visibili sotto i grafici. Nessuna incertezza parametrica aggiunta.

La curva simulata rappresenta una realizzazione casuale del modello, non una
previsione puntuale aggiornata con le misure. Il target e inferito dai dati,
come documentato nel protocollo dell'esperimento.

## Dipendenze e verifiche

Python dell'ambiente esistente con NumPy/pandas; server HTTP della libreria
standard. ECharts 6.1.0 locale in `vendor/`, copiato dalla dipendenza gia
installata dell'app dataset exploration (licenza Apache-2.0 inclusa).
Nessuna build, installazione npm o connessione CDN necessaria.

```powershell
.venv/Scripts/python -B -m pytest tests/test_ar_validation_viewer.py -q
node webapp/ar_validation_viewer/viewer.test.cjs
```

I test Python verificano scala comune dal training, confini dei tratti e
accesso HTTP limitato alla validation e agli asset autorizzati. Il test JS usa
il renderer SVG reale di ECharts per verificare zoom condiviso, ripristino,
serie, valori e navigazione; non sostituisce la prova dei gesti in un browser.
