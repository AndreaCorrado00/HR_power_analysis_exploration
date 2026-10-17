"""Within-lap temporal SD: observed versus autonomous simulated power."""
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from .cli import read_json, resolved_records, atomic_text, encode
from .data import segment_frame, verify_inputs, sha256
from .model import DecompositionModel
from .garch import GARCH11, simulate
from .variance_models import context_features, simulate_context
from .diagnostics_analysis import markdown_table


def run():
    out=Path(__file__).parent
    base=read_json(out/'model.json'); variants=read_json(out/'variance_models.json')
    mean=DecompositionModel.from_dict(base['decomposition'])
    original=read_json(out/'garch_model.json')
    if original['baseline_sha256']!=sha256(out/'model.json'):
        raise ValueError('Original GARCH and frozen mean model mismatch')
    prior=read_json(out/'variance_manifest.json')
    if any(sha256(out/f)!=h for f,h in prior['protected'].items()):
        raise ValueError('Variance comparison baseline artifacts changed')
    garches={name:GARCH11(**{k:source[k] for k in ['omega','alpha','beta']})
             for name,source in [('garch',original['model']),('targeted',variants['targeted'])]}
    ids=set(base['split']['train']+base['split']['validation'])
    records=[r for r in resolved_records(base) if r['workout_id'] in ids]
    verify_inputs(records)
    rows=[]
    for record in records:
        wid=record['workout_id']; split='train' if wid in base['split']['train'] else 'validation'
        frame=pd.read_csv(record['path']); indexed=frame.set_index('elapsed_seconds')
        starts=frame.groupby('lap_index').elapsed_seconds.min()
        segments,_=segment_frame(frame,wid,split_at_prescription=False)
        accum={}
        for s in segments:
            if len(s.target)<=mean.ar.p: continue
            laps=indexed.loc[s.time,'lap_index'].to_numpy()
            age=np.zeros(len(s.time)); last=s.time[0]
            for i in range(len(s.time)):
                if i and s.target[i]!=s.target[i-1]: last=s.time[i]
                age[i]=s.time[i]-last
            stable=(age>=30)&(s.time-np.array([starts.loc[x] for x in laps])>=30)
            det=s.target+mean.dynamics.response(s.target)
            actual=s.target+s.residual
            masks={(int(lap),phase):(laps==lap)&mask for lap in np.unique(laps)
                   for phase,mask in [('full',np.ones(len(laps),bool)),('stable',stable),('transition',~stable)]}
            seed=int.from_bytes(hashlib.sha256(f'{wid}:{s.segment_id}'.encode()).digest()[:8],'little')
            for name in ['constant','garch','targeted','context']:
                rng=np.random.default_rng(seed)
                if name in garches:
                    sims=simulate(garches[name],mean.ar,len(s.time),1000,rng)
                else:
                    h=np.full(len(s.time),mean.ar.sigma2) if name=='constant' else np.exp(context_features(s.target)@variants['context']['beta'])
                    sims=simulate_context(mean.ar,h,rng.standard_normal((1000,len(s.time))),rng.standard_normal((1000,mean.ar.p)))
                sims+=det
                for (lap,phase),mask in masks.items():
                    if not mask.any(): continue
                    key=(lap,phase,name)
                    a=accum.setdefault(key,dict(n=0,real_sum=0.,real_sq=0.,sim_sum=np.zeros(1000),sim_sq=np.zeros(1000)))
                    y=actual[mask]; x=sims[:,mask]
                    a['n']+=len(y); a['real_sum']+=y.sum(); a['real_sq']+=y@y
                    a['sim_sum']+=x.sum(axis=1); a['sim_sq']+=np.sum(x*x,axis=1)
        for (lap,phase,name),a in accum.items():
            n=a['n']
            if n<30: continue
            real=np.sqrt(max(0,(a['real_sq']-a['real_sum']**2/n)/(n-1)))
            sim=np.sqrt(np.maximum(0,(a['sim_sq']-a['sim_sum']**2/n)/(n-1)))
            q=np.quantile(sim,[.1,.5,.9])
            rows.append(dict(split=split,workout_id=wid,lap=lap,phase=phase,model=name,n=n,
                real_sd_w=real,sim_sd_p10_w=q[0],sim_sd_median_w=q[1],sim_sd_p90_w=q[2],
                ratio=q[1]/real if real>0 else np.nan,real_below_p10=real<q[0],
                real_above_p90=real>q[2],sim_over_real_fraction=float(np.mean(sim>real))))
        print(f'Completed {split} {wid}',flush=True)
    d=pd.DataFrame(rows)
    summary=d.groupby(['split','phase','model']).agg(laps=('lap','size'),workouts=('workout_id','nunique'),
        real_sd_median_w=('real_sd_w','median'),sim_sd_median_w=('sim_sd_median_w','median'),
        median_ratio=('ratio','median'),fraction_below_p10=('real_below_p10','mean'),fraction_above_p90=('real_above_p90','mean')).reset_index()
    workout=d.groupby(['split','workout_id','phase','model']).agg(laps=('lap','size'),median_ratio=('ratio','median'),
        fraction_below_p10=('real_below_p10','mean')).reset_index()
    verify_inputs(records)
    for name,df in [('laps',d),('summary',summary),('workouts',workout)]:
        atomic_text(out/f'lap_variability_{name}.csv',df.to_csv(index=False,lineterminator='\n'))
    text='''# Variabilita temporale interna ai lap

Nessun rifit. Train e validation soltanto. Lap reali da lap_index, campioni validi come nella pipeline originale.
Confronto SD campionaria (ddof=1) della potenza reale con la distribuzione della SD di 1000 traiettorie libere.
Non e un confronto con l'ampiezza delle bande fra traiettorie. Include la risposta deterministica in entrambe le serie.
Simulazione per segmento continuo, senza reset ai lap; frammenti validi dello stesso lap combinati sugli stessi timestamp.
Stabile: almeno30s dall'inizio lap, dall'ultimo cambio target e dall'inizio del segmento valido.
Transition: complemento della parte stabile, include inizializzazioni dopo gap; non solo cambi target.
Almeno30 campioni validi per ciascun gruppo; segmenti <=ordine AR esclusi come nel confronto precedente.
Seed SHA256(workout:segment), modelli e inizializzazioni identici al confronto della varianza.
Rapporto=mediana SD simulate / SD reale, poi mediana fra lap; zero SD reale: rapporto non definito.
Aggregato principale a peso uguale per lap; file workouts permette confronto a livello workout.
Percentili10-90 descrivono la variabilita simulativa, non IC sui parametri o test di significativita.
Nessuna correzione per potenza negativa applicata.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.lap_variability

'''
    atomic_text(out/'lap_variability_report.md',text+markdown_table(summary)+'\n')
    atomic_text(out/'lap_variability_manifest.json',encode(dict(paths=1000,
        sources={r['workout_id']:r['sha256'] for r in records},
        hashes={f:sha256(out/f) for f in ['model.json','garch_model.json','variance_models.json','lap_variability.py','garch.py','variance_models.py']}))+'\n')
    print(summary.to_string(index=False),flush=True)


if __name__=='__main__': run()
