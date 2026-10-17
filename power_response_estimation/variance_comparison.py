"""Reproduce train/validation-only variance comparison: python -m this.module."""
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
import pandas as pd
from .cli import read_json, get_segments, atomic_text, encode, resolved_records
from .model import DecompositionModel
from .garch_run import innovations
from .garch import GARCH11, simulate, conditional_metrics, interval_metrics
from .variance_models import context_features, fit_targeted, fit_context, simulate_context
from .diagnostics_analysis import arch_lm, markdown_table
from .interval_diagnostics import acf_components, ratio
from .data import sha256, verify_inputs


def compact_view(view):
    """Viewer-only rounding; metric CSVs retain full numerical precision."""
    for workouts in view.values():
        for payload in workouts.values():
            for key,values in payload.items():
                if key != 'models':
                    payload[key] = [None if v is None else round(v,3) for v in values]
            for model in payload['models'].values():
                for key,values in model.items():
                    model[key] = [round(v,6 if key=='acf' else 3) for v in values]
    return view


def context_report(subgroup, diagnostics):
    phase = subgroup[(subgroup.split=='validation') & (subgroup.dimension=='phase')]
    jump = subgroup[(subgroup.split=='validation') & (subgroup.dimension=='jump')]
    arch = diagnostics[diagnostics.split=='validation'].assign(reject=lambda x:x.p_value<.05).groupby(
        ['model','lag']).agg(significant=('reject','sum'),workouts=('workout_id','nunique')).reset_index()
    cols=['band','model','workouts','n','coverage80','width80_w','interval_score80_w']
    return ('\n## Validation per fase e salto\n\n'+markdown_table(phase[cols])+'\n\n'+markdown_table(jump[cols])+
        '\n\n## ARCH-LM validation dopo standardizzazione\n\nP-value nominali <0.05; conteggi diagnostici, non corretti per confronti multipli.\n\n'+markdown_table(arch)+
        '\n\nLa riduzione globale delle bande va verificata sulle transizioni: una copertura inferiore all’80% indica sottocopertura. '
        'Il contesto non sostituisce automaticamente la memoria degli errori: osservare la diagnostica standardizzata. '
        'Le fasce con pochi workout non consentono conclusioni altrettanto robuste. '
        'Il viewer arrotonda a 0.001 W/W² (ACF a 6 decimali); CSV e metriche conservano la precisione originale.\n')


def strata(target):
    jump, age = None, 0
    rows = []
    for i,p in enumerate(target):
        if i and p != target[i-1]:
            jump, age = abs(p-target[i-1]), 0
        elif i:
            age += 1
        band = 'unknown' if jump is None else ('0-25' if jump<25 else '25-75' if jump<75 else '75-150' if jump<150 else '150+')
        rows.append([f'{int(p//50)*50}-{int(p//50)*50+50}', band,
                     'start' if jump is None else 'transition' if age<30 else 'plateau'])
    return np.array(rows)


def run():
    out = Path(__file__).parent
    base = read_json(out/'model.json')
    selected_ids = set(base['split']['train']+base['split']['validation'])
    records = [r for r in resolved_records(base) if r['workout_id'] in selected_ids]
    verify_inputs(records)
    original = read_json(out/'garch_model.json')
    protected = {f:sha256(out/f) for f in ['model.json','garch_model.json','results.js','garch_results.js']}
    if original['baseline_sha256'] != protected['model.json']:
        raise ValueError('GARCH baseline mismatch')
    mean = DecompositionModel.from_dict(base['decomposition'])
    p = mean.ar.p
    train,_ = get_segments(base,'train')
    train = [s for s in train if len(s.target)>p]
    errors = [innovations(s,mean) for s in train]
    targeted,ts = fit_targeted(errors)
    beta,cs = fit_context([context_features(s.target)[p:] for s in train],errors,[s.workout_id for s in train])
    garch = GARCH11(**{k:original['model'][k] for k in ['omega','alpha','beta']})
    models = dict(targeted=targeted.to_dict(),context=dict(beta=beta.tolist()),targeted_statistics=ts,context_statistics=cs)
    print(encode(models),flush=True)
    metrics,groups,diagnostics,view = [],[],[],{}
    for split in ['train','validation']:
        segments = train if split=='train' else get_segments(base,split)[0]
        for wid in dict.fromkeys(s.workout_id for s in segments):
            data = {name:[] for name in ['constant','garch','targeted','context']}
            payload = dict(t=[],target=[],real=[],mean=[],conditionalMean=[],models={})
            for s in [s for s in segments if s.workout_id==wid and len(s.target)>p]:
                n = len(s.target)
                residual = s.residual-mean.dynamics.response(s.target)
                e = innovations(s,mean)
                x = context_features(s.target)
                hs = dict(constant=np.full(n,mean.ar.sigma2), context=np.exp(x@beta))
                hs['garch'] = np.r_[np.full(p,garch.unconditional_variance),garch.variance(e)]
                hs['targeted'] = np.r_[np.full(p,targeted.unconditional_variance),targeted.variance(e)]
                seed = int.from_bytes(hashlib.sha256(f'{wid}:{s.segment_id}'.encode()).digest()[:8],'little')
                tags = strata(s.target)
                det = s.target+mean.dynamics.response(s.target)
                payload['t'].extend(s.time.tolist()); payload['target'].extend(s.target.tolist())
                payload['real'].extend((s.target+s.residual).tolist())
                payload['mean'].extend((det+mean.ar.intercept/(1-sum(mean.ar.coefficients))).tolist())
                payload['conditionalMean'].extend([None]*p+(s.target[p:]+s.residual[p:]-e).tolist())
                for name,h in hs.items():
                    rng = np.random.default_rng(seed)
                    if name in ['garch','targeted']:
                        sims = simulate(garch if name=='garch' else targeted,mean.ar,n,1000,rng)
                    else:
                        sims = simulate_context(mean.ar,h,rng.standard_normal((1000,n)),rng.standard_normal((1000,p)))
                    lo,hi = np.quantile(sims,[.1,.9],axis=0)
                    v = payload['models'].setdefault(name,dict(h=[],low=[],high=[],sample=[]))
                    for field,values in [('h',h),('low',det+lo),('high',det+hi),('sample',det+sims[0])]:
                        v[field].extend(values.tolist())
                    data[name].append(dict(e=e,h=h[p:],residual=residual,low=lo,high=hi,tags=tags))
            for name,parts in data.items():
                cat = lambda key:np.concatenate([a[key] for a in parts])
                e,h = cat('e'),cat('h')
                common = dict(split=split,workout_id=wid,model=name)
                metrics.extend([{**common,'mode':'conditional',**conditional_metrics(e,h)},
                    {**common,'mode':'free',**interval_metrics(cat('residual'),cat('low'),cat('high'))}])
                standardized = [a['e']/np.sqrt(a['h']) for a in parts]
                num,den,_ = acf_components([z*z for z in standardized])
                payload['models'][name]['acf'] = ratio(num,den)[0].tolist()
                for lag in [5,15,30]:
                    diagnostics.append({**common,'lag':lag,**arch_lm(standardized,lag)})
                for j,dimension in enumerate(['target','jump','phase']):
                    tags = cat('tags')[:,j]
                    etags = np.concatenate([a['tags'][p:,j] for a in parts])
                    for band in np.unique(tags):
                        mask,emask = tags==band,etags==band
                        if emask.sum()<2:
                            continue
                        groups.append({**common,'dimension':dimension,'band':band,
                            'innovation_variance':float(np.var(e[emask],ddof=1)),
                            'innovation_bias':float(np.mean(e[emask])),
                            'predicted_innovation_variance':float(np.mean(h[emask])),
                            **interval_metrics(cat('residual')[mask],cat('low')[mask],cat('high')[mask])})
            view.setdefault(split,{})[wid] = payload
            print(f'Completed {split} {wid}',flush=True)
    m,g,d = pd.DataFrame(metrics),pd.DataFrame(groups),pd.DataFrame(diagnostics)
    verify_inputs(records)
    summary = m.groupby(['split','mode','model'])[['coverage80','width80_w','interval_score80_w','nll']].mean().reset_index()
    subgroup = g.groupby(['split','dimension','band','model']).agg(workouts=('workout_id','nunique'),n=('n','sum'),
        coverage80=('coverage80','mean'),width80_w=('width80_w','mean'),interval_score80_w=('interval_score80_w','mean'),
        innovation_variance=('innovation_variance','mean'),predicted_innovation_variance=('predicted_innovation_variance','mean')).reset_index()
    for f,df in [('metrics',m),('summary',summary),('groups',g),('group_summary',subgroup),('diagnostics',d)]:
        atomic_text(out/f'variance_{f}.csv',df.to_csv(index=False,lineterminator='\n'))
    atomic_text(out/'variance_models.json',encode(models)+'\n')
    atomic_text(out/'variance_results.js','window.VARIANCE_RESULTS = '+encode(dict(splits=compact_view(view),summary=summary.fillna('').to_dict('records'),groups=subgroup.to_dict('records')))+';\n')
    protocol = '''# Confronto della varianza: train e validation

Fit solo train; validation fuori dal fitting. Test escluso: non caricato e non valutato.
Le osservazioni dell'utente che motivano questo confronto non provengono dal test.
Media dinamica e AR congelati. Baseline costante e GARCH originale congelati.
Variance targeting: omega=(1-alpha-beta)*mean(epsilon_train²), Gaussian QML multistart.
Contesto (nuova proposta esplorativa, non modello ciclistico pubblicato):
log(h/W²)=b0+b1*target/100W+b2*abs(ultimo salto)/100W*exp(-eta/30s).
Coefficienti adimensionali, segni liberi; fit Gaussian QML. 30 s fissati prima del fit.
Nessun salto iniziale inventato: transiente nullo fino alla prima variazione nel segmento.
Reset ai gap reali; innovazioni disponibili dopo p campioni; nessun collegamento ACF/ARCH fra gap.
Simulazioni gaussiane libere: 1000 traiettorie per segmento, seed SHA256(workout:segment), nessun feedback osservato.
GARCH inizializzato con warm-up stazionario; contesto/costante con stato AR stazionario per h iniziale.
Gli intervalli sono quantili marginali 10%-90%, non bande simultanee per intere traiettorie.
Metriche aggregate: media con peso uguale per workout, anche nelle fasce; numerosita riportate.
Jump: ampiezza dell'ultimo salto (<25,25-75,75-150,>=150 W); fase: primi30s o plateau.
La fascia del salto persiste fino al salto successivo: non classifica l'intero workout.
Intervalli di confidenza parametrici non stimati; resta da valutare stabilita tra workout e sensibilita ai30s.
ARCH p-value nominali, diagnostici; nessuna selezione tramite significativita multipla.
Fonti: Engle1982 doi:10.2307/1912773; Francq et al.2011 Merits and Drawbacks of Variance Targeting;
Gneiting e Raftery2007 doi:10.1198/016214506000001437.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.variance_comparison
'''
    validation = m[(m.split=='validation') & (m['mode']=='free')]
    paired = validation.pivot(index='workout_id',columns='model',values='interval_score80_w')
    comparisons = pd.DataFrame([dict(model=name,
        delta_score_vs_constant=float((paired[name]-paired.constant).mean()),
        improved_workouts=int((paired[name]<paired.constant).sum()),workouts=len(paired))
        for name in ['garch','targeted','context']])
    fourth = (targeted.alpha+targeted.beta)**2+2*targeted.alpha**2
    extra = ('\n## Validation: confronto appaiato delle bande libere\n\n'+markdown_table(comparisons)+
        f'\n\nVariance targeting: persistenza={targeted.alpha+targeted.beta:.6f}; '
        f'varianza incondizionata={targeted.unconditional_variance:.3f} W²; '
        f'fattore quarto momento gaussiano={fourth:.6f}. '
        +('Quarto momento non finito nel modello: cautela sulle code e sulla stabilita Monte Carlo.' if fourth>=1 else 'Quarto momento finito nel modello.')+
        '\n\nParametri del contesto [b0,b1,b2]: '+str(beta.tolist())+'.\n')
    atomic_text(out/'variance_report.md',protocol+'\n'+markdown_table(summary)+'\n'+extra+context_report(subgroup,d))
    assert all(sha256(out/f)==h for f,h in protected.items())
    atomic_text(out/'variance_manifest.json',encode(dict(protected=protected,paths=1000,splits=['train','validation'],
        code={f:sha256(out/f) for f in ['variance_models.py','variance_comparison.py']},
        sources={r['workout_id']:r['sha256'] for r in records},
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__)))+'\n')
    print(summary.to_string(index=False),flush=True)


if __name__=='__main__':
    run()
