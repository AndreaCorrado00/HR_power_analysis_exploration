"""PDF composition for the approved, immutable 00e47e9c experiment analysis."""
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import json

import numpy as np
import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle,PageBreak,KeepTogether
from reportlab.pdfgen.canvas import Canvas

INK=colors.HexColor('#243a43');TEAL=colors.HexColor('#257969');GRAY=colors.HexColor('#617078');LIGHT=colors.HexColor('#edf3f1')
WIDTH=178*mm


def num(value,digits=2):
    if value is None or not np.isfinite(value):return 'n.d.'
    if abs(value)>=10000:return f'{value:.2e}'.replace('.',',')
    return f'{value:.{digits}f}'.replace('.',',')


def setup_fonts():
    root=Path(matplotlib.get_data_path())/'fonts'/'ttf'
    for name,file in [('Report','DejaVuSans.ttf'),('Report-Bold','DejaVuSans-Bold.ttf'),('Report-Italic','DejaVuSans-Oblique.ttf'),('ReportMono','DejaVuSansMono.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(root/file)))
    pdfmetrics.registerFontFamily('Report',normal='Report',bold='Report-Bold',italic='Report-Italic',boldItalic='Report-Bold')


class NumberedCanvas(Canvas):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.states=[]
    def showPage(self):
        self.states.append(dict(self.__dict__));self._startPage()
    def save(self):
        total=len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setStrokeColor(colors.HexColor('#d5dfdb'));self.setLineWidth(.5)
            self.line(16*mm,16*mm,A4[0]-16*mm,16*mm)
            self.setFont('Report',7);self.setFillColor(GRAY)
            self.drawString(16*mm,11*mm,'HR-POWER | RUN 00e47e9c | Analisi train-only')
            self.drawRightString(A4[0]-16*mm,11*mm,f'{self._pageNumber} / {total}')
            Canvas.showPage(self)
        Canvas.save(self)


def build_pdf(out,m,series,rows,starts,acts,s,images):
    setup_fonts()
    styles={
        'body':ParagraphStyle('body',fontName='Report',fontSize=9.1,leading=13,spaceAfter=8,textColor=INK),
        'small':ParagraphStyle('small',fontName='Report',fontSize=8,leading=11.4,spaceAfter=6,textColor=GRAY),
        'caption':ParagraphStyle('caption',fontName='Report',fontSize=7.8,leading=10.8,spaceBefore=5,spaceAfter=12,textColor=GRAY),
        'h1':ParagraphStyle('h1',fontName='Report-Bold',fontSize=18,leading=23,spaceAfter=13,textColor=INK),
        'h2':ParagraphStyle('h2',fontName='Report-Bold',fontSize=11,leading=15,spaceBefore=10,spaceAfter=6,textColor=TEAL),
        'cover':ParagraphStyle('cover',fontName='Report-Bold',fontSize=25,leading=31,spaceAfter=18,textColor=INK),
        'kicker':ParagraphStyle('kicker',fontName='Report-Bold',fontSize=8,leading=11,spaceAfter=12,textColor=TEAL),
        'formula':ParagraphStyle('formula',fontName='Report',fontSize=10,leading=16,spaceBefore=7,spaceAfter=10,textColor=INK,backColor=LIGHT,borderPadding=9),
        'cell':ParagraphStyle('cell',fontName='Report',fontSize=7.8,leading=10.5,textColor=INK),
    }
    story=[];p=lambda text,style='body':Paragraph(text,styles[style]);stats=s['aggregate_stats'];by={r['segment']:r for r in rows}
    def text(t,kind='body'):story.append(p(t,kind))
    def title(t):text(t,'h1')
    def head(t):text(t,'h2')
    def page(t):story.append(PageBreak());title(t)
    def table(headers,data,widths=None):
        cells=[[p(escape(str(v)),'cell') for v in headers]]+[[p(escape(str(v)),'cell') for v in row] for row in data]
        t=Table(cells,colWidths=widths or [WIDTH/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e0e7e3'))]))
        story.extend([t,Spacer(1,9)])
    def image(name,caption,width=WIDTH):
        obj=Image(str(out/'figures'/name));obj.drawHeight=obj.imageHeight*width/obj.imageWidth;obj.drawWidth=width
        story.extend([obj,p(caption,'caption')])
    def metric_table(keys):
        table(['Grandezza','Media ± SD','Mediana [Q1; Q3]','Minimo; massimo'],[
            [label,f"{num(stats[k]['mean'],d)} ± {num(stats[k]['sd'],d)}",f"{num(stats[k]['median'],d)} [{num(stats[k]['q1'],d)}; {num(stats[k]['q3'],d)}]",f"{num(stats[k]['minimum'],d)}; {num(stats[k]['maximum'],d)}"] for k,label,d in keys], [100,125,160,WIDTH-385])
    def count(test):return sum(test(r) for r in rows)
    def refs(ids):return ', '.join(ids)

    text('REPORT TECNICO / 26 SETTEMBRE 2026','kicker')
    text('Identificazione P1D<br/>della risposta HR-Power','cover')
    text('Analisi dell’esperimento <b>Up_to_Down_under60s</b><br/>Run <font name="ReportMono">00e47e9c0e2b41b0911e978afd611905</font>','body')
    text('34 segmenti train · 5 attività · segnali originali · nessun refitting','kicker')
    head('Esito principale')
    text('Il P1D ricostruisce bene la forma di alcuni segmenti, ma questa run <b>non fornisce ancora una caratterizzazione stabile dei tre parametri</b>. Residui strutturati, soluzioni vincolate e inizializzazioni senza informazione dinamica richiedono una diagnosi distinta dal solo errore medio.')
    table(['Indicatore','Esito e significato'],[
        ['RMSE mediano / medio',f"{num(stats['RMSE']['median'])} / {num(stats['RMSE']['mean'])} bpm fra segmenti"],
        ['RMSE aggregato sui campioni',f"{num(s['pooled_RMSE'])} bpm: gli errori elevati pesano maggiormente"],
        ['Forma attenuata',f"{s['counts']['attenuated']}/34 fit con range previsto ≤35% del range HR osservato"],
        ['Residui persistenti',f"34/34 con ACF1 >0,5; mediana {num(stats['ACF1']['median'],3)}"],
        ['Multistart bloccato all’origine','169/272 start con L iniziale ≥ durata; tutti dichiarati convergenti senza muoversi'],
        ['Precisione / vincoli','6 stime K al massimo; CI95 di tau negativi inferiormente in 15/34 casi'],
    ],[163,WIDTH-163])
    head('Come leggere il documento')
    text('Le sezioni 1-14 ricostruiscono protocollo, statistiche, problemi numerici e casi illustrativi. La sezione 15 propone verifiche successive senza eseguirle. Seguono metodi, fonti, inventario e <b>34 schede individuali</b>, ciascuna con grafici e incertezza dei parametri.')
    text('Tutti gli errori sono <b>in-sample</b>. Validation e test rimangono inutilizzati. La selezione dei segmenti dipende anche dalla HR osservata; i risultati non vanno estesi a workout futuri o interpretati come biomarcatori fisiologici.','small')

    page('1. Provenienza, campione e integrità')
    text('La run del 26/09/2026, ore 06:00:32 UTC, usa il sottoinsieme G1 + UtD dell’archivio <b>dataset_segments_G1_G2.zip</b>. Il manifest sorgente è formato v1: le colonne usate sono <b>power_w</b> e <b>heart_rate_bpm</b>, senza medie mobili o normalizzazioni attive. Il nome assegnato al dataset non è una regola di selezione.')
    image('01_dataset.png','Figura 1. Campione effettivo. Colori A1-A5 mantenuti nelle figure successive: blu, marrone, verde, viola, ocra. Non vengono lette le serie validation/test per calcolare risultati del modello.')
    text(f"Il dataset contiene 56 segmenti e 7 attività. Lo split per attività assegna 5/1/1 attività a train/validation/test, corrispondenti a <b>34/19/3 segmenti</b> (60,7%/33,9%/5,4%), pur richiedendo 70/10/20%. È una conseguenza delle diverse numerosità dei gruppi, non uno split casuale dei campioni.")
    text(f"Nel train le durate sono {num(stats['duration_s']['minimum'],0)}-{num(stats['duration_s']['maximum'],0)} s: <b>{s['durations_above60']}/34 superano 60 s</b>. La metadata di selezione originale usa per G1 il confine 144,5 s; il filtro salvato non impone &lt;60 s. Non vengono esclusi o rinominati segmenti retroattivamente.")
    text(f"Sono presenti {s['n_records']} record e {s['unique_activity_timestamps']} coppie uniche attività-timestamp: {s['repeated_records']} occorrenze ripetute fra segmenti train. Lo split per attività evita contaminazione tra insiemi, ma non rende indipendenti i segmenti della stessa sessione.")
    text(f"Verificati hash del manifest, di 34 risultati, di 34 CSV e dello snapshot del simulatore. Tutte le serie coincidono con i CSV. Una ricostruzione indipendente per sovrapposizione di gradini riproduce le previsioni entro {s['checks']['max_prediction_reconstruction_error']:.2e} bpm e le SSE dei 272 start entro {s['checks']['max_start_sse_error']:.2e} bpm².",'small')

    page('2. Modello e criteri di analisi')
    text('Il modello analizzato è quello concordato nel protocollo utente; non viene presentato come replica di uno specifico articolo. Ogni segmento ha tre parametri propri, non esiste un unico parametro dell’atleta stimato congiuntamente.')
    text('τ dx/dt + x = K [P(t − L) − P₀]<br/>HR̂(t) = HR₀ + x(t)<br/>P₀ = P(0), HR₀ = HR(0), x(0) = 0; P(t &lt; 0) = P₀','formula')
    text('Il primo campione è assunto in equilibrio. La potenza è ricostruita come costante a tratti (ZOH), con integrazione esatta e ritardo continuo. Le curve osservate non sono interpolate né smussate. La simulazione mantiene la potenza anche nei gap; nei grafici le linee sono invece interrotte per rendere visibile l’assenza di campioni.')
    table(['Parametro','Unità','Bounds numerici'],[['K','bpm/W','[0,000001; 5]'],['L','s','[0; 120]'],['τ','s','[0,01; 1800]']],[100,100,WIDTH-200])
    text('Least squares TRF, loss lineare/SSE, Jacobiano numerico a tre punti, scala Jacobiano, ftol/xtol/gtol = 10⁻⁸; massimo 500 valutazioni per start, 8 start, seed fit 42. Il vincitore è la SSE più bassa, anche se l’ottimizzatore non dichiara successo. [R1]')
    head('Tre livelli, tenuti separati')
    text('<b>Errore:</b> RMSE, MAE, bias e dispersione dei residui.<br/><b>Forma:</b> escursione, transizioni, plateau, risposta quasi costante e residuo che conserva il trend HR.<br/><b>Identificabilità:</b> bounds, CI/RSE, correlazioni locali dei parametri e soluzioni multistart.')
    text('I criteri morfologici sono euristiche post-hoc, non soglie cliniche: range previsto/osservato ≤0,35 con range osservato ≥3 bpm; plateau previsto con |ΔHR̂/Δt| ≤0,05 bpm/s per almeno 5 s; discordanza se la HR osservata varia di almeno 3 bpm nello stesso intervallo. Le soglie sono registrate in summary.json e discusse in sezione 16.')

    page('3. Bontà del fit: oltre la media')
    image('05_fit_quality.png','Figura 2. Barre: RMSE P1D. Tratti neri: RMSE della previsione costante HR(0), senza stimare ulteriori parametri. A destra, un errore in bpm va valutato rispetto alla dinamica da ricostruire.')
    metric_table([('RMSE','RMSE [bpm]',2),('MAE','MAE [bpm]',2),('R2_centered','R² centrato',2)])
    text(f"Il RMSE aggregato √(ΣSSE/ΣN) è <b>{num(s['pooled_RMSE'])} bpm</b>, diverso dalla media dei RMSE ({num(stats['RMSE']['mean'])}). S08 e S12 producono da soli il <b>{num(100*sum(by[k]['SSE'] for k in ('S08','S12'))/sum(r['SSE'] for r in rows),1)}%</b> della SSE totale. Non vengono rimossi come outlier.")
    text(f"Tutti i fit migliorano la costante HR(0), ma {s['negative_R2']}/34 hanno R² centrato negativo: peggio della media HR calcolata sul segmento. Quest’ultimo è un riferimento descrittivo che usa tutta l’uscita, non un predittore prospettico. Nove fit hanno R² &gt;0,8; questo non rende automaticamente affidabili i loro parametri.")

    page('4. Distribuzione dei parametri')
    image('02_parameters.png','Figura 3. Boxplot e singoli segmenti, colorati per attività. Cerchi rossi: bounds attivi/vicini secondo il criterio della run. K e τ in scala logaritmica; le barre del box non sono intervalli di confidenza.')
    metric_table([('K','K [bpm/W]',4),('L','L [s]',2),('tau','τ [s]',2),('K_over_tau','K/τ [bpm/(W·s)]',5)])
    text('La distribuzione è fortemente asimmetrica. La media di K (1,0123 bpm/W) è quasi venti volte la mediana (0,0511), soprattutto per sei soluzioni sul tetto K=5. La media di τ è 129,55 s contro una mediana di 15,05 s. Una sintesi con la sola media descriverebbe male il segmento tipico.')
    text('Queste differenze combinano workout diversi, escursioni diverse e diversa informazione dinamica disponibile. Non sono evidenza di cambiamento di forma o fatica. Anche K/τ è soltanto una combinazione matematica utile alla diagnosi dei transitori brevi, non un parametro fisiologico validato.')
    text('I bounds sono numerici. Una soluzione K=5 significa che l’ottimo vincolato tocca il dominio scelto: non è una misura di guadagno fisiologicamente elevato. Aumentare il bound senza studiare la valle della SSE potrebbe soltanto spostare la stima lungo una direzione poco identificata.')

    page('5. Effetto dell’attività e dipendenza del campione')
    image('06_activity.png','Figura 4. Stime per attività; il tratto orizzontale indica la mediana. Numerosità 7, 9, 2, 15, 1: i segmenti non forniscono repliche bilanciate fra sessioni.')
    table(['Attività / FIT','n','RMSE pooled','Mediana K','Mediana L','Mediana τ'],[[a['activity']+' / '+a['fit_source'].replace('.fit',''),a['n_segments'],num(a['pooled_RMSE']),num(a['median_K'],4),num(a['median_L']),num(a['median_tau'])] for a in acts],[153,25,80,80,80,WIDTH-418])
    text(f"L’attività A4 fornisce 15/34 segmenti (44,1%). Il RMSE pooled per attività varia da {num(min(a['pooled_RMSE'] for a in acts))} a {num(max(a['pooled_RMSE'] for a in acts))} bpm. Dando lo stesso peso alle cinque attività, la media dei loro RMSE pooled è {num(s['equal_activity_mean_RMSE'])} bpm.")
    text('Sensibilità leave-one-activity-out <b>descrittiva, senza rifitting</b>: eliminando a turno una sessione, il RMSE medio per segmento varia da 3,34 a 5,36 bpm; la mediana K da 0,0399 a 0,2584 bpm/W e la mediana τ da 11,67 a 90,76 s. L’aggregazione dipende sensibilmente dalla composizione del campione.')
    text('Con sole cinque attività train, numerosità sbilanciate e selezione basata anche sulla forma HR, non vengono prodotti p-value di confronto tra sessioni né CI di popolazione trattando i 34 segmenti come indipendenti. La ripetibilità test-retest resta non dimostrata.')

    page('6. SE, CI95 e precisione locale')
    image('03_uncertainty.png','Figura 5. CI95 locali della run, senza clipping ai bounds. La scala symlog mantiene visibili zero, intervalli negativi e code molto ampie; non rende questi intervalli fisiologicamente ammissibili.')
    table(['Parametro','RSE mediano','RSE >50%','CI con estremo <0','Al bound'],[
        ['K',num(stats['K_RSE_pct']['median'])+'%', '9/34','9/34','6/34'],
        ['L',num(stats['L_RSE_pct']['median'])+'%', '3/33','4/34','1/34'],
        ['τ',num(stats['tau_RSE_pct']['median'])+'%', '15/34','15/34','0/34'],
    ],[80,115,95,130,WIDTH-420])
    text('Cov(θ̂) ≈ [SSE/(N−3)] (JᵀJ)⁻¹<br/>SEⱼ = √Covⱼⱼ; CI95ⱼ = θ̂ⱼ ± 1,96 SEⱼ','formula')
    text('Il calcolo è coerente con quello salvato. Tutti i Jacobiani hanno rango numerico 3, ma ciò non dimostra buona identificabilità pratica. In S02 il RSE di K supera il 52.000%; in S25 è oltre il 4.300%. L’RSE di L in S09 è non definito perché L≈0. Il condizionamento non scalato dipende anche dalle unità dei parametri.')
    text('L’approssimazione è locale e usa una linearizzazione del modello: curvature marcate, bounds attivi e residui dipendenti ne limitano l’interpretazione. Gli intervalli negativi non sono evidenza di parametri negativi; rendono visibile l’inadeguatezza della sintesi simmetrica in quei casi. Non viene applicata una correzione arbitraria dei CI. [R2]')

    page('7. Perché K e τ possono essere confondibili')
    image('04_identifiability.png','Figura 6. Relazione delle stime, correlazione locale da covarianza e RSE. L’orizzonte (T−L) è soltanto un limite superiore della finestra informativa: la transizione effettiva può iniziare più tardi.')
    text('Per un gradino ΔP e u=t−t<sub>gradino</sub>−L &gt;0:<br/>x(t)=K ΔP [1−exp(−u/τ)] ≈ (K/τ) ΔP u, se u/τ ≪1.','formula')
    text('In questa approssimazione la traiettoria dipende soprattutto da K/τ. Aumentare K e τ insieme conserva quasi la stessa pendenza; le colonne del Jacobiano rispetto a K e τ diventano quasi collineari. Il guadagno a regime richiede informazione sul plateau finale, spesso assente in questi segmenti.')
    text(f"In <b>{count(lambda r:r['effective_horizon_over_tau']<.2)}/34</b> casi (T−L)/τ &lt;0,2; in <b>{count(lambda r:r['cov_corr_K_tau']>.99)}/34</b> la correlazione locale K-τ supera 0,99. La mediana è {num(stats['cov_corr_K_tau']['median'],3)}. Sono risultati compatibili con confondibilità pratica, pur con rango numerico formalmente pieno.")
    text('L può a sua volta compensare errori nell’allineamento o nell’inizializzazione. Un ritardo stimato non va automaticamente interpretato come latenza fisiologica. La derivazione è una diagnosi matematica del P1D, non la proposta di un nuovo modello.')

    page('8. Multistart: otto avvii non sono otto prove utili')
    image('10_multistart.png','Figura 7. Ogni riga è un segmento e ogni colonna uno start. La × bianca indica L iniziale ≥T. La scala colore è il rapporto fra SSE finale e migliore SSE del segmento. A destra, start con L finale &lt;T e quelli concordi nei parametri col vincitore.')
    table(['Diagnostica','Esito'],[['Start complessivi','272 (34 × 8)'],['L iniziale ≥T, invariati e “success”','169 / 272 (62,1%)'],['L finale ≥T','178 / 272 (65,4%)'],['L finale <T per segmento','Da 2 a 5, anziché 8'],['Accordo fra tutti gli start con L finale <T','18 / 34 segmenti']],[320,WIDTH-320])
    text('Il warning di disaccordo multistart su 34/34 è dunque in parte strutturale: include avvii incapaci di vedere la dinamica. Escluderli dalla diagnosi lascia comunque 16/34 segmenti senza accordo fra tutte le soluzioni con L finale &lt;T. Tale esclusione serve solo a leggere i risultati salvati: non cambia il vincitore e non dimostra un minimo globale.')
    text('Le cinque segnalazioni di SSE quasi equivalenti e parametri diversi riguardano S13, S21, S25, S27 e S28. La soglia salvata è entro max(10⁻⁸, 1% della SSE migliore), con accordo parametrico rtol=5% e atol=0,01. S27 è inoltre il solo vincitore con status 0, per esaurimento delle valutazioni.')

    page('9. La regione piatta del ritardo: dimostrazione')
    image('11_delay_objective.png','Figura 8. Sezioni della SSE a K e τ fissati ai valori migliori, non profili ottimizzati. Oltre la durata T, la previsione è HR(0) e la SSE è esattamente costante. I grafici non dimostrano globalità dell’ottimo.')
    text('Se L≥T, allora t−L≤0 per ogni osservazione e P(t−L)−P₀=0.<br/>Con x(0)=0 segue x(t)=0, HR̂(t)=HR₀.<br/>SSE(K,L,τ)=Σ[HR(t)−HR₀]²; J=0 nella regione interna L&gt;T.','formula')
    text('Un ottimizzatore basato sul gradiente può quindi terminare correttamente secondo la propria tolleranza, pur restituendo un fit privo di risposta dinamica. Questa è <b>convergenza numerica, non identificazione</b>. Nei 169 avvii con L iniziale ≥T, i parametri finali sono esattamente uguali agli iniziali; le previsioni sono costanti.')
    text('Il generatore riusa gli stessi otto punti iniziali in ogni segmento, perché usa lo stesso seed. Dopo il primo punto L=5 s, gli altri ritardi sono circa 16,17; 90,89; 46,05; 94,86; 65,90; 74,22; 110,84 s. Con segmenti da 44 a 90 s una parte maggioritaria della ricerca parte senza sensibilità.')
    text('La diagnosi giustifica, per una futura run da concordare, inizializzazioni compatibili con la durata effettiva e una segnalazione distinta per le soluzioni senza eccitazione. Non autorizza a concludere che la potenza sia priva d’informazione o che serva un modello più complesso.')

    page('10. Valli della funzione obiettivo')
    image('12_objective_ridges.png','Figura 9. Sezioni K-τ della SSE normalizzata, con L fissato. Croce: stima salvata; tratteggio: rapporto K/τ costante. Contorni 1,01, 1,1 e 2 volte la SSE migliore. Il dominio visualizzato resta entro i bounds della run.')
    text('Le valli allungate mostrano come parametri diversi possano mantenere previsioni simili. Non sono regioni di confidenza: non sono stati riottimizzati gli altri parametri né applicata una soglia probabilistica. Servono a leggere la geometria della funzione obiettivo.')
    head('S01: guadagno vincolato')
    text(f"S01 raggiunge K=5 bpm/W e τ={num(by['S01']['tau'])} s su T=60 s. Il rapporto (T−L)/τ è {num(by['S01']['effective_horizon_over_tau'],3)}. La curva descrive parte della risposta, ma l’osservazione non copre un regime stazionario sufficiente a separare robustamente guadagno e costante di tempo.")
    head('S34: fit buono, interpretazione ancora condizionata')
    text(f"S34 raggiunge R²={num(by['S34']['R2_centered'],3)} su un’escursione di 72 bpm, con K={num(by['S34']['K'],3)} e τ={num(by['S34']['tau'])} s. Il maggiore contenuto dinamico restringe la valle rispetto ai casi estremi, ma τ resta molto più lungo del segmento e le assunzioni su riferimenti iniziali e residui rimangono determinanti.")
    text('La buona qualità di una traiettoria e la buona precisione di ciascun parametro sono domande diverse. La prima non va usata come prova automatica della seconda.')

    page('11. Residui: dinamica sistematica residua')
    image('07_residuals.png','Figura 10. ACF per segmento, coppie di residui successivi centrate entro segmento e bias agli estremi. Non vengono concatenate le sessioni per calcolare ACF. Per S06 il lag è in campioni, non in secondi costanti.')
    metric_table([('bias','Bias [bpm]',2),('ACF1','ACF lag 1',3),('ACF5','ACF lag 5',3),('ACF10','ACF lag 10',3)])
    text(f"ACF1 è positiva in tutti i segmenti (minimo {num(stats['ACF1']['minimum'],3)}); a lag 5 resta mediamente {num(stats['ACF5']['mean'],3)}. La media vicina a zero al lag 10 non dimostra rumore bianco: aggrega curve che possono cambiare segno e avere forme diverse. Le sequenze residue e i lag plot mostrano struttura temporale. [R3, R4]")
    text(f"Il bias pooled è solo {num(s['pooled_bias'],3)} bpm, ma nasconde compensazioni: 26 segmenti hanno bias negativo e 8 positivo. I bias individuali vanno da {num(stats['bias']['minimum'])} a {num(stats['bias']['maximum'])} bpm. Non è corretto descrivere la run come uniformemente priva di bias.")

    page('12. Forma, attenuazione e plateau')
    image('08_shape.png','Figura 11. Residui lungo il tempo relativo (nessuna media/smoothing) e relazione fra attenuazione della risposta e residuo che conserva la forma della HR. Linee tratteggiate: criteri esplorativi ratio≤0,35 e correlazione≥0,90.')
    text('Nessuno dei 34 vincitori ha HR prevista globalmente costante entro 1 bpm; nessuna HR osservata è globalmente piatta entro 1 bpm. Il problema non deve quindi essere raccontato come “tutti fit costanti”. Si osservano invece <b>sette risposte fortemente attenuate</b>, che spiegano poco della dinamica pur riducendo la SSE rispetto a HR(0).')
    table(['Segmento','RMSE [bpm]','Ratio ampiezza','corr(e,HR)','R²'],[[r['segment'],num(r['RMSE']),num(r['amplitude_ratio'],3),num(r['corr_residual_HR'],3),num(r['R2_centered'],3)] for r in rows if r['attenuated']],[85,105,110,105,WIDTH-405])
    text('Se HR̂(t)≈c, allora e(t)=HR(t)−c: il residuo riproduce quasi interamente il trend della HR. La correlazione elevata tra e e HR è qui una conseguenza algebrica della risposta attenuata; non è una prova indipendente di un meccanismo fisiologico.')

    page('13. Plateau iniziali e finali: distinguere le cause')
    image('09_plateaus.png','Figura 12. Plateau iniziale previsto definito dalla pendenza ≤0,05 bpm/s; la × segnala almeno 3 bpm di variazione osservata nello stesso intervallo. A destra, plateau finale osservato entro un range di 1 bpm: le due definizioni non sono intercambiabili.')
    text('Il plateau iniziale è in parte imposto dal modello: prima che l’ingresso ritardato cambi rispetto a P₀, HR̂ rimane HR₀. Il ritardo fisso e il mantenimento del primo valore di potenza possono prolungarlo; non è di per sé un errore software.')
    text(f"Con il criterio dichiarato, <b>{s['counts']['initial_plateau_mismatch']}/34</b> segmenti mostrano una variazione osservata di almeno 3 bpm durante un plateau previsto di almeno 5 s. È una discrepanza di forma da esaminare, non un test statistico di rifiuto. Può dipendere da stato iniziale non in equilibrio, compromesso del fitting, dinamica pregressa o struttura insufficiente; questa run non separa le cause.")
    text('S02 resta quasi fermo per 51/63 s mentre la HR osservata varia di 16 bpm. S06 resta quasi fermo per 55/90 s e presenta anche un gap di 8 s. Il solo plateau finale previsto ≥5 s è S25: sette secondi durante i quali la HR osservata varia di 6 bpm, un caso effettivamente discordante.')
    text('Plateau brevi della HR osservata sono compatibili anche con quantizzazione a 1 bpm o andamento localmente stabile. Non vengono classificati automaticamente come dropout; un sospetto sul sensore richiederebbe la storia originale e informazioni sul dispositivo.')

    page('14a. Caso critico: la campana quasi ignorata')
    image('13_flat_alternative.png','Figura 13. S25: vincitore attenuato e uno degli start bloccati. Il residuo dello start costante è esattamente HR−HR(0); anche il vincitore conserva quasi tutta la forma residua.')
    r=by['S25']
    text(f"S25 (260424160919, lap 035-036) ha HR osservata con escursione 9 bpm e previsione con escursione {num(r['predicted_range'])} bpm: ratio {num(r['amplitude_ratio'],3)}. RMSE={num(r['RMSE'])} bpm potrebbe apparire accettabile, ma R²={num(r['R2_centered'],3)} e il miglioramento di SSE rispetto a HR(0) è soltanto {num(100*r['skill_HR0'],1)}%.")
    text('La HR prima scende, poi risale fino a un plateau interno, infine torna a scendere; la previsione si sposta poco verso l’alto. Nei sette secondi finali il modello è quasi piatto mentre l’osservazione scende di 6 bpm. La correlazione residuo-HR è 0,983. La forma non è recuperata in modo soddisfacente.')
    text(f"K={num(r['K'],4)} bpm/W, L≈10 s e τ={num(r['tau'])} s producono (T−L)/τ={num(r['effective_horizon_over_tau'],3)}. I RSE di K e τ superano il 4.000%, e il CI95 di L include valori negativi. Il caso combina poco contenuto informativo nel transitorio e forte inadeguatezza della previsione di forma.")

    page('14b. Caso critico: errore assoluto elevato')
    image('fit_S12.png','Figura 14. S12: HR sale subito, mentre il P1D resta al riferimento per circa 24 s; la discesa finale prevista è troppo rapida e troppo ampia. L’area gialla indica [0,L].')
    r=by['S12']
    text(f"S12 (250729173622, lap 020-021) è il peggiore per RMSE: <b>{num(r['RMSE'])} bpm</b>, MAE={num(r['MAE'])} bpm, bias={num(r['bias'])} bpm e R²={num(r['R2_centered'],3)}. Nel plateau previsto iniziale l’escursione osservata è 38 bpm.")
    text('La minimizzazione produce un compromesso: recupera parte della HR centrale, ma non la salita iniziale e il recupero finale. La coincidenza centrale non compensa l’errore strutturato ai bordi. K è sul massimo 5 bpm/W, τ≈205,50 s e L≈23,28 s; i CI locali di K e τ attraversano ampiamente zero.')
    text('È plausibile che il segmento inizi durante una dinamica già avviata, incompatibile con l’equilibrio assunto. È anche possibile che il singolo primo campione di potenza non rappresenti il livello di riferimento appropriato. Sono ipotesi coerenti con il grafico, non cause dimostrate senza il pre-segmento FIT.')
    text('S08 è il secondo caso per errore (RMSE 13,13 bpm, R² −0,358, K al bound). Insieme S08 e S12 spiegano oltre metà della SSE della run. Le schede complete permettono di distinguere questi fallimenti dai casi a errore basso ma risposta attenuata.')

    page('14c. Casi informativi: descrizione buona, limiti diversi')
    image('fit_S20.png','Figura 15. S20: il minimo RMSE della run. La previsione cattura la variazione principale, ma conserva uno scarto iniziale sistematico.')
    r=by['S20'];r34=by['S34']
    text(f"S20 (260424160919, lap 010-011) ha RMSE={num(r['RMSE'])} bpm, R²={num(r['R2_centered'],3)} e riduzione SSE rispetto a HR(0) del {num(r['skill_HR0']*100,1)}%. Non è un fit da classificare insieme a S12. Restano però ACF1={num(r['ACF1'],3)}, plateau iniziale discordante e incertezza condizionata agli assunti.")
    text(f"S34 ha la migliore R² ({num(r34['R2_centered'],3)}) ma RMSE={num(r34['RMSE'])} bpm su una variazione HR di 72 bpm: l’errore assoluto più alto di S20 non implica una peggiore fedeltà relativa. Cattura salita e recupero principali, ma il picco è anticipato e la HR prevista è inizialmente inferiore all’osservata.")
    text('La combinazione di errore assoluto, errore relativo e lettura del grafico impedisce due errori opposti: scartare una ricostruzione utile soltanto perché la HR varia molto, oppure accettare un fit quasi costante soltanto perché la HR varia poco.')

    page('14d. Gap, risposta troppo rapida e coda finale')
    image('fit_S06.png','Figura 16. S06: linee interrotte nel gap; il simulatore ha mantenuto la potenza costante in quel tratto. La HR osservata continua a cambiare molto prima che la previsione si muova.')
    text('S06 contiene il solo gap segnalato, massimo 8 s. Il ritardo L=54,71 s produce una lunga zona iniziale quasi costante, seguita da una risposta tardiva. La ACF è calcolata per lag in campioni: qui non equivale uniformemente a un lag in secondi. L’input nel gap è un’assunzione del simulatore, non una misura.')
    text('S09 è un’anomalia differente: L≈0 al bound inferiore e τ≈0,97 s. La previsione segue troppo da vicino le variazioni di potenza, con escursione 18,53 bpm contro 12 bpm osservati; R²=−0,170. Il RSE di L è non definito e quello di τ è 181%. Il modello usa una risposta quasi istantanea, ma la forma non ne trae beneficio.')
    text('S33 mostra un fallimento prevalentemente finale: RMSE nell’ultimo 20% pari a 14,86 bpm, contro 2,77 bpm nel primo 20%. I parametri hanno CI locali relativamente stretti, ma la coda residua resta marcata. Precisione locale e adeguatezza della traiettoria non sono equivalenti; le schede individuali rendono verificabili entrambi i casi.')

    page('15. Interpretazione matematica e passi successivi')
    head('L’equilibrio e il riferimento iniziale possono introdurre struttura comune')
    text('Nel modello HR₀ è un livello additivo fissato. Se il primo campione contiene errore η₀ e gli altri campioni hanno errori ηₜ indipendenti, a parametri fissati un caso ideale dà eₜ≈ηₜ−η₀ per t&gt;0. Allora Cov(eₜ,eₛ)=Var(η₀) per t≠s, mentre e₀=0 per costruzione. Anche l’ancoraggio può dunque introdurre dipendenza; l’ACF osservata non deve essere attribuita automaticamente a una nuova dinamica fisiologica.')
    text('L’errore di equilibrio è distinto dall’errore sul singolo campione: un transitorio precedente può produrre una derivata HR non nulla a t=0, mentre la previsione impone inizialmente una risposta piatta. Il fitting può compensare deformando K, L e τ. Il riferimento P₀ fissato introduce un ulteriore vincolo comune sul forcing.')
    head('Ordine delle verifiche proposte, non eseguite')
    table(['Priorità','Verifica successiva','Evidenza che la motiva'],[
        ['1','Separare convergenza da start senza sensibilità; inizializzazioni temporali compatibili con ogni segmento','169 avvii già nella zona L≥T; nessuna informazione sul minimo globale'],
        ['2','Esaminare il pre-segmento FIT per P₀/HR₀ ed equilibrio, mantenendo confrontabile il resto del protocollo','32 plateau iniziali discordanti, casi S12 e S25'],
        ['3','Valutare identificabilità con esperimenti più informativi e profili/CI adatti a bounds e dipendenza','K al massimo in 6 fit; valli K-τ; RSE estremi'],
        ['4','Ripetere il confronto su sessioni non osservate, con baseline semplici e protocollo congelato','Questa run identifica e valuta sugli stessi segmenti'],
    ],[45,255,WIDTH-300])
    text('Non è ancora giustificato aggiungere covariate o complessità per nascondere questi risultati. H1 (predicibilità fuori campione) non è stata testata; H2 (ripetibilità) non è dimostrata; H3 (valore della complessità) non è valutabile con un solo modello e senza validazione indipendente. Il risultato informativo è che la procedura attuale produce sia traiettorie utili sia fallimenti chiaramente diagnosticabili.')

    page('16. Metodi statistici, sensibilità e limiti')
    text('Le statistiche di distribuzione danno uguale peso ai segmenti. SD campionaria con ddof=1; quantili lineari al 25%, 50%, 75%. Le statistiche pooled pesano i record; le sintesi per attività evitano di confondere sessioni numerose con maggiori repliche indipendenti. Nessun intervallo di popolazione viene ricavato dai 34 segmenti come se fossero indipendenti.')
    text('e=HR−HR̂; RMSE=√mean(e²); MAE=mean(|e|).<br/>R²=1−SSE/Σ(HR−mean(HR))².<br/>Skill rispetto a HR(0)=1−SSE/Σ(HR−HR(0))².<br/>ACF(k)=Σ(eᵢ−ē)(eᵢ₊ₖ−ē)/Σ(eᵢ−ē)², entro ciascun segmento.','formula')
    text('I primi/ultimi 20% sono definiti sul tempo trascorso, includendo gli estremi; non sono finestre del 20% dei record. Il primo residuo nullo è incluso in N e nelle metriche per riprodurre la convenzione della run. Per ACF si usa il lag in campioni e non si ricampiona S06. Le sezioni di SSE non aggiungono nuovi fit né stime.')
    table(['Criterio post-hoc','Regola','Esito'],[
        ['HR globalmente piatta','Range ≤1 bpm','0 osservate; 0 vincitori previsti'],
        ['Risposta attenuata','Ratio ≤0,35; range HR≥3 bpm','7 segmenti'],
        ['Residuo conserva il trend HR','Attenuazione + corr(e,HR)≥0,90','7 segmenti'],
        ['Plateau previsto','Pendenze adiacenti ≤0,05 bpm/s in modulo; ≥5 s','32 discrepanze iniziali; 1 finale'],
        ['Plateau osservato al bordo','Massimo intervallo dal bordo con range ≤1 bpm','Descrittivo; non prova di dropout'],
    ],[125,255,WIDTH-380])
    text('Sensibilità della soglia di attenuazione: ratio≤0,20 identifica 0 fit; ≤0,25 ne identifica 1; ≤0,35 ne identifica 7; ≤0,50 ne identifica 11. I sette casi non sono una classe naturale dimostrata. Le traiettorie, le ampiezze continue e i CSV permettono di cambiare criterio senza ricostruire o modificare l’esperimento.')
    text('L’analisi è post-hoc sul train selezionato, senza correzioni dei segnali, esclusioni silenziose o rifitting. Le ipotesi sulle cause sono separate dai risultati misurati. Errori del sensore, inizializzazione, protocollo di selezione e inadeguatezza strutturale non sono separabili causalmente con questa sola run.')

    page('17. Tracciabilità e riferimenti')
    text('Il report è riproducibile dalla radice del repository con:','body')
    text('<font name="ReportMono">.venv/Scripts/python scripts/report_model_identification.py</font>','small')
    table(['Artefatto','Contenuto'],[
        ['report_analisi_P1D_00e47e9c.pdf','Documento finale'],
        ['segment_metrics.csv','34 righe: fit, residui, parametri, SE/CI/RSE, criteri morfologici'],
        ['multistart_metrics.csv','272 righe: parametri iniziali/finali, SSE, stato e censura temporale'],
        ['activity_metrics.csv','Aggregazione delle cinque attività train'],
        ['summary.json','Statistiche, criteri, hash input, controlli numerici, versioni'],
        ['figures/*.png','Figure di sintesi e una figura originale per ogni fit'],
    ],[195,WIDTH-195])
    text('Le sorgenti della run restano nello storage dell’app e non vengono modificate. Gli hash completi sono in summary.json; report_build.json conserva gli hash dei due script, delle figure e del PDF. Il backup dei risultati deve includere anche manifest e CSV originali; questo report non sostituisce i dati della run.')
    head('Riferimenti metodologici consultati il 26/09/2026')
    references=[
        ('R1','SciPy. least_squares: TRF, residuali, bounds e criteri di arresto.','https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html'),
        ('R2','SciPy. curve_fit: significato della covariance locale e limiti della linearizzazione. Usato come riferimento metodologico, non come funzione di fitting della run.','https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html'),
        ('R3','NIST/SEMATECH. Autocorrelation Plot: definizione e lettura della dipendenza temporale.','https://www.itl.nist.gov/div898/handbook/eda/section3/autocopl.htm'),
        ('R4','NIST/SEMATECH. Assessing independence of random errors: lag plot e distinzione fra trend residuo e dipendenza degli errori.','https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd444.htm'),
    ]
    for label,desc,url in references:
        text(f'<b>[{label}]</b> {escape(desc)}<br/><link href="{url}" color="#257969">{url}</link>','small')
    text('Le spiegazioni su L≥T, rapporto K/τ e rumore condiviso dal riferimento iniziale sono derivazioni esplicite dal modello della run, non risultati attribuiti alla letteratura fisiologica. Le convenzioni grafiche riprendono i report della repository: segnali originali, unità su ciascun asse, gap visibili, criteri empirici dichiarati. Le scale HR locali, qui necessarie per diagnosticare piccoli scarti, sono esplicitate e non confrontabili visivamente senza leggere gli assi.','small')

    for offset in (0,17):
        page(f'Appendice A. Inventario dei fit ({offset+1}-{offset+17})')
        text('Identificativi S01-S34 ordinati per nome CSV; attività A1-A5 definite in sezione 5. Tutte le metriche sono in-sample. R² negativo significa peggio della costante mean(HR) sullo stesso segmento.','small')
        table(['ID','FIT / lap','T [s]','RMSE','R²','Bias','ACF1'],[[r['segment'],r['filename'].replace('.csv','').replace('__laps_',' / '),num(r['duration_s'],0),num(r['RMSE']),num(r['R2_centered']),num(r['bias']),num(r['ACF1'],3)] for r in rows[offset:offset+17]],[35,190,40,60,55,55,WIDTH-435])
        text('Il CSV delle metriche contiene anche MAE, errori iniziali/finali, ampiezze, indicatori di plateau, intervalli dei parametri e diagnostica delle otto inizializzazioni. Nessun segmento è stato scartato per rendere migliori le statistiche.','small')

    # Each individual sheet is a complete, readable audit trail for one segment.
    for z in series:
        r=z['row'];page(f"Scheda {r['segment']} | attività {r['activity_code']}")
        text(r['filename'].replace('.csv','')+f" · durata {num(r['duration_s'],0)} s · {r['samples']} campioni",'small')
        image('fit_'+r['segment']+'.png',f"Figura {r['segment']}. HR osservata (rosso), prevista (verde), potenza (blu, asse destro), HR(0) puntinata; residui sotto. Area gialla: intervallo [0,L]. Nessun smoothing aggiuntivo.")
        table(['Parametro','Stima','SE','CI95 inferiore; superiore','RSE %'],[[k+(' [bpm/W]' if k=='K' else ' [s]'),num(r[k],4 if k=='K' else 2),num(r[k+'_SE'],4 if k=='K' else 2),num(r[k+'_CI_low'],4 if k=='K' else 2)+'; '+num(r[k+'_CI_high'],4 if k=='K' else 2),num(r[k+'_RSE_pct'],1)] for k in ('K','L','tau')],[88,85,85,164,WIDTH-422])
        table(['MAE [bpm]','Bias [bpm]','SD residui','Skill HR(0)','Ratio ampiezza'],[[num(r['MAE']),num(r['bias']),num(r['residual_sd']),num(100*r['skill_HR0'],1)+'%',num(r['amplitude_ratio'],3)]])
        flags=[]
        if r['R2_centered']<0:flags.append('peggio della media HR del segmento (R²<0)')
        if r['attenuated']:flags.append('risposta fortemente attenuata; il residuo conserva il trend HR')
        if r['initial_plateau_mismatch']:flags.append(f"plateau iniziale previsto {num(r['predicted_plateau_initial_s'],0)} s, escursione HR contemporanea {num(r['observed_range_during_initial_plateau'],0)} bpm")
        if r['final_plateau_mismatch']:flags.append(f"plateau finale discordante {num(r['predicted_plateau_final_s'],0)} s")
        if r['K_bound'] or r['L_bound'] or r['tau_bound']:flags.append('bound attivo/vicino: '+', '.join(k for k in ('K','L','tau') if r[k+'_bound']))
        if not r['optimizer_success']:flags.append('ottimizzatore non convergente: limite valutazioni raggiunto')
        if r['max_gap_s']>1.5*r['sampling_median_s']:flags.append(f"gap massimo {num(r['max_gap_s'],0)} s")
        text('<b>Lettura diagnostica.</b> '+('; '.join(flags) if flags else 'Nessun flag morfologico aggiuntivo con le soglie del report.')+'.','small')
        text(f"Status ottimizzatore {r['optimizer_status']}; rango Jacobiano {r['rank']}; corr locale K-τ={num(r['cov_corr_K_tau'],3)}. Start con L iniziale≥T: {r['initial_dead_starts']}/8; con L finale&lt;T: {r['informative_terminal_starts']}/8; concordi col best: {r['matching_starts']}/8. RMSE iniziale/finale (20% del tempo): {num(r['RMSE_initial20'])}/{num(r['RMSE_final20'])} bpm.",'small')
        text('CI95 locali, non corretti per dipendenza temporale e condizionati a P₀/HR₀. ACF1 elevata e disaccordo multistart sono presenti in tutta la run. I flag non sostituiscono la lettura delle traiettorie.','small')

    target=out/'report_analisi_P1D_00e47e9c.pdf'
    def header(canvas,doc):
        canvas.saveState();canvas.setFont('Report',7);canvas.setFillColor(GRAY)
        canvas.drawString(16*mm,A4[1]-12*mm,'POWER_HR_MODEL / IDENTIFICAZIONE DINAMICA')
        canvas.drawRightString(A4[0]-16*mm,A4[1]-12*mm,'26.09.2026 · ANALISI POST-HOC')
        canvas.restoreState()
    doc=SimpleDocTemplate(str(target),pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=20*mm,bottomMargin=21*mm,
                          title='Analisi P1D HR-Power - esperimento 00e47e9c',author='power_HR_model',subject='Parametri, residui, qualità dei fit e identificabilità - train only')
    doc.build(story,onFirstPage=header,onLaterPages=header,canvasmaker=NumberedCanvas)
    from pypdf import PdfReader
    pdf=PdfReader(target);contents=[page.extract_text() or '' for page in pdf.pages]
    for r in rows:
        assert any('Scheda '+r['segment'] in text for text in contents),r['segment']
    assert all(len(text)>100 for text in contents),'Unexpected empty page'
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('report_model_identification.py')]}
    result=dict(pdf=target.name,pages=len(pdf.pages),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),scripts=hashes,
                images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((out/'figures').glob('*.png'))},
                source_run_unchanged=True)
    (out/'report_build.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'README.md').write_text('''# Analisi esperimento P1D 00e47e9c

Report tecnico in italiano sui 34 fit train dell'esperimento
`Up_to_Down_under60s`, senza rifitting o uso di validation/test.

- [Report PDF](report_analisi_P1D_00e47e9c.pdf)
- [Metriche per segmento](segment_metrics.csv)
- [Diagnostica delle 272 inizializzazioni](multistart_metrics.csv)
- [Statistiche per attività](activity_metrics.csv)
- [Criteri, statistiche e hash delle sorgenti](summary.json)
- [Hash degli script, figure e PDF](report_build.json)

## Riproduzione

Dalla radice del repository:

```powershell
.\\.venv\\Scripts\\python scripts/report_model_identification.py
```

Il report è specifico della run `00e47e9c0e2b41b0911e978afd611905`.
Sono necessari manifest, risultati e blob originali nello storage dell'app.
I due script sono `scripts/report_model_identification.py` (analisi e figure)
e `scripts/report_model_identification_pdf.py` (composizione del documento).
`--analysis-only` rigenera CSV, statistiche e figure senza il PDF.
Versioni delle librerie registrate in summary.json. Nessuna casualità aggiunta.

## Convenzioni

Segnali originali senza smoothing, HR rossa, potenza blu e previsione verde;
unità e scale esplicite, gap visibili. I grafici di fit usano scale HR locali
per rendere leggibili le differenze; non confrontare le altezze delle curve
fra schede senza leggere gli assi. Le classificazioni sono euristiche post-hoc,
con soglie in summary.json e sensibilità documentata nel report. Nessuna
esclusione automatica; ogni segmento compare in una scheda dell'appendice.

RSE non definito vicino a zero e intervalli che attraversano zero sono conservati.
Le statistiche sono descrittive e condizionate al campione. I 34 segmenti
provengono da cinque attività e non sono repliche indipendenti.
I record ripetuti fra segmenti non vengono eliminati; i conteggi sono espliciti.

## Verifiche

SHA256 delle sorgenti, corrispondenza CSV-serie, ricalcolo metriche e SE,
ricostruzione indipendente ZOH/ritardo per tutte le previsioni e tutti gli start.
Copertura delle 34 schede e controllo del testo PDF; rendering e revisione
visiva delle pagine prima della consegna. Gli intermedi di rendering sono
sotto tmp/pdfs, fuori dagli artefatti finali.
''',encoding='utf-8')
    print(f'PDF: {len(pdf.pages)} pages; {target}')
