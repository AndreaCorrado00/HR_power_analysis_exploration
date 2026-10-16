"""Fit/evaluate variance only; publish separate artifacts for the existing viewer."""
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm
from .garch import GARCH11,fit_garch,simulate,burn_in,conditional_metrics,interval_metrics
from .model import DecompositionModel
from .data import verify_inputs,sha256
from .diagnostics_analysis import arch_lm,bh_adjust,markdown_table
from .interval_diagnostics import acf_components,ratio


def innovations(segment,model):
    residual = segment.residual-model.dynamics.response(segment.target)
    p = model.ar.p
    e = residual[p:]-model.ar.intercept
    for j,coefficient in enumerate(model.ar.coefficients,1):
        e -= coefficient*residual[p-j:len(residual)-j]
    return e


def run(args):
    from .cli import read_json,get_segments,resolved_records,atomic_text,encode,digest,read_results
    output = Path(args.output)
    base = read_json(output/'model.json')
    mean = DecompositionModel.from_dict(base['decomposition'])
    records = resolved_records(base)
    verify_inputs(records)
    baseline_hash = sha256(output/'model.json')
    protected = {n:sha256(output/n) for n in ['model.json','results.js','predictions.csv','metrics.csv','report.md'] if (output/n).exists()}
    path = output/'garch_model.json'
    if args.command=='fit-garch':
        if path.exists() and not args.overwrite:
            raise FileExistsError('GARCH already fitted; use test-garch or --overwrite')
        train,_ = get_segments(base,'train')
        parts,clusters = [],[]
        for segment in train:
            if len(segment.residual)>mean.ar.p:
                parts.append(innovations(segment,mean)); clusters.append(segment.workout_id)
        garch,statistics = fit_garch(parts,clusters)
        saved = dict(format_version=1,baseline_sha256=baseline_hash,baseline_model_hash=digest(base),
            model=garch.to_dict(),statistics=statistics,split=base['split'],
            config=dict(seed=mean.seed,paths=mean.paths,distribution='Gaussian',fit='Gaussian QML',
                weighting='equal sample',initial_variance='unconditional at each real segment',
                mean_model='frozen',stationary_simulation_burn_in=burn_in(garch,mean.ar),
                bounds='omega_scaled>=1e-8, alpha,beta>=0, alpha+beta<=1-1e-6'),
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__),
            training_workouts=len(set(clusters)),source_sha256={r['workout_id']:r['sha256'] for r in records},
            code_sha256={name:sha256(Path(__file__).with_name(name)) for name in ['garch.py','garch_run.py']})
        splits = ['validation','test']
    else:
        saved = read_json(path)
        if saved['baseline_sha256']!=baseline_hash:
            raise ValueError('Frozen mean model changed; GARCH evaluation rejected')
        garch = GARCH11(**{k:saved['model'][k] for k in ['omega','alpha','beta']})
        splits = ['validation','test'] if args.split=='both' else [args.split]
    original = read_results(output)
    if original['model_hash']!=digest(base):
        raise ValueError('Original viewer/model mismatch')
    # Existing evaluation samples are the reference; no stochastic baseline rerun.
    frame = pd.read_csv(output/'predictions.csv',dtype={'workout_id':str})
    results = dict(baselineModelHash=digest(base),model=saved,splits={})
    prior = output/'garch_results.js'
    prefix = 'window.POWER_GARCH_RESULTS = '
    if args.command=='test-garch' and prior.exists():
        results = json.loads(prior.read_text(encoding='utf-8')[len(prefix):-2])
        if results['baselineModelHash']!=digest(base) or results['model']!=saved:
            raise ValueError('GARCH viewer/model mismatch')
    exported,metrics,diagnostics = [],[],[]
    # Keep previously evaluated splits when evaluating a subset.
    if args.command=='test-garch':
        for name,target in [('garch_predictions.csv',exported),('garch_metrics.csv',metrics),('garch_diagnostics.csv',diagnostics)]:
            if (output/name).exists():
                old = pd.read_csv(output/name,dtype={'workout_id':str})
                old = old[~old.split.isin(splits)]
                if len(old):
                    target.append(old)
    for split in splits:
        d = frame[frame.split==split]
        if set(d.workout_id)!=set(base['split'][split]):
            raise ValueError(f'Missing frozen baseline {split}; run the existing test command first')
        workouts = {}
        for wid,g in d.groupby('workout_id',sort=False):
            g = g.copy().reset_index(drop=True)
            for col in ['h_w2','standardized','conditional_mean_w','garch_sample_w','garch_low_w','garch_high_w']:
                g[col] = np.nan
            words = np.frombuffer(hashlib.sha256(wid.encode()).digest()[:16],dtype='<u4').tolist()
            rng = np.random.default_rng(np.random.SeedSequence([saved['config']['seed'],*words]))
            for _,part in g.groupby('segment_id',sort=False):
                if np.any(np.diff(part.time_s)!=1):
                    raise ValueError('Unexpected internal gap')
                residual = part.final_residual_w.to_numpy()
                p = mean.ar.p
                e = residual[p:]-mean.ar.intercept
                for j,coef in enumerate(mean.ar.coefficients,1):
                    e -= coef*residual[p-j:len(residual)-j]
                np.testing.assert_allclose(part.innovation_w.to_numpy()[p:],e,atol=1e-9)
                if part.innovation_w.iloc[:p].notna().any():
                    raise ValueError('Innovation has insufficient AR history')
                ids = part.index[p:]
                if len(e):
                    h = garch.variance(e)
                    g.loc[ids,'h_w2'] = h
                    g.loc[ids,'standardized'] = e/np.sqrt(h)
                    g.loc[ids,'conditional_mean_w'] = part.real_w.iloc[p:].to_numpy()-e
                sim = simulate(garch,mean.ar,len(part),saved['config']['paths'],rng)
                lo,hi = np.quantile(sim,[.1,.9],axis=0)
                g.loc[part.index,'garch_sample_w'] = sim[0]
                g.loc[part.index,'garch_low_w'] = lo
                g.loc[part.index,'garch_high_w'] = hi
            valid = g.innovation_w.notna()
            e = g.loc[valid,'innovation_w'].to_numpy()
            h = g.loc[valid,'h_w2'].to_numpy()
            rows,diags,acf = [],[],{}
            for label,variance in [('constant',np.full(len(e),mean.ar.sigma2)),('garch',h)]:
                rows.append(dict(split=split,workout_id=wid,model=label,mode='conditional',
                    **conditional_metrics(e,variance)))
                parts = [part.innovation_w.dropna().to_numpy()/(np.sqrt(mean.ar.sigma2) if label=='constant'
                         else np.sqrt(part.loc[part.innovation_w.notna(),'h_w2'].to_numpy()))
                         for _,part in g.groupby('segment_id') if part.innovation_w.notna().any()]
                num,den,pairs = acf_components([x*x for x in parts])
                acf[label] = ratio(num,den)[0].tolist()
                for lag in [5,15,30]:
                    diags.append(dict(split=split,workout_id=wid,model=label,lag_s=lag,**arch_lm(parts,lag)))
            for label,lo,hi in [('constant',g.ar_low_w,g.ar_high_w),('garch',g.garch_low_w,g.garch_high_w)]:
                rows.append(dict(split=split,workout_id=wid,model=label,mode='free',
                    **interval_metrics(g.final_residual_w.to_numpy(),lo.to_numpy(),hi.to_numpy())))
            metrics.append(pd.DataFrame(rows)); diagnostics.append(pd.DataFrame(diags))
            fields = dict(t='time_s',segment='segment_id',target='target_w',real='real_w',
                epsilon='innovation_w',h='h_w2',z='standardized',conditionalMean='conditional_mean_w',
                arSample='garch_sample_w',low='garch_low_w',high='garch_high_w')
            payload = {k:g[col].astype(object).where(g[col].notna(),None).tolist() for k,col in fields.items()}
            payload.update(acf=acf,metrics=rows,arch=diags)
            workouts[wid] = payload
            exported.append(g[['split','workout_id','time_s','segment_id','innovation_w','h_w2','standardized',
                'conditional_mean_w','garch_sample_w','garch_low_w','garch_high_w']])
            print(f'GARCH: {split} {wid}',flush=True)
        results['splits'][split] = dict(workouts=workouts)
    m = pd.concat(metrics,ignore_index=True)
    dg = pd.concat(diagnostics,ignore_index=True)
    dg['p_fdr'] = np.nan
    for _,indices in dg.groupby('model').groups.items():
        dg.loc[indices,'p_fdr'] = bh_adjust(dg.loc[indices,'p_value'])
    summary = m.groupby(['split','mode','model']).agg(workouts=('workout_id','nunique'),
        n=('n','sum'),nll=('nll','mean'),coverage80=('coverage80','mean'),width80_w=('width80_w','mean'),
        interval_score80_w=('interval_score80_w','mean')).reset_index()
    results['summary'] = summary.astype(object).where(summary.notna(),None).to_dict('records')
    verify_inputs(records)
    if any(sha256(output/n)!=s for n,s in protected.items()):
        raise RuntimeError('Baseline artifacts changed')
    # Nothing is published until fitting, simulation and input checks all succeed.
    if args.command=='fit-garch':
        atomic_text(path,encode(saved)+'\n')
    atomic_text(output/'garch_results.js',prefix+encode(results).replace('<','\\u003c')+';\n')
    atomic_text(output/'garch_predictions.csv',pd.concat(exported,ignore_index=True).to_csv(index=False,lineterminator='\n'))
    atomic_text(output/'garch_metrics.csv',m.to_csv(index=False,lineterminator='\n'))
    atomic_text(output/'garch_diagnostics.csv',dg.to_csv(index=False,lineterminator='\n'))
    atomic_text(output/'garch_summary.csv',summary.to_csv(index=False,lineterminator='\n'))
    params = pd.DataFrame(saved['statistics']['parameters'])
    count = dg.assign(reject=dg.p_fdr<.05).groupby(['split','model','lag_s']).agg(
        significant_fdr=('reject','sum'),workouts=('workout_id','nunique')).reset_index()
    fourth = 3*garch.alpha**2+2*garch.alpha*garch.beta+garch.beta**2
    interpretation = []
    for split in summary.split.unique():
        s = summary[summary.split==split].set_index(['mode','model'])
        if all((mode,label) in s.index for mode in ['conditional','free'] for label in ['constant','garch']):
            interpretation.append(f"- {split}: ΔNLL a un passo = "
                f"{s.loc[('conditional','garch'),'nll']-s.loc[('conditional','constant'),'nll']:.3f}; "
                f"Δinterval score a un passo = {s.loc[('conditional','garch'),'interval_score80_w']-s.loc[('conditional','constant'),'interval_score80_w']:.2f} W; "
                f"Δinterval score libero = {s.loc[('free','garch'),'interval_score80_w']-s.loc[('free','constant'),'interval_score80_w']:.2f} W. "
                'Delta = GARCH − costante: negativo favorisce GARCH.')
    lines = ['# AR(2) congelato + GARCH(1,1)','',
        'Fit della sola varianza sul training; validation e test già esaminati sono descrittivi. '
        'Risposta dinamica, AR, split e artefatti originali invariati. Nessuna covariata aggiunta.', '',
        markdown_table(params),'',f"Persistenza α+β: {garch.alpha+garch.beta:.6f}; varianza incondizionata: {garch.unconditional_variance:.3f} W².",
        f"Training: {saved['training_workouts']} workout, {saved['statistics']['nobs']} innovazioni. "
        f"Avvisi: {saved['statistics']['warnings'] or 'nessuno'}. La routine non riporta IC locali quando rileva "
        'persistenza elevata o stime al bordo; None significa non stimato, non incertezza nulla. '
        'Gli IC locali cluster workout, quando disponibili, sono condizionati alla media congelata; '
        'non includono incertezza della dinamica/AR né della ricostruzione target.', '',
        '## Lettura dei risultati','',*interpretation,'',
        f"Controllo del quarto momento gaussiano: 3α²+2αβ+β² = {fourth:.6f}; " +
        ('non è <1, quindi il quarto momento incondizionato non è finito nel modello stimato. '
         'La varianza incondizionata resta finita perché α+β<1. Questo segnala code marginali molto pesanti '
         'e cautela nell’interpretare diagnostiche dei quadrati e simulazioni finite.' if fourth>=1 else
         'è <1, compatibile con quarto momento incondizionato finito.'), '',
        'Valutare separatamente uso aggiornato e simulazione libera. Una migliore NLL condizionata non '
        'giustifica automaticamente la sostituzione della simulazione AR. Copertura diversa dall’80% '
        'nominale indica calibrazione ancora imperfetta; persistenza e incertezza richiedono cautela. '
        'Non è stato imposto un ulteriore vincolo sul quarto momento e non è stato aggiunto un modello di contesto.', '',
        '## Metriche fuori training','',
        'Medie con peso uguale per workout. NLL e interval score: minore è meglio; copertura nominale 0.80. '
        'Le due modalità rispondono a domande diverse e non vanno confrontate fra loro.', '',
        markdown_table(summary),'',
        'Conditional: media AR usa residui osservati fino a t−1; h_t usa solo ε fino a t−1. '
        'Primi due campioni esclusi. Bande Gaussiane a un passo. La media è identica fra varianza costante e GARCH. '
        'Free: nessun feedback osservato; P10/P90 empirici delle traiettorie, non bande sulla media. '
        f"{saved['config']['paths']} traiettorie, seed {saved['config']['seed']}; quantili soggetti a errore Monte Carlo. "
        'La baseline free mantiene esattamente le simulazioni esistenti. Nessun clipping.', '',
        '## ARCH sulle innovazioni standardizzate','',markdown_table(count),'',
        'FDR sui workout×lag separatamente per modello. P-value e statistiche completi in garch_diagnostics.csv. '
        'Riduzione dei rigetti non dimostra adeguatezza delle code Gaussiane: leggere anche copertura e score.', '',
        '## Protocollo','',
        'ε_t=√h_t z_t; h_t=ω+α ε²_(t−1)+β h_(t−1), z Gaussiani standard nella simulazione. '
        'ω in W², α/β adimensionali. QML gaussiana, peso per campione, 6 partenze SLSQP, vincoli positività/stazionarietà. '
        'Nessuna selezione sul test. La distribuzione Gaussiana è una scelta iniziale da verificare.',
        'h iniziale = ω/(1−α−β) per ogni tratto valido reale, nessun reset ai lap/target. '
        f"Simulazione congiunta AR/GARCH: warm-up {saved['config']['stationary_simulation_burn_in']} s, "
        'almeno 2000 s e decadimento atteso <1e−8, rifiutata se richiede oltre 100000 s. '
        'Le traiettorie sono autonome: non riproducono intenzionalmente il timing degli episodi osservati di alta varianza.', '',
        '[Bollerslev (1986)](https://doi.org/10.1016/0304-4076(86)90063-1). '
        'Hash, versioni, partenze e parametri in garch_model.json. Comandi e pagina HTML in README.md.']
    atomic_text(output/'garch_report.md','\n'.join(lines)+'\n')
    evaluation = dict(baseline_sha256=protected,garch_model_sha256=sha256(path),
        splits=list(results['splits']),
        code_sha256={name:sha256(Path(__file__).with_name(name)) for name in ['garch.py','garch_run.py','cli.py']},
        output_sha256={name:sha256(output/name) for name in ['garch_results.js','garch_predictions.csv',
            'garch_metrics.csv','garch_summary.csv','garch_diagnostics.csv','garch_report.md']})
    atomic_text(output/'garch_evaluation.json',encode(evaluation)+'\n')
    print(summary.to_string(index=False),flush=True)
