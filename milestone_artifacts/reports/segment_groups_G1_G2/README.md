# Raggruppamenti empirici dei segmenti

[Distribuzione delle durate](durate.png) · [Classificazioni e tavola di ciascun segmento](classificazioni.csv)

## Riproduzione e criteri

Eseguire dalla radice: `.venv/Scripts/python scripts/plot_segment_groups.py --input "dataset/dataset_segments_G1_G2.zip" --output "reports/segment_groups_G1_G2"`.
Fonte: `dataset/dataset_segments_G1_G2.zip`, letto senza estrazione o modifica.
Hash e versioni delle librerie sono registrati in `summary.json`.

Durata = ultimo meno primo tempo registrato, inclusi eventuali gap.
Un confine è proposto tra durate consecutive distinte se il vuoto è almeno
30 s e il rapporto tra durata maggiore e minore è almeno 1,2. La soglia è
il punto medio del vuoto. Sono raggruppamenti descrittivi, non cluster
statisticamente validati: le soglie dipendono dal campione e dalla regola.
Eventuali gruppi con pochissimi elementi non dimostrano popolazioni distinte.

Direzione della potenza: differenza tra media dell'ultimo e del primo 20%
del tempo del segmento. Una direzione è netta solo oltre il massimo tra
20 W e il 10% della maggiore delle due medie. HR: differenza tra mediane
delle stesse finestre; variazioni inferiori a 3 bpm non sono direzionali.
Campana: mediane HR in 10 intervalli temporali uguali; massimo nei bin
2–8 e almeno 3 bpm sopra entrambe le mediane iniziale/finale.
UtD: potenza in calo e HR in calo o a campana. DtU: potenza in aumento e
HR in aumento senza campana. Tutti gli altri casi sono ambigui.
Le soglie sono euristiche esplorative, non stimate o validate fisiologicamente.
Il confronto tra estremi non identifica ogni transizione interna: segmenti
con più inversioni o risposte ritardate richiedono revisione visiva.

Curve originali senza smoothing, normalizzazione o interpolazione.
Le mediane in bin servono esclusivamente alla classificazione.
I gap superiori a 1,5 volte il passo mediano interrompono le linee.
Asse temporale comune nel gruppo; HR comune 80–200 bpm (range osservato
87–192); potenza su scala locale, esplicitata nei singoli pannelli.
Le colonne vuote indicano assenza di segmenti di quella classe.
Nelle tavole degli ambigui entrambe le colonne contengono casi da rivedere.
Ogni segmento compare esattamente una volta nelle tavole.

## Risultati

Totale: 215. UtD: 123; DtU: 2; ambigui: 90.

Soglie candidate (s): 144.5.

- [G1_UtD_DtU_01.png](G1_UtD_DtU_01.png)
- [G1_UtD_DtU_02.png](G1_UtD_DtU_02.png)
- [G1_UtD_DtU_03.png](G1_UtD_DtU_03.png)
- [G1_UtD_DtU_04.png](G1_UtD_DtU_04.png)
- [G1_UtD_DtU_05.png](G1_UtD_DtU_05.png)
- [G1_UtD_DtU_06.png](G1_UtD_DtU_06.png)
- [G1_UtD_DtU_07.png](G1_UtD_DtU_07.png)
- [G1_UtD_DtU_08.png](G1_UtD_DtU_08.png)
- [G1_UtD_DtU_09.png](G1_UtD_DtU_09.png)
- [G1_UtD_DtU_10.png](G1_UtD_DtU_10.png)
- [G1_UtD_DtU_11.png](G1_UtD_DtU_11.png)
- [G1_UtD_DtU_12.png](G1_UtD_DtU_12.png)
- [G1_ambigui_01.png](G1_ambigui_01.png)
- [G1_ambigui_02.png](G1_ambigui_02.png)
- [G1_ambigui_03.png](G1_ambigui_03.png)
- [G1_ambigui_04.png](G1_ambigui_04.png)
- [G1_ambigui_05.png](G1_ambigui_05.png)
- [G1_ambigui_06.png](G1_ambigui_06.png)
- [G1_ambigui_07.png](G1_ambigui_07.png)
- [G1_ambigui_08.png](G1_ambigui_08.png)
- [G1_ambigui_09.png](G1_ambigui_09.png)
- [G2_UtD_DtU_01.png](G2_UtD_DtU_01.png)
- [G2_UtD_DtU_02.png](G2_UtD_DtU_02.png)
- [G2_UtD_DtU_03.png](G2_UtD_DtU_03.png)
- [G2_UtD_DtU_04.png](G2_UtD_DtU_04.png)
- [G2_UtD_DtU_05.png](G2_UtD_DtU_05.png)
- [G2_UtD_DtU_06.png](G2_UtD_DtU_06.png)
- [G2_UtD_DtU_07.png](G2_UtD_DtU_07.png)
- [G2_UtD_DtU_08.png](G2_UtD_DtU_08.png)
- [G2_UtD_DtU_09.png](G2_UtD_DtU_09.png)
- [G2_UtD_DtU_10.png](G2_UtD_DtU_10.png)
- [G2_UtD_DtU_11.png](G2_UtD_DtU_11.png)
- [G2_UtD_DtU_12.png](G2_UtD_DtU_12.png)
- [G2_UtD_DtU_13.png](G2_UtD_DtU_13.png)
- [G2_UtD_DtU_14.png](G2_UtD_DtU_14.png)
- [G2_ambigui_01.png](G2_ambigui_01.png)
