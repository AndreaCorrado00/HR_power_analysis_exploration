"""Frozen dynamics + integrated lap intercept + AR(2): reproducible experiment."""
from pathlib import Path
import hashlib
import platform
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from .cli import read_json,resolved_records,atomic_text,encode
from .data import verify_inputs,segment_frame,sha256
from .model import DecompositionModel
from .lap_random_ar import LapAR,prepare,fit,nll
from .garch import interval_metrics
from .diagnostics_analysis import markdown_table


READING='''
## Come interpretare pagina e risultati

- SD offset lap: se zero, il contributo b e inattivo; le curve con/senza offset devono coincidere salvo precisione numerica.
- SD marginale w descrive la dispersione stazionaria delle oscillazioni; SD epsilon descrive i nuovi shock a un passo.
  Sono grandezze diverse e non vanno confuse con la SD campionaria di un lap finito.
- Media libera invariata: E[b]=E[w]=0; non si utilizzano le medie osservate dei lap per spostare la previsione.
- Il grafico inferiore mostra b e w della medesima traiettoria superiore. Non sono stime degli stati reali della validation.
- Bande P10-P90: dispersione fra traiettorie a tempo fisso. Il rapporto SD nel riepilogo lap misura invece la variabilita
  nel tempo dentro ogni lap. Un rapporto mediano maggiore1 indica oscillazioni simulate troppo grandi.
- Coverage attesa80%; un valore maggiore non e automaticamente migliore: controllare ampiezza e interval score.
- Confronto interno lap_random/lap_zero usa gli stessi numeri casuali; differenze inferiori0.01W di score sono trascurabili.
  I riferimenti precedenti hanno seed diversi: piccole differenze di bande possono essere Monte Carlo.
- Profilo likelihood: delta NLL positivo peggiora il fit rispetto all'ottimo; il profilo non e un IC al bordo zero.
- Negative probability e la quota media simulativa di potenze negative, non una correzione applicata al segnale.
- Il risultato non identifica offset rispetto a prescrizioni esterne indipendenti, perche i target qui sono ricostruiti
  dalle medie osservate. Non sostituire i modelli precedenti se non si osserva un miglioramento fuori dal fitting.

'''


def target_audit(out,ids):
    root=out.parent/'data/processed/prescribed_workouts_final'
    manifest=read_json(root/'manifest.json')
    table=pd.read_csv(root/'laps.csv',dtype={'workout_id':str})
    table=table[table.workout_id.isin(ids)].dropna(subset=['mean_power_w','power_target_w'])
    difference=(table.mean_power_w-table.power_target_w).abs()
    audit=dict(power_model=manifest['rules']['power_model'],target_rounding_w=manifest['rules']['target_rounding_w'],
        numeric_laps=len(table),median_absolute_mean_minus_target_w=float(difference.median()),
        fraction_within_2_5w=float((difference<=2.5+1e-9).mean()),
        manifest_sha256=sha256(root/'manifest.json'),laps_sha256=sha256(root/'laps.csv'))
    atomic_text(out/'lap_ar_target_audit.json',encode(audit)+'\n')
    return ('\n## Limite della ricostruzione target\n\n'
        f"Il manifest originale usa {audit['power_model']}, arrotondamento {audit['target_rounding_w']} W. "
        'Alcune ripetute condividono target ricavati dalle medie osservate. '
        f"Nei {len(table)} lap train/validation con target e media numerici (senza soglia di durata), "
        f"il {100*audit['fraction_within_2_5w']:.2f}% ha media osservata entro2.5 W dal target; "
        f"differenza assoluta mediana {difference.median():.3f} W. "
        'La ricostruzione assorbe quindi parte dello scostamento che b_lap dovrebbe rappresentare. '
        'sigma_b=0 non prova assenza di offset rispetto a prescrizioni esterne indipendenti; '
        'il risultato vale condizionatamente ai target ricostruiti. Non si modifica la pipeline target in questo esperimento.\n')


def run():
    out=Path(__file__).parent;base=read_json(out/'model.json');dynamics=DecompositionModel.from_dict(base['decomposition'])
    ids=base['split']['train']+base['split']['validation'];records=[r for r in resolved_records(base) if r['workout_id'] in ids]
    verify_inputs(records)
    protected={f:sha256(out/f) for f in ['model.json','garch_model.json','variance_models.json','scaled_ar_models.json']}
    m=dynamics.ar.intercept/(1-sum(dynamics.ar.coefficients));cache={};training=[];energy=0.;samples=0
    for record in records:
        wid=record['workout_id'];frame=pd.read_csv(record['path']);segments,_=segment_frame(frame,wid,split_at_prescription=False)
        segments=[s for s in segments if len(s.target)>2];indexed=frame.set_index('elapsed_seconds')
        labels=[indexed.loc[s.time,'lap_index'].to_numpy(int) for s in segments]
        residual=[s.residual-dynamics.dynamics.response(s.target) for s in segments]
        prepared=prepare(residual,labels,m);cache[wid]=(frame,segments,labels,residual,prepared)
        if wid in base['split']['train']:
            training.append(prepared);energy+=sum(np.sum((r-m)**2) for r in residual);samples+=sum(map(len,residual))
    models={};statistics={}
    for name,offset in [('lap_zero',False),('lap_random',True)]:
        models[name],statistics[name]=fit(training,m,energy/samples,offset)
        print(name,encode(statistics[name]),flush=True)
    # Profile nuisance parameters at fixed offset SD; do not apply chi-square CI at boundary.
    profile=[];best=models['lap_random'];start=[np.log(best.sigma_e),np.arctanh(best.k1),np.arctanh(best.k2)]
    for b in sorted(set([0.,5.,10.,20.,40.,80.,best.sigma_b])):
        def loss(x):return sum(nll(LapAR(float(np.exp(x[0])),b,*np.tanh(x[1:]),m),p) for p in training)/samples
        opt=minimize(loss,start,method='L-BFGS-B',bounds=[(-5,10),(-4,4),(-4,4)],options={'ftol':1e-12,'gtol':1e-7})
        profile.append(dict(sigma_b=b,converged=bool(opt.success),nll_per_sample=float(opt.fun),
            delta_total_nll=float((opt.fun-statistics['lap_random']['nll'])*samples)))
    metrics=[];laprows=[];phase_rows=[];boundary_rows=[];view={}
    for record in records:
        wid=record['workout_id'];split='train' if wid in base['split']['train'] else 'validation'
        frame,segments,labels,residual,prepared=cache[wid];starts=frame.groupby('lap_index').elapsed_seconds.min()
        payload=dict(t=[],target=[],real=[],mean=[],lap=[],models={});accum={}
        dets=[];phases=[];stable_parts=[]
        for s,laps in zip(segments,labels):
            det=s.target+dynamics.dynamics.response(s.target);dets.append(det)
            age=np.zeros(len(s.time));last=s.time[0];known=np.zeros(len(s.time),bool);seen=False
            for i in range(len(s.time)):
                if i and s.target[i]!=s.target[i-1]:last=s.time[i];seen=True
                age[i]=s.time[i]-last;known[i]=seen
            phases.append(np.where(~known,'start',np.where(age<30,'transition','plateau')))
            stable_parts.append((age>=30)&(s.time-np.array([starts.loc[x] for x in laps])>=30))
            for key,x in [('t',s.time),('target',s.target),('real',s.target+s.residual),('mean',det+m),('lap',laps)]:payload[key].extend(x.tolist())
        for name,model in models.items():
            seed=int.from_bytes(hashlib.sha256(f'lap-ar:{wid}'.encode()).digest()[:8],'little')
            sims,offsets=model.simulate(labels,1000,np.random.default_rng(seed))
            low=[];high=[];negative=[];samples_for_view=[];offset_view=[];noise_view=[]
            for s,laps,det,r,sim,b,stable in zip(segments,labels,dets,residual,sims,offsets,stable_parts):
                lo,hi=np.quantile(sim,[.1,.9],axis=0);low.append(lo);high.append(hi)
                powers=det+sim;negative.append(np.mean(powers<0,axis=0));samples_for_view.extend(powers[0].tolist());offset_view.extend(b[0].tolist());noise_view.extend((sim[0]-m-b[0]).tolist())
                actual=s.target+s.residual
                for lap in np.unique(laps):
                    for phase,mask in [('full',laps==lap),('stable',(laps==lap)&stable),('transition',(laps==lap)&~stable)]:
                        if not mask.any():continue
                        a=accum.setdefault((name,int(lap),phase),dict(n=0,rs=0.,rq=0.,ss=np.zeros(1000),sq=np.zeros(1000),residual_sum=0.,sim_residual_sum=np.zeros(1000)))
                        x=powers[:,mask];y=actual[mask];a['n']+=len(y);a['rs']+=y.sum();a['rq']+=y@y;a['ss']+=x.sum(axis=1);a['sq']+=(x*x).sum(axis=1)
                        a['residual_sum']+=(r[mask]-m).sum();a['sim_residual_sum']+=(sim[:,mask]-m).sum(axis=1)
                changes=np.flatnonzero(np.diff(laps)!=0)+1
                for i in changes:
                    jump=powers[:,i]-powers[:,i-1]
                    boundary_rows.append(dict(split=split,workout_id=wid,model=name,time_s=s.time[i],
                        actual_step=actual[i]-actual[i-1],sim_step_p10=np.quantile(jump,.1),sim_step_p90=np.quantile(jump,.9),
                        sim_step_sd=float(np.std(jump,ddof=1))))
            r=np.concatenate(residual);lo=np.concatenate(low);hi=np.concatenate(high);phase=np.concatenate(phases)
            common=dict(split=split,workout_id=wid,model=name,mode='free')
            metrics.append({**common,**interval_metrics(r,lo,hi),'joint_nll_per_sample':nll(model,prepared)/prepared['n'],'negative_probability':float(np.mean(np.concatenate(negative)))})
            for label in np.unique(phase):
                use=phase==label;phase_rows.append({**common,'phase':label,**interval_metrics(r[use],lo[use],hi[use])})
            det=np.concatenate(dets);payload['models'][name]=dict(low=(det+lo).tolist(),high=(det+hi).tolist(),sample=samples_for_view,
                offset=offset_view,noise=noise_view,negative=np.concatenate(negative).tolist())
        for (name,lap,phase),a in accum.items():
            n=a['n']
            if n<30:continue
            real=np.sqrt(max(0,(a['rq']-a['rs']**2/n)/(n-1)));sd=np.sqrt(np.maximum(0,(a['sq']-a['ss']**2/n)/(n-1)));q=np.quantile(sd,[.1,.5,.9])
            means=np.quantile(a['sim_residual_sum']/n,[.1,.9])
            laprows.append(dict(split=split,workout_id=wid,model=name,lap=lap,phase=phase,n=n,real_sd_w=real,
                sim_sd_p10=q[0],sim_sd_median_w=q[1],sim_sd_p90=q[2],ratio=q[1]/real if real else np.nan,
                real_below_p10=bool(real<q[0]),real_above_p90=bool(real>q[2]),actual_mean_residual=a['residual_sum']/n,
                sim_mean_residual_p10=means[0],sim_mean_residual_p90=means[1]))
        for key in ['t','target','real','mean']:payload[key]=[round(x,3) for x in payload[key]]
        for v in payload['models'].values():
            for key,x in v.items():v[key]=[round(z,6 if key=='negative' else 3) for z in x]
        view.setdefault(split,{})[wid]=payload
        print('Evaluated',split,wid,flush=True)
    met=pd.DataFrame(metrics);laps=pd.DataFrame(laprows);ph=pd.DataFrame(phase_rows)
    summary=met.groupby(['split','mode','model']).agg(workouts=('workout_id','nunique'),coverage80=('coverage80','mean'),width80_w=('width80_w','mean'),
        interval_score80_w=('interval_score80_w','mean'),joint_nll_per_sample=('joint_nll_per_sample','mean'),negative_probability=('negative_probability','mean')).reset_index()
    prior=pd.read_csv(out/'scaled_ar_summary.csv');prior=prior[prior['mode']=='free'].drop(columns=['nll'])
    comparison=pd.concat([prior,summary],ignore_index=True)
    lap_summary=laps.groupby(['split','phase','model']).agg(laps=('lap','size'),workouts=('workout_id','nunique'),real_sd_median_w=('real_sd_w','median'),
        sim_sd_median_w=('sim_sd_median_w','median'),median_ratio=('ratio','median'),fraction_below_p10=('real_below_p10','mean')).reset_index()
    for name,df in [('metrics',met),('summary',comparison),('laps',laps),('lap_summary',lap_summary),('phases',ph),('boundaries',pd.DataFrame(boundary_rows)),('profile',pd.DataFrame(profile))]:
        atomic_text(out/f'lap_ar_{name}.csv',df.to_csv(index=False,lineterminator='\n'))
    atomic_text(out/'lap_ar_models.json',encode(statistics)+'\n')
    atomic_text(out/'lap_ar_results.js','window.LAP_AR_RESULTS = '+encode(dict(splits=view,summary=comparison.astype(object).where(comparison.notna(),None).to_dict('records'),models=statistics,lapSummary=lap_summary.to_dict('records')))+';\n')
    val=met[met.split=='validation'].pivot(index='workout_id',columns='model',values='interval_score80_w');delta=val.lap_random-val.lap_zero
    result=f'Validation: delta interval score random-zero={delta.mean():.4f} W; miglioramenti superiori a0.01 W in {int((delta<-.01).sum())}/{len(delta)} workout. Differenze inferiori a0.01 W considerate trascurabili. '
    result+=f'SD offset stimata={best.sigma_b:.6f} W; SD marginale w={np.sqrt(best.w_variance):.3f} W; SD innovazioni={best.sigma_e:.3f} W. '
    result+='Una stima al bordo zero significa che il fit non richiede un effetto casuale lap aggiuntivo rispetto all’AR.\n'
    protocol='''# Intercetta casuale per lap e AR(2)

P=target+G(delta target)+m+b_lap+w. Risposta ordine4 e m congelati; b_lap iid N(0,sigma_b²), indipendente da w.
w AR(2) stazionario senza intercetta, innovazioni iid N(0,sigma_e²). sigma_e e SD innovazioni, non SD marginale w.
Lap identificati da lap_index dei file, diversi fra workout. Offset condiviso fra frammenti dello stesso lap;
w continuo ai confini lap e indipendentemente reinizializzato ai gap reali. Nessuna interpolazione o clipping della potenza.
Famiglia: modello lineare misto con correlazione AR, Pinheiro e Bates2000; implementazione specializzata gaussiana.
Fit ML marginale ESATTO: integra b, include stato iniziale AR stazionario, usa Woodbury e sufficienti cross-prodotti.
Parametri: sigma_e e sigma_b in W, PACF k1/k2 adimensionali; phi1=k1(1-k2),phi2=k2.
4 partenze; sigma_b² puo essere zero. Media residua m fissa al valore del precedente AR: confronto isolato delle covarianze.
Scala numerica del parametro sigma_b² basata sul train. Likelihood pesata per campione.
Confronto interno lap_zero: stesso fit con sigma_b=0; riferimento equivalente alla scala unica gaussiana precedente.
Train36 workout per fitting; validation12 per predizione marginale libera, senza conoscere offset/medie osservate.
Nessun fit/posterior offset sulla validation. Gli offset mostrati sono estrazioni casuali, NON stime dei lap reali.
1000 traiettorie/workout, seed SHA256('lap-ar:'+workout), stessi numeri casuali per le due varianti.
Media libera=target+G+m, invariata; bande=P10-P90 marginali, non simultanee. NLL qui e congiunta marginale/workout,
non la NLL un passo dei precedenti file: non confrontare colonne con significato diverso.
Metriche aggregate con peso uguale per workout; SD interna lap con stesso protocollo precedente (min30campioni,
stabile dopo30s da lap/cambio target/segmento). Pesi uguali per lap nel riepilogo SD.
Confini lap: salvati salti reali e simulati per verificare discontinuita da offset indipendenti.
Potenza negativa: quota delle simulazioni, senza correzione. Non e nuova evidenza fisiologica.
Profilo likelihood a sigma_b fissato con ristima altri parametri: diagnostica, non IC chi-quadro al bordo.
Incertezza dei parametri non propagata nelle bande; nessun IC Wald per varianza al bordo o confondimento con persistenza.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.lap_random_ar_run

'''
    atomic_text(out/'lap_ar_report.md',protocol+'## Esito\n\n'+result+target_audit(out,ids)+READING+'\n\n'+markdown_table(summary)+'\n\n'+markdown_table(lap_summary)+'\n\n'+markdown_table(pd.DataFrame(profile))+'\n')
    verify_inputs(records);assert all(sha256(out/f)==h for f,h in protected.items())
    atomic_text(out/'lap_ar_manifest.json',encode(dict(protected=protected,sources={r['workout_id']:r['sha256'] for r in records},
        code={f:sha256(out/f) for f in ['lap_random_ar.py','lap_random_ar_run.py']},paths=1000,python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__))+'\n')
    print(summary.to_string(index=False));print(lap_summary.to_string(index=False));print(result)


if __name__=='__main__':run()
