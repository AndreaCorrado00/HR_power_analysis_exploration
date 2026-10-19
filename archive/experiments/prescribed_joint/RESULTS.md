# Primo risultato — 17 ottobre 2026

Esperimento completato sui 60 workout, split cronologico comune 42/9/9.
Training: 18 maggio 2025–24 giugno 2026; validation: 8 luglio–27 agosto 2026;
test: 29 agosto–19 settembre 2026. Attività interamente separate tra gli split.
È una valutazione retrospettiva, con target ricostruiti da dati osservati.

## Modelli ristimati

- Potenza: ordine **2 + AR(2)**. L'ordine 4 ha RMSE validation leggermente
  inferiore nella selezione (69.053 vs 69.142 W), ma la differenza di 0.089 W
  rientra in un SE appaiato (0.096 W): si seleziona l'ordine più piccolo.
- HR: tutti i **182** fit train completati; **118** vettori superano lo screening
  per REML. K=0.26347 bpm/W, L=7.43384 s, tau=48.29319 s. SD tra tratti:
  0.07463 bpm/W, 2.71505 s, 22.04742 s. Sono parametri matematici, non biomarcatori.
- A=86.99925 bpm; HR iniziale train=121.72527 bpm. Nessuna HR heldout
  condiziona le predizioni. Nessun parametro storico viene riutilizzato.
- 1.000 traiettorie Monte Carlo per tratto; 37/37 tratti validation e 24/24
  tratti test previsti, senza fallimenti, con tutte le 18 attività rappresentate.

## Errori fuori training

RMSE medi per workout, su interi tratti HR >=300 s; unità bpm.

| Predizione HR | Validation | Test descrittivo |
|---|---:|---:|
| Catena prescrizione → potenza → HR | 12.23 | 11.10 |
| HR da potenza reale | 10.38 | 8.96 |
| HR direttamente dalla prescrizione | 12.27 | 10.89 |
| Baseline statica da potenza predetta | 17.68 | 16.90 |
| Baseline statica da potenza reale | 18.20 | 17.71 |

MAE della catena: 10.07 / 8.62 bpm; bias osservato-predetto: +0.93 / -4.44 bpm.
Il bias test indica una sovrastima media. Le metriche da 180 s e nei primi
180 s sono disponibili nella pagina e nei CSV: nessuna calibrazione nei primi
tre minuti, che sono esclusi soltanto nella metrica di coda.

RMSE potenza su tutti i tratti validi: **69.08 / 77.19 W**, rispetto a
**72.15 / 80.46 W** della sola prescrizione. Il supporto potenza include anche
tratti brevi: per confrontare la catena usare le righe `power_common`.

## Cosa emerge e cosa resta aperto

Il P1D supera la baseline statica su questi dati. La potenza reale permette
una predizione HR migliore della catena basata sulla prescrizione. Non emerge
un beneficio sostanziale dello stadio power_response sulla previsione media HR
rispetto all'ingresso prescritto diretto: differenze di circa 0.04 bpm sulla
validation e 0.21 bpm sul test, con segno diverso. Non sono confronti di
significatività; il centro della catena è una media Monte Carlo, mentre il
confronto diretto usa i parametri medi.

Le fasce HR hanno copertura media **96.4% / 97.3%**, ma larghezza media
**64.04 / 64.60 bpm**. La copertura elevata non dimostra precisione utile.
La variabilità rimane ampia e parziale: nessun rumore residuo HR o incertezza
delle medie/A/HR0/coefficienti potenza. L'errore standard Monte Carlo massimo
della media HR in validation è 0.91 bpm; differenze minime non vanno enfatizzate.

Questo esperimento non dimostra ripetibilità test-retest dei parametri o
trasferibilità a prescrizioni originali indipendenti. Non si aggiungono modelli,
covariate o correzioni per migliorare il test. Prossimi passi concordati:
riorganizzazione della repository e verifica prospettica sul campo.

## Verifica

65 test numerici/di regressione superati (un warning di deprecazione esterno).
131 controlli della pagina offline in Edge: entrambi gli split, tutti i workout,
selezione tratti, finestre metriche e zoom. Screenshot ispezionato visivamente.
Revisione indipendente del codice senza rilievi bloccanti.

Protocollo: [PROTOCOL.md](PROTOCOL.md). Pagina: [index.html](index.html).
Dettagli locali, serie complete e hash: `results/`.
