"""Train/validation experiment for Gaussian marginal scales and AR correlation."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from .cli import read_json,resolved_records,atomic_text,encode
from .data import verify_inputs,segment_frame,sha256
from .model import DecompositionModel
from .scaled_ar import fit,transition_phase
from .garch import conditional_metrics,interval_metrics
from .interval_diagnostics import acf_components,ratio
from .variance_comparison import compact_view
from .diagnostics_analysis import markdown_table,arch_lm


def run():
    out=Path(__file__).parent;base=read_json(out/'model.json');mean=DecompositionModel.from_dict(base['decomposition'])
    ids=base['split']['train']+base['split']['validation'];records=[r for r in resolved_records(base) if r['workout_id'] in ids]
    verify_inputs(records); cache={};parts=[];phases=[]
    protected={f:sha256(out/f) for f in ['model.json','garch_model.json','variance_models.json','variance_results.js']}
    for record in records:
        frame=pd.read_csv(record['path']);segments,_=segment_frame(frame,record['workout_id'],split_at_prescription=False)
        segments=[s for s in segments if len(s.target)>2];cache[record['workout_id']]=(frame,segments)
        if record['workout_id'] in base['split']['train']:
            for s in segments:parts.append(s.residual-mean.dynamics.response(s.target));phases.append(transition_phase(s.target))
    m=mean.ar.intercept/(1-sum(mean.ar.coefficients));models={};stats={}
    for name,two in [('constant_scaled',False),('phase_scaled',True)]:
        models[name],stats[name]=fit(parts,phases,m,two)
        print(name,encode(stats[name]),flush=True)
    metrics=[];laprows=[];group_rows=[];diags=[];view={}
    for record in records:
        wid=record['workout_id'];split='train' if wid in base['split']['train'] else 'validation'
        frame,segments=cache[wid];indexed=frame.set_index('elapsed_seconds');starts=frame.groupby('lap_index').elapsed_seconds.min()
        payload=dict(t=[],target=[],real=[],mean=[],models={});accum={};collected={name:[] for name in models}
        for s in segments:
            det=s.target+mean.dynamics.response(s.target);actual=s.target+s.residual;residual=actual-det;phase=transition_phase(s.target)
            laps=indexed.loc[s.time,'lap_index'].to_numpy();age=np.zeros(len(s.time));last=s.time[0]
            for i in range(len(s.time)):
                if i and s.target[i]!=s.target[i-1]:last=s.time[i]
                age[i]=s.time[i]-last
            stable=(age>=30)&(s.time-np.array([starts.loc[x] for x in laps])>=30)
            for key,values in [('t',s.time),('target',s.target),('real',actual),('mean',det+m)]:payload[key].extend(values.tolist())
            seed=int.from_bytes(hashlib.sha256(f'{wid}:{s.segment_id}'.encode()).digest()[:8],'little')
            for name,model in models.items():
                sim=model.simulate(phase,1000,np.random.default_rng(seed));lo,hi=np.quantile(sim,[.1,.9],axis=0)
                mu,h=model.conditional(residual,phase);e=residual[2:]-mu[2:]
                values=payload['models'].setdefault(name,dict(h=[],low=[],high=[],sample=[],conditionalMean=[]))
                for key,x in [('h',model.scales(phase)**2*model.q),('low',det+lo),('high',det+hi),('sample',det+sim[0])]:values[key].extend(x.tolist())
                values['conditionalMean'].extend([None,None]+(det[2:]+mu[2:]).tolist())
                collected[name].append(dict(e=e,h=h[2:],residual=residual,lo=lo,hi=hi,phase=phase))
                powers=sim+det
                for lap in np.unique(laps):
                    for label,mask in [('full',laps==lap),('stable',(laps==lap)&stable),('transition',(laps==lap)&~stable)]:
                        if not mask.any():continue
                        a=accum.setdefault((name,int(lap),label),dict(n=0,rs=0.,rq=0.,ss=np.zeros(1000),sq=np.zeros(1000)))
                        r=actual[mask];x=powers[:,mask];a['n']+=len(r);a['rs']+=r.sum();a['rq']+=r@r;a['ss']+=x.sum(axis=1);a['sq']+=(x*x).sum(axis=1)
        for name,parts in collected.items():
            cat=lambda k:np.concatenate([x[k] for x in parts]);common=dict(split=split,workout_id=wid,model=name)
            metrics.extend([{**common,'mode':'conditional',**conditional_metrics(cat('e'),cat('h'))},{**common,'mode':'free',**interval_metrics(cat('residual'),cat('lo'),cat('hi'))}])
            z=[x['e']/np.sqrt(x['h']) for x in parts];num,den,_=acf_components([x*x for x in z]);payload['models'][name]['acf']=ratio(num,den)[0].tolist()
            for lag in [5,15,30]:diags.append({**common,'lag':lag,**arch_lm(z,lag)})
            for flag,label in [(True,'transition'),(False,'baseline')]:
                mask=cat('phase')==flag
                if mask.sum():group_rows.append({**common,'phase':label,**interval_metrics(cat('residual')[mask],cat('lo')[mask],cat('hi')[mask])})
        for (name,lap,label),a in accum.items():
            n=a['n']
            if n<30:continue
            real=np.sqrt(max(0,(a['rq']-a['rs']**2/n)/(n-1)));sd=np.sqrt(np.maximum(0,(a['sq']-a['ss']**2/n)/(n-1)));q=np.quantile(sd,[.1,.5,.9])
            laprows.append(dict(split=split,workout_id=wid,model=name,lap=lap,phase=label,n=n,real_sd_w=real,sim_sd_median_w=q[1],ratio=q[1]/real if real else np.nan,real_below_p10=bool(real<q[0]),real_above_p90=bool(real>q[2])))
        view.setdefault(split,{})[wid]=payload
        print('Evaluated',split,wid,flush=True)
    met=pd.DataFrame(metrics);laps=pd.DataFrame(laprows);groups=pd.DataFrame(group_rows)
    summary=met.groupby(['split','mode','model'])[['coverage80','width80_w','interval_score80_w','nll']].mean().reset_index()
    comparison=pd.concat([pd.read_csv(out/'variance_summary.csv'),summary],ignore_index=True)
    lap_summary=laps.groupby(['split','phase','model']).agg(laps=('lap','size'),real_sd_median_w=('real_sd_w','median'),sim_sd_median_w=('sim_sd_median_w','median'),median_ratio=('ratio','median'),fraction_below_p10=('real_below_p10','mean')).reset_index()
    for name,df in [('metrics',met),('summary',comparison),('laps',laps),('lap_summary',lap_summary),('phases',groups),('diagnostics',pd.DataFrame(diags))]:atomic_text(out/f'scaled_ar_{name}.csv',df.to_csv(index=False,lineterminator='\n'))
    # Compact display only; metrics retain precision. Existing compact_view handles numerical arrays.
    for workouts in view.values():
        for payload in workouts.values():
            for v in payload['models'].values():
                v['conditionalMean']=[None if x is None else round(x,3) for x in v['conditionalMean']]
    for workouts in view.values():
        for payload in workouts.values():
            for key in ['t','target','real','mean']:payload[key]=[round(x,3) for x in payload[key]]
            for v in payload['models'].values():
                for key in ['h','low','high','sample','acf']:v[key]=[round(x,6 if key=='acf' else 3) for x in v[key]]
    atomic_text(out/'scaled_ar_results.js','window.SCALED_AR_RESULTS = '+encode(dict(splits=view,summary=comparison.fillna('').to_dict('records')))+';\n')
    atomic_text(out/'scaled_ar_models.json',encode(stats)+'\n')
    protocol='''# AR normalizzato e scala marginale del residuo

Struttura nota GLS con covarianza D R D: Pinheiro e Bates2000, https://stat.ethz.ch/R-manual/R-devel/library/nlme/html/gls.html.
Adattamento al progetto: r=m+s(t)u, Var(u)=1, u AR(2) stazionario. Dinamica ordine4 e media residua m congelate.
Due SD marginali (W): primi30s dopo un salto reale oppure resto. Nessun salto inventato a inizio segmento: scala base.
Soglia30s fissata, scale libere e positive; non imposto SD transizione maggiore. Non e GARCH.
AR parametrizzato da correlazioni parziali k1,k2: phi1=k1(1-k2),phi2=k2; varianza innovazione normalizzata q=(1-k1²)(1-k2²).
MLE gaussiana esatta con coppia iniziale stazionaria, indipendenza fra segmenti; peso uguale per campione; tre partenze.
Confronto interno scala unica ristimata con stessa likelihood/normalizzazione; confronti esterni originali congelati.
Nessun IC parametri stimato. Train soltanto per fit, validation per confronto, test escluso.
La previsione libera media resta invariata; la previsione AR a un passo cambia per il rapporto fra scale corrente e passate.
Simulazione1000 traiettorie per segmento, seed SHA256(workout:segment), niente feedback osservato.
Lap e parti stabili: stesso protocollo di lap_variability.py; metriche globali a peso uguale per workout.
Phase baseline include inizi con storia salto ignota; non equivale al plateau60 della diagnostica precedente.
Potenza negativa non corretta. Un miglioramento probabilistico non prova realismo fisiologico.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.scaled_ar_run

'''
    atomic_text(out/'scaled_ar_report.md',protocol+markdown_table(comparison)+'\n\n'+markdown_table(lap_summary)+'\n')
    verify_inputs(records);assert all(sha256(out/f)==h for f,h in protected.items())
    atomic_text(out/'scaled_ar_manifest.json',encode(dict(protected=protected,sources={r['workout_id']:r['sha256'] for r in records},code={f:sha256(out/f) for f in ['scaled_ar.py','scaled_ar_run.py']},paths=1000))+'\n')
    print(summary.to_string(index=False));print(lap_summary.to_string(index=False))


if __name__=='__main__':run()
