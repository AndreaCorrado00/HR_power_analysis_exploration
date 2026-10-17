"""Frozen-model transition alignment: systematic mean versus dispersion."""
from pathlib import Path
import numpy as np
import pandas as pd
from .cli import read_json,resolved_records,atomic_text,encode
from .data import verify_inputs,segment_frame,sha256
from .model import DecompositionModel
from .garch_run import innovations
from .diagnostics_analysis import markdown_table


def run():
    out=Path(__file__).parent; base=read_json(out/'model.json')
    model=DecompositionModel.from_dict(base['decomposition']); p=model.ar.p
    records=[r for r in resolved_records(base) if r['workout_id'] in base['split']['train']+base['split']['validation']]
    verify_inputs(records); frames=[]
    for record in records:
        wid=record['workout_id']; split='train' if wid in base['split']['train'] else 'validation'
        segments,_=segment_frame(pd.read_csv(record['path']),wid,split_at_prescription=False)
        for s in segments:
            if len(s.target)<=p:continue
            residual=s.residual-model.dynamics.response(s.target)-model.ar.intercept/(1-sum(model.ar.coefficients))
            eps=np.r_[np.full(p,np.nan),innovations(s,model)]
            changes=np.flatnonzero(np.diff(s.target)!=0)+1
            # No fabricated transition at segment starts. Stop each event at next change/gap.
            for k,start in enumerate(changes):
                end=changes[k+1] if k+1<len(changes) else len(s.target)
                jump=s.target[start]-s.target[start-1]; size=abs(jump)
                age=np.arange(end-start)
                bins=np.where(age<30,(age//5*5).astype(str),np.where(age<60,'30-59','60+'))
                frames.append(pd.DataFrame(dict(split=split,workout=wid,event=f'{wid}:{s.segment_id}:{start}',
                    direction='up' if jump>0 else 'down',amplitude='0-25' if size<25 else '25-75' if size<75 else '75-150' if size<150 else '150+',
                    age=age,bin=bins,phase=np.where(age<30,'transition',np.where(age<60,'30-59','plateau60')),
                    residual=residual[start:end],innovation=eps[start:end])))
    d=pd.concat(frames,ignore_index=True).dropna(subset=['innovation'])
    long=d.melt(id_vars=[c for c in d if c not in ['residual','innovation']],value_vars=['residual','innovation'],var_name='signal',value_name='error')
    keys=['split','signal','direction','amplitude','bin']
    profile=long.groupby(keys).agg(n=('error','size'),events=('event','nunique'),workouts=('workout','nunique'),
        mean_w=('error','mean'),sd_w=('error','std'),mse_w2=('error',lambda x:float(np.mean(x*x)))).reset_index()
    wk=long.groupby(['split','workout','signal','phase']).agg(n=('error','size'),mean_w=('error','mean'),
        variance_w2=('error','var'),mse_w2=('error',lambda x:float(np.mean(x*x)))).reset_index()
    summary=wk.groupby(['split','signal','phase']).agg(workouts=('workout','nunique'),n=('n','sum'),
        mean_w=('mean_w','mean'),variance_w2=('variance_w2','mean'),mse_w2=('mse_w2','mean')).reset_index()
    summary['sd_w']=np.sqrt(summary.variance_w2)
    # Descriptive train-cell mean subtraction on validation, not a refit of the model.
    cells=['signal','direction','amplitude','bin']
    means=profile[(profile.split=='train')&(profile.events>=5)&(profile.workouts>=3)][cells+['mean_w']].rename(columns={'mean_w':'train_mean'})
    val=long[long.split=='validation'].merge(means,on=cells,how='left')
    supported=val.dropna(subset=['train_mean']).copy(); supported['centered']=supported.error-supported.train_mean
    compare=[]
    for (signal,phase),g in supported.groupby(['signal','phase']):
        per=[]
        for _,w in g.groupby('workout'):
            per.append([np.mean(w.error**2),np.mean(w.centered**2),np.var(w.error,ddof=1),np.var(w.centered,ddof=1)])
        a=np.mean(per,axis=0)
        compare.append(dict(signal=signal,phase=phase,n=len(g),workouts=g.workout.nunique(),
            available_n=int(((val.signal==signal)&(val.phase==phase)).sum()),raw_mse=a[0],centered_mse=a[1],
            mse_reduction_pct=100*(1-a[1]/a[0]),raw_variance=a[2],centered_variance=a[3]))
    comparison=pd.DataFrame(compare)
    for name,df in [('profiles',profile),('workouts',wk),('summary',summary),('train_centering',comparison)]:
        atomic_text(out/f'transition_{name}.csv',df.to_csv(index=False,lineterminator='\n'))
    atomic_text(out/'transition_profiles.js','window.TRANSITION_PROFILES = '+encode(profile.astype(object).where(profile.notna(),None).to_dict('records'))+';\n')
    protocol='''# Transizioni: errore medio e dispersione

Analisi precedenti: diagnostics/variance_transition_aggregate.csv confrontava media/varianza delle sole innovazioni per fase;
interval_report.md verificava ACF/ARCH nei plateau e dopo normalizzazione entro intervallo.
lap_variability_report.md confrontava SD della potenza totale, non il residuo dopo la dinamica.
Qui si aggiungono train, residuo della dinamica e allineamento per direzione/ampiezza/tempo dal salto.

Modelli congelati, nessun rifit e nessuna simulazione nuova; test escluso.
Residuo = reale-target-risposta ordine4-media stazionaria AR; innovazione = errore AR a un passo.
Ogni cambio target e un evento; nessun evento inventato a inizio segmento. Censura al cambio successivo o gap.
Classi salto assoluto: <25,25-75,75-150,>=150 W. Bin temporali 0-4,5-9,...25-29,30-59,>=60s.
Plateau60 qui include solo campioni almeno60s dopo un salto noto: diverso dal plateau storico >=30s.
Profili pesati per campione, con numerosita eventi/workout. Riepilogo per fase a peso uguale per workout.
SD e dispersione attorno alla media del gruppo, non RMSE attorno a zero.
Controllo fuori dal train: sottrazione diagnostica della media train della stessa cella direzione/ampiezza/tempo;
minimo5 eventi e3 workout train, nessuna stima sulla validation. Confronto sugli stessi campioni supportati.
La sottrazione non cambia il modello: misura quanto una semplice forma sistematica trasferibile spiega gli errori.
Nessun p-value iid o IC sui secondi correlati. Celle sparse, durata e livelli target possono confondere i confronti.
Un mancato miglioramento non dimostra l'assenza di ogni errore sistematico possibile.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.transition_diagnostics

'''
    atomic_text(out/'transition_report.md',protocol+'\n'+markdown_table(summary)+'\n\n## Sottrazione diagnostica media train sulla validation\n\n'+markdown_table(comparison)+'\n')
    atomic_text(out/'transition_manifest.json',encode(dict(sources={r['workout_id']:r['sha256'] for r in records},
        hashes={f:sha256(out/f) for f in ['model.json','transition_diagnostics.py']}))+'\n')
    verify_inputs(records)
    print(summary.to_string(index=False)); print(comparison.to_string(index=False))


if __name__=='__main__':run()
