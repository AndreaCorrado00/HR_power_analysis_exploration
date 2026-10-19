"""Publish offline data and a concise report from saved evaluation artifacts."""
import json
from .data import HERE, OUTPUT, save


def publish(output=OUTPUT):
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    hr=json.loads((output/'hr_model.json').read_text(encoding='utf-8'))
    power=json.loads((output/'power/model.json').read_text(encoding='utf-8'))
    frozen=json.loads((output/'frozen.json').read_text(encoding='utf-8'))
    splits={}
    for key in ('validation','test'):
        path=output/f'{key}.json'
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8'))
            if value['hashes']!=frozen['hashes']: raise ValueError('Stale split evaluation')
            splits[key]=value
    bundle=dict(splits=splits,quality=manifest['quality'],split=manifest['split'],
        hr=dict(status=hr['analysis']['status'],model=hr['analysis']['model'],
            retained=hr['analysis']['retained_vectors'],train_count=hr['analysis']['train_count'],
            B_reference=hr['analysis'].get('B_reference'),HR0_reference=hr['analysis'].get('HR0_reference'),
            warnings=hr['analysis']['warnings'],static=hr['static']),
        power=dict(order=power['selected_order'],selection=power['selection'],ar=power['decomposition']['ar']))
    # Rounding is display-only; scoring and JSON artifacts retain full precision.
    for value in splits.values():
        for segment in value['segments']:
            segment['series']={k:[round(v,4) if v is not None else None for v in a]
                               for k,a in segment['series'].items()}
    (output/'results.js').write_text('window.JOINT_RESULTS='+json.dumps(bundle,ensure_ascii=False,allow_nan=False,separators=(',',':'))+';\n',encoding='utf-8')
    lines=['# Risultati esperimento prescribed 42/9/9','',
        'Valutazione retrospettiva; target ricostruiti. Nessuna HR heldout inizializza le predizioni.',
        f"Potenza selezionata: ordine {power['selected_order']} + AR(2).",
        f"HR: {hr['analysis']['status']}; {hr['analysis']['retained_vectors']}/{hr['analysis']['train_count']} vettori ammessi REML.",
        '', 'Metriche aggregate: media non pesata dei valori per workout. Bias = osservato - predetto.',
        'Fasce 95% puntuali: AR potenza + variabilità parametri HR; non comprendono errore HR residuo o incertezza delle medie.', '']
    for key,value in splits.items():
        lines += [f'## {key}',f"Tratti previsti: {len(value['segments'])}/{value['requested_segments']}; fallimenti: {len(value['failures'])}.",
            '', '| Modello | Finestra | Workout | Campioni | MAE | RMSE | Bias | Copertura |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
        for row in value['summary']:
            if row['window']=='initial' or row['model'].endswith('_common'):continue
            cov='—' if row['coverage'] is None else f"{row['coverage']:.1%}"
            lines.append(f"| {row['model']} | {row['window']} | {row['workouts']} | {row['N']} | {row['MAE']:.2f} | {row['RMSE']:.2f} | {row['bias']:.2f} | {cov} |")
        if value['segments']:
            lines += ['',f"Massimo errore standard Monte Carlo della media HR: {max(s['max_mean_mcse_bpm'] for s in value['segments']):.3f} bpm."]
        for failure in value['failures']:lines.append(f"- Fallimento {failure['id']}: {failure['error']}")
        lines.append('')
    lines += ['## Limiti',
        '- Test già esaminato storicamente; split nuovo non equivale a dati vergini.',
        '- Segmenti continui >=300 s; ripartenze a gap/pause, senza reset ai cambi di target.',
        '- Previsioni condizionate ai target ricostruiti e alla disponibilità dei tratti validi.',
        '- Stato lento, fatica e significati fisiologici dei parametri non sono inferiti.',
        '- Parametri HR gaussiani troncati ai bounds; A e HR0 fissi. Rumore potenza indipendente dai parametri HR.',
        '- REML assume indipendenza dei tratti anche quando appartengono allo stesso workout.',
        '- Campioni anomali sono quantificati nel manifest; nessuna correzione o interpolazione automatica.',
        '', 'Protocollo e comandi: ../PROTOCOL.md e ../README.md.']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
