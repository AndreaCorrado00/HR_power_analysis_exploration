"""Paired early/late conditional variance comparison; workout cluster bootstrap."""
from pathlib import Path
import numpy as np
import pandas as pd
from .cli import read_json,resolved_records,atomic_text,encode
from .data import verify_inputs,segment_frame,sha256
from .model import DecompositionModel
from .garch_run import innovations
from .diagnostics_analysis import markdown_table


def variances(weights,counts,sums,squares):
    n=weights@counts
    total=np.einsum('bw,wgt->bgt',weights,sums)
    sq=np.einsum('bw,wgt->bgt',weights,squares)
    valid=n>=2
    sse=np.maximum(0,sq-total**2/np.maximum(n[...,None],1))
    numerator=np.sum(np.where(valid[...,None],sse,0),axis=1)
    dof=np.sum(np.where(valid,n-1,0),axis=1)
    variance=numerator/np.where(dof>0,dof,np.nan)[:,None]
    return np.column_stack([variance[:,:20].mean(axis=1),variance[:,20:].mean(axis=1)])


def run():
    out=Path(__file__).parent; base=read_json(out/'model.json'); model=DecompositionModel.from_dict(base['decomposition'])
    records=[r for r in resolved_records(base) if r['workout_id'] in base['split']['train']+base['split']['validation']]
    verify_inputs(records); events=[]
    for r in records:
        wid=r['workout_id']; split='train' if wid in base['split']['train'] else 'validation'
        segments,_=segment_frame(pd.read_csv(r['path']),wid,split_at_prescription=False)
        for s in segments:
            if len(s.target)<=model.ar.p:continue
            eps=np.r_[np.full(model.ar.p,np.nan),innovations(s,model)]
            changes=np.flatnonzero(np.diff(s.target)!=0)+1
            for k,start in enumerate(changes):
                end=changes[k+1] if k+1<len(changes) else len(s.target)
                if end-start<121 or not np.isfinite(eps[start:start+121]).all():continue
                jump=s.target[start]-s.target[start-1]; size=abs(jump)
                events.append(dict(split=split,workout=wid,event=f'{wid}:{s.segment_id}:{start}',
                    direction='up' if jump>0 else 'down',amplitude='0-25' if size<25 else '25-75' if size<75 else '75-150' if size<150 else '150+',
                    values=np.r_[eps[start:start+20],eps[start+100:start+120]]))
    rows,leaves,catalog=[],[],[]
    for split in ['train','validation']:
        subset=[e for e in events if e['split']==split]
        for mode in ['pooled','stratified','up','down']:
            chosen=[e for e in subset if mode not in ['up','down'] or e['direction']==mode]
            key=lambda e:e['direction']+'/'+e['amplitude'] if mode=='stratified' else 'all'
            groups=list(dict.fromkeys(key(e) for e in chosen)); workouts=list(dict.fromkeys(e['workout'] for e in chosen))
            counts=np.zeros((len(workouts),len(groups))); sums=np.zeros((*counts.shape,40)); squares=np.zeros_like(sums)
            for e in chosen:
                i,j=workouts.index(e['workout']),groups.index(key(e)); counts[i,j]+=1;sums[i,j]+=e['values'];squares[i,j]+=e['values']**2
            for j,g in enumerate(groups):catalog.append(dict(split=split,mode=mode,group=g,events=int(counts[:,j].sum()),workouts=int((counts[:,j]>0).sum())))
            # Fix supported strata before resampling: duplicating one original event
            # must not turn an unidentifiable variance cell into a supported cell.
            keep=counts.sum(axis=0)>=2
            counts,sums,squares=counts[:,keep],sums[:,keep,:],squares[:,keep,:]
            obs=variances(np.ones((1,len(workouts))),counts,sums,squares)[0]
            rng=np.random.default_rng(20261017+['train','validation'].index(split))
            weights=rng.multinomial(len(workouts),np.full(len(workouts),1/len(workouts)),size=10000)
            boot=variances(weights,counts,sums,squares); lograt=np.log(boot[:,0]/boot[:,1]); lograt=lograt[np.isfinite(lograt)]
            logobs=np.log(obs[0]/obs[1]); ci=np.exp(np.quantile(lograt,[.025,.975]))
            # Approximate centered cluster bootstrap null distribution, not exact randomization.
            pvalue=(1+np.sum(lograt-logobs>=logobs))/(len(lograt)+1)
            rows.append(dict(split=split,mode=mode,eligible_events=len(chosen),contributing_events=int(counts.sum()),workouts=len(workouts),early_variance=obs[0],late_variance=obs[1],
                early_sd=np.sqrt(obs[0]),late_sd=np.sqrt(obs[1]),variance_ratio=np.exp(logobs),ci95_low=ci[0],ci95_high=ci[1],
                p_one_sided_approx=pvalue,bootstrap_valid=len(lograt)))
            for i,wid in enumerate(workouts):
                weight=np.ones((1,len(workouts)));weight[0,i]=0
                v=variances(weight,counts,sums,squares)[0]
                leaves.append(dict(split=split,mode=mode,omitted_workout=wid,variance_ratio=v[0]/v[1]))
    result=pd.DataFrame(rows);loo=pd.DataFrame(leaves)
    for name,frame in [('results',result),('leave_one_out',loo),('groups',pd.DataFrame(catalog))]:
        atomic_text(out/f'transition_test_{name}.csv',frame.to_csv(index=False,lineterminator='\n'))
    protocol='''# Varianza iniziale/finale delle innovazioni AR

Modelli congelati; train e validation separati, test escluso. Stessi eventi osservati da tau0 a120s senza nuovi salti/gap.
Finestre0-19 e100-119s. A ogni tau si centra l'errore sulla media FRA eventi, non sulla media temporale della finestra.
Pooled: varianza campionaria fra tutti gli eventi a tau fisso, poi media sui20 tau per finestra.
Stratified: centratura separata per direzione e ampiezza (<25,25-75,75-150,>=150 W), somma SSE/somma gradi di liberta;
celle originarie con meno2 eventi escluse anche da tutti i bootstrap; celle ricampionate con meno2 eventi escluse dalla varianza.
La composizione iniziale/finale e identica. Eventi ammissibili e contribuenti distinti nella tabella.
Up/down: sensibilita descrittiva per direzione. Eventi hanno ugual peso prima della correzione dei gradi di liberta.
10000 bootstrap con ricampionamento di workout interi, mantenendo abbinamento iniziale/finale e tutte le dipendenze interne.
IC95% percentile del rapporto; p unilaterale approssimato da distribuzione bootstrap centrata di log(rapporto),
H0 rapporto=1 contro rapporto>1. Non e un test esatto; pochi workout e code pesanti limitano la calibrazione.
Workout trattati come cluster indipendenti: eventuale dipendenza fra sessioni non modellata.
Leave-one-workout-out per sensibilita. Analisi per direzione secondarie, nessuna correzione multipla: IC e robustezza hanno priorita.
Finestre suggerite dal grafico gia osservato: approfondimento sui dati esistenti, non conferma indipendente.
Un risultato positivo supporta una differenza iniziale/finale, non monotonicita, forma esponenziale o causalita del salto.
Fonte per inferenza cluster: Cameron & Miller2015 doi:10.3368/jhr.50.2.317; statistica specifica adattata a questa analisi.
Riproduzione: .venv/Scripts/python -B -m power_response_estimation.transition_variance_test

## Proposta da testare, non implementata ne fittata

Estensione esplorativa del GARCH con due scale di varianza note dal target:
v(tau)=v_P*[1+kappa*I(0<=tau<T)], h_t=v(tau_t)*g_t,
g_t=(1-alpha-beta)+alpha*[epsilon_(t-1)^2/v(tau_(t-1))]+beta*g_(t-1).
v_P>0 in W², kappa>=0 adimensionale, alpha,beta>=0,alpha+beta<1; E[g]=1 sotto le assunzioni gaussiane.
Innovazione epsilon_t=sqrt(h_t)*z_t con z indipendente N(0,1). Dinamica ordine4 e AR congelati.
Input aggiuntivi solo derivati dal target: eta dall'ultimo salto. Ai gap eta non nota: inizializzazione da dichiarare separatamente,
senza inventare un salto. T=30s candidato fissato dal protocollo precedente, NON stimato o dimostrato dal test iniziale/finale.
Scopo: separare scala plateau e maggiorazione transiente dalla persistenza stocastica g.
Fitting eventuale Gaussian QML solo train; prima verificare varianza plateau e transiente empirica e identifiabilita.
Confronto validation con GARCH targeted (kappa=0) e scala a due livelli senza GARCH (g=1).
Metriche: SD interna lap, coverage/interval score per fase, NLL a un passo; simulazione autonoma senza feedback osservato.
Non imporre esponenziale o asimmetria salita/discesa da questi risultati: analisi direzionali secondarie e campione piccolo.
Questa e una proposta specifica del progetto, non una dinamica fisiologica o un modello ciclistico validato.

'''
    atomic_text(out/'transition_test_report.md',protocol+markdown_table(result)+'\n\n## Sensibilita leave-one-workout-out\n\n'+markdown_table(loo.groupby(['split','mode']).variance_ratio.agg(['min','max']).reset_index())+'\n')
    verify_inputs(records)
    atomic_text(out/'transition_test_manifest.json',encode(dict(seed=20261017,replicates=10000,sources={r['workout_id']:r['sha256'] for r in records},
        hashes={f:sha256(out/f) for f in ['model.json','transition_variance_test.py']}))+'\n')
    print(result.to_string(index=False));print(loo.groupby(['split','mode']).variance_ratio.agg(['min','max']).to_string())


if __name__=='__main__':run()
