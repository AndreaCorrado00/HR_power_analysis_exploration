"""Run-local reports, derived only from saved results. No model refitting."""
from __future__ import annotations

import csv
import io
import json
import math
import textwrap
import zipfile
from collections import Counter
from xml.sax.saxutils import escape

import numpy as np

QUALITY = ('RMSE', 'MAE', 'bias', 'R2', 'amplitude_ratio')
RESIDUALS = ('residual_mean', 'residual_sd', 'residual_autocorrelation_lag1', 'residual_autocorrelation_lag5')


def flatten(value, prefix=''):
    out = {}
    for k, v in value.items():
        key = prefix+k
        if isinstance(v, dict): out.update(flatten(v, key+'.'))
        else: out[key] = json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
    return out


def csv_data(rows):
    stream = io.StringIO(newline='')
    keys = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def tables_zip(manifest, results, population=None):
    tables = {k: [] for k in ('fits', 'parameters', 'multistart', 'series', 'pre_window', 'residual_acf')}
    for r in results:
        identity = {'run_id':manifest['id'], 'segment_id':r['segment_id'], 'status':r['status']}
        tables['fits'].append(dict(identity, **flatten({k:v for k,v in r.items() if k not in ('series','pre_window','starts','parameters','residual_acf')})))
        for k,p in r.get('parameters',{}).items():
            tables['parameters'].append(dict(identity, parameter=k, **flatten(p)))
        for i,s in enumerate(r.get('starts',[])):
            tables['multistart'].append(dict(identity, start=i+1, **flatten(s)))
        for table in ('series','pre_window'):
            s = r.get(table,{})
            for i,t in enumerate(s.get('time',[])):
                tables[table].append(dict(identity, time=t, **{k:v[i] for k,v in s.items() if isinstance(v,list) and k!='time'}))
        acf = r.get('residual_acf',{})
        for lag, value in zip(acf.get('lags',[]), acf.get('values',[])):
            tables['residual_acf'].append(dict(identity, lag_samples=lag, acf=value))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,rows in tables.items(): z.writestr(name+'.csv',csv_data(rows))
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False))
        z.writestr('results.json',json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False))
        if population is not None:
            z.writestr('population.json', json.dumps(population,ensure_ascii=False,indent=2,allow_nan=False))
            z.writestr('population_screening.csv', csv_data([flatten(r) for r in population['screening']]))
            z.writestr('population_test_metrics.csv', csv_data([flatten({k:v for k,v in r.items() if k!='series'}) for r in population['test']]))
        z.writestr('README.txt','UTF-8 CSV. Empty cells = unavailable/not applicable. Failed records retained; aggregate reports use status=fitted only. Residual = observed - predicted. ACF lags are sample counts. Pre-window never contributes to new segment_v2 objectives. Full diagnostics and context metadata: results.json. Units and parameter order: manifest.json.\n')
    return stream.getvalue()


def finite(values):
    return [float(v) for v in values if isinstance(v,(int,float)) and math.isfinite(v)]


def summary(values):
    v = finite(values)
    return [len(v), *([float(np.mean(v)),float(np.median(v)),float(np.std(v,ddof=1)) if len(v)>1 else None,min(v),max(v)] if v else [None]*5)]


def fmt(value):
    if value is None: return 'n.d.'
    if isinstance(value,bool): return 'si' if value else 'no'
    if isinstance(value,(int,float)): return f'{value:.5g}'
    return str(value)


def pdf_report(manifest, results, population=None):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Preformatted

    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallText',fontSize=8,leading=11,spaceAfter=5,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CodeSmall',fontName='Courier',fontSize=6.5,leading=8))
    story = []
    width = 499
    valid = [r for r in results if r['status']=='fitted']
    params = manifest.get('model',{}).get('parameters',[])
    structure = manifest.get('model_structure',manifest.get('config',{}).get('model_structure','p1d_full (storico)'))

    def p(text, style='SmallText'):
        story.append(Paragraph(escape(str(text)),styles[style]))

    def heading(text): p(text,'Heading2')

    def table(headers, rows, widths=None):
        if not rows:
            p('Nessun valore disponibile.'); return
        cells = [[Paragraph(escape(fmt(v)),styles['SmallText']) for v in row] for row in [headers,*rows]]
        t = Table(cells,colWidths=widths or [width/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4eee9')),
                              ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5),
                              ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#268575')),
                              ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f7')])]))
        story.extend([t,Spacer(1,9)])

    def plot(fig, height):
        stream = io.BytesIO()
        FigureCanvasAgg(fig).print_png(stream)
        stream.seek(0)
        story.append(Image(stream,width=width,height=height))

    def histograms(items, title):
        items = [(label,finite(values)) for label,values in items]
        items = [(label,v) for label,v in items if v]
        if not items:
            p(title+': nessun dato disponibile.'); return
        rows = (len(items)+1)//2
        fig = Figure(figsize=(8.2,2.1*rows),layout='constrained')
        axes = list(fig.subplots(rows,2,squeeze=False).flat)
        for ax,(label,values) in zip(axes,items):
            ax.hist(values,bins=min(12,max(1,int(np.sqrt(len(values))))),color='#268575',edgecolor='white')
            ax.set_title(f'{label} (n={len(values)})',fontsize=9)
            ax.set_ylabel('Segmenti',fontsize=8)
            ax.tick_params(labelsize=8)
        for ax in axes[len(items):]: ax.set_visible(False)
        plot(fig,125*rows)

    def metric_rows(keys):
        return [[k,*summary([r.get('metrics',{}).get(k) for r in valid])] for k in keys]

    p('HR / POWER','Title')
    p('Report di identificazione','Heading1')
    p('Run '+manifest['id'])
    p('Dataset: '+manifest['dataset']['name'])
    p('Creazione: '+manifest.get('created_at','n.d.')+' | Stato: '+manifest['status'])
    p('Struttura: '+structure+' | '+manifest.get('model',{}).get('equation',''))
    p('Inizializzazione: '+manifest.get('initialization_mode','equilibrium (storico)')+' | '+manifest.get('model',{}).get('initial_conditions',''))
    p(f"Dataset: {len(manifest['dataset'].get('segments',[]))} segmenti; train richiesti: {manifest['progress']['total']}; risultati: {len(results)}; validi: {len(valid)}; falliti: {sum(r['status']!='fitted' for r in results)}.")
    p('Ambito identificazione: fit in-sample sui soli segmenti train. '+('Previsione test separata nella sezione Parametri dell atleta; nessun refit sul test.' if population else 'Val/test non utilizzati.')+' Aggregati non pesati per durata, calcolati solo sui record fitted; n indica i valori numerici disponibili. n.d. = non disponibile o non applicabile. Nessuna conclusione fisiologica automatica.')
    p('Pre-window richiesta: '+fmt(manifest.get('use_pre_window'))+'; durata: '+fmt(manifest.get('pre_window_seconds'))+' s. P0: '+manifest.get('P0_method','protocollo storico')+'; HR0: '+manifest.get('HR0_method','protocollo storico'))
    inventory = manifest.get('pre_window_inventory',[])
    p(f"Pre-window disponibili: {sum(bool(s.get('available')) for s in inventory)} / {len(inventory)} segmenti train inventariati.")
    heading('Qualita della traiettoria')
    p('RMSE, MAE e bias in bpm; R2 e amplitude_ratio adimensionali. Bias positivo: HR osservata maggiore della prevista.')
    table(['Metrica','n','Media','Mediana','SD','Min','Max'],metric_rows(QUALITY),[133,30,67,67,67,67,68])
    histograms([(k,[r.get('metrics',{}).get(k) for r in valid]) for k in ('RMSE','R2')],'Qualita')
    story.append(PageBreak())
    heading('Residui')
    p('e = HR osservata - HR prevista. SD campionaria (ddof=1); ACF centrata, lag in campioni. Le segnalazioni sono conservate e non impongono nuove esclusioni.')
    table(['Metrica','n','Media','Mediana','SD','Min','Max'],metric_rows(RESIDUALS),[133,30,67,67,67,67,68])
    histograms([(k,[r.get('metrics',{}).get(k) for r in valid]) for k in ('residual_mean','residual_sd')],'Residui')
    warnings = Counter(w for r in results for w in r.get('warnings',[]))
    table(['Segnalazione','Segmenti'],sorted(warnings.items()),[400,99])
    heading('Multistart')
    p('Ricerca: '+manifest.get('optimizer_settings',{}).get('search_strategy','multistart (storico)')+'. I tentativi comprendono gli eventuali raffinamenti da griglia; n_multistart indica solo gli start originali.')
    starts = [s for r in results for s in r.get('starts',[])]
    p(f"Start registrati: {len(starts)}; convergenti: {sum(bool(s.get('success')) for s in starts)}. Accordo di tutti gli start: {sum(bool(r.get('all_starts_agree')) for r in valid)} / {len(valid)} fit validi.")
    table(['Diagnostica','n','Media','Mediana','SD','Min','Max'],[[k,*summary([s.get(k) for s in starts])] for k in ('SSE','nfev')],[133,30,67,67,67,67,68])
    story.append(PageBreak())
    heading('Distribuzione e precisione dei parametri')
    p('SE e CI95 locali di Wald, condizionati ai riferimenti iniziali. RSE in percentuale. Bounds, autocorrelazione e rango ridotto possono limitare la precisione. Un parametro fissato non ha SE/CI stimabili.')
    table(['Parametro','n','Media','Mediana','SD','Min','Max'],[[f"{p['key']} ({p['unit']})",*summary([r.get('parameters',{}).get(p['key'],{}).get('estimate') for r in valid])] for p in params],[133,30,67,67,67,67,68])
    table(['Parametro','SE mediana','RSE mediana %','Al bound','Vicino al bound'],[[p['key'],summary([r.get('parameters',{}).get(p['key'],{}).get('se') for r in valid])[2],summary([r.get('parameters',{}).get(p['key'],{}).get('rse_pct') for r in valid])[2],sum(bool(r.get('parameters',{}).get(p['key'],{}).get('at_bound')) for r in valid),sum(bool(r.get('parameters',{}).get(p['key'],{}).get('near_bound')) for r in valid)] for p in params])
    histograms([(p['key']+' ('+p['unit']+')',[r.get('parameters',{}).get(p['key'],{}).get('estimate') for r in valid]) for p in params],'Parametri')
    story.append(PageBreak())
    heading('Identificabilita')
    for line in ('rho = (T-L)/tau: tempo disponibile dopo il ritardo in unita di tau. Valori piccoli descrivono una frazione breve del transitorio; nessuna soglia automatica.',
                 'Correlazioni parametriche vicine a -1 o +1 segnalano compensazione locale tra stime; non misurano la qualita della traiettoria.',
                 'Rango Jacobiano: confrontare con p, il numero di parametri liberi. Rango < p indica direzioni non identificabili localmente.',
                 'Multistart: SSE simili con parametri differenti indicano ambiguita. CI e correlazioni restano approssimazioni locali.'):
        p('- '+line)
    table(['Diagnostica','n','Media','Mediana','SD','Min','Max'],[
        ['rho',*summary([r.get('rho') for r in valid])],
        ['correlation_K_tau',*summary([r.get('identifiability',{}).get('correlation_K_tau') for r in valid])],
        ['Jacobian rank',*summary([r.get('uncertainty',{}).get('rank') for r in valid])],
        ['Jacobian condition',*summary([r.get('uncertainty',{}).get('jacobian_condition') for r in valid])]], [133,30,67,67,67,67,68])
    if any(p['key']=='tau' for p in params):
        histograms([('rho',[r.get('rho') for r in valid]),('correlation_K_tau',[r.get('identifiability',{}).get('correlation_K_tau') for r in valid])],'Identificabilita')
    else: p('rho non applicabile alla struttura gamma, L. K e tau non vengono ricostruiti.')

    for r in results:
        story.append(PageBreak())
        p('Scheda segmento','Heading1')
        p(r['filename'])
        p('ID: '+r['segment_id']+' | Stato: '+r['status'])
        p('optimizer_success: '+fmt(r.get('optimizer_success'))+' | identification_valid: '+fmt(r.get('identification_valid')))
        if r.get('error'): p('Fallimento: '+r['error'])
        pre = r.get('pre_window',{})
        init = r.get('initial_conditions',{})
        p(f"Pre-window disponibile: {fmt(pre.get('available'))}; usata: {fmt(pre.get('used'))}; campioni: {fmt(pre.get('samples'))}. P0={fmt(init.get('P0'))} W; HR0={fmt(init.get('HR0'))} bpm.")
        if r.get('initialization_mode') == 'estimated_equilibrium':
            p(f"HR(0) osservata fissata; B={fmt(init.get('B'))} bpm stimato; x(0)={fmt(init.get('x0'))} bpm. B e un livello matematico di equilibrio, senza interpretazione fisiologica.")
        if pre.get('included_in_objective'): p('Replay storico: i campioni pre-window erano parte dell obiettivo originale; asse temporale riferito al primo record.')
        if r.get('metrics'):
            table(['RMSE','MAE','bias','R2','amplitude_ratio'],[[r['metrics'].get(k) for k in QUALITY]])
            table(['residual_mean','residual_sd','ACF lag 1','ACF lag 5'],[[r['metrics'].get(k) for k in RESIDUALS]])
        s = r.get('series')
        if s:
            fig = Figure(figsize=(8.2,3.8),layout='constrained')
            ax, residual_ax, acf_ax = fig.subplots(3,1,gridspec_kw={'height_ratios':[2,1,1]})
            ax.plot(s['time'],s['observed'],label='HR osservata',color='#536a80',lw=1)
            ax.plot(s['time'],s['predicted'],label='HR prevista',color='#268575',lw=1.2)
            power_ax = ax.twinx()
            context = pre if not pre.get('included_in_objective') else {}
            power_ax.step(context.get('time',[])+s['time'],context.get('power',[])+s['power'],where='post',color='#c88c3c',alpha=.6,lw=.8)
            power_ax.set_ylabel('Power (W)',fontsize=7)
            if context.get('time'):
                ax.plot(context['time'],context['observed'],color='#536a80',lw=1)
                ax.axvspan(-10,0,color='#dbe6df',alpha=.6,label='Pre-window')
            ax.set_ylabel('HR (bpm)',fontsize=7)
            ax.legend(fontsize=7,loc='best')
            residual_ax.plot(s['time'],s['residual'],color='#268575',lw=.8)
            residual_ax.axhline(0,color='gray',lw=.5)
            residual_ax.set_ylabel('Residuo (bpm)',fontsize=7)
            residual_ax.set_xlabel('Tempo (s)',fontsize=7)
            acf = r.get('residual_acf',{})
            if acf: acf_ax.bar(acf['lags'],[np.nan if v is None else v for v in acf['values']],color='#536a80')
            acf_ax.set_ylabel('ACF',fontsize=7)
            acf_ax.set_xlabel('Lag (campioni)',fontsize=7)
            for a in (ax,power_ax,residual_ax,acf_ax): a.tick_params(labelsize=7)
            plot(fig,235)
        table(['Parametro','Stima','SE','CI95','RSE %','Bound','Near'],[[k,p.get('estimate'),p.get('se'),' / '.join(fmt(v) for v in p['ci95']) if p.get('ci95') else None,p.get('rse_pct'),p.get('bound_hit',p.get('at_bound')),p.get('near_bound')] for k,p in r.get('parameters',{}).items()],[58,65,65,116,65,65,65])
        uncertainty = r.get('uncertainty',{})
        p(f"rho={fmt(r.get('rho'))}; Jacobian rank={fmt(uncertainty.get('rank'))}/{fmt(uncertainty.get('p'))}; cond={fmt(uncertainty.get('jacobian_condition'))}; accordo multistart={fmt(r.get('all_starts_agree'))}.")
        p('Correlazioni: '+json.dumps(r.get('identifiability',{}).get('correlations',{})))
        starts = r.get('starts',[])
        p(f"Multistart: {len(starts)} tentativi, {sum(bool(s.get('success')) for s in starts)} convergenti; SSE min/max: "+ (' / '.join(fmt(v) for v in (min(s['SSE'] for s in starts),max(s['SSE'] for s in starts))) if starts else 'n.d.'))
        search = r.get('search',{})
        if search.get('strategy') == 'profile_multistart':
            p(f"Griglia: {search.get('grid_evaluations')} coppie L/tau; SSE multistart originale: {fmt(search.get('baseline_SSE'))}; selezione: {search.get('selected_source')}.")
        p('Segnalazioni: '+(', '.join(r.get('warnings',[])) or 'nessuna'))

    story.append(PageBreak())
    if population is not None:
        from .population_report import append_population
        append_population(population, p, heading, table, plot, lambda: story.append(PageBreak()))
        story.append(PageBreak())
    heading('Configurazione completa dell esperimento')
    config = {k:v for k,v in manifest.items() if k not in ('dataset','environment','model')}
    config['model'] = {k:v for k,v in manifest.get('model',{}).items() if k!='structures'}
    config['dataset'] = {k:v for k,v in manifest['dataset'].items() if k not in ('segments','source_manifests')}
    config['dataset']['segments'] = [{k:s.get(k) for k in ('id','filename','sha256','duration_seconds','samples')} for s in manifest['dataset'].get('segments',[])]
    config['environment'] = manifest.get('environment',{})
    p('Configurazione, split, sorgenti, hash e ambiente della run. I CSV originali restano conservati nel blob store. Manifest integrale e risultati sono inclusi nell export tabellare ZIP.')
    text = json.dumps(config,ensure_ascii=True,indent=2,allow_nan=False)
    lines = '\n'.join('\n'.join(textwrap.wrap(line,105,replace_whitespace=False,drop_whitespace=False)) or '' for line in text.splitlines())
    story.append(Preformatted(lines,styles['CodeSmall']))

    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont('Helvetica',7)
        canvas.setFillColor(colors.HexColor('#536a80'))
        canvas.drawString(48,25,'HR-Power | '+manifest['id'])
        canvas.drawRightString(547,25,str(doc.page))
        canvas.restoreState()
    doc = SimpleDocTemplate(output,pagesize=(595,842),leftMargin=48,rightMargin=48,topMargin=38,bottomMargin=42,
                            title='HR-Power - '+manifest['id'],author='HR-Power identification app')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
