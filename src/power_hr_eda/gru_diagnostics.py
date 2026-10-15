"""Descriptive train/validation diagnostics, outside the frozen GRU code package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .gru.data import WindowDataset, eligible, fit_scaler, load_manifest, sha256, write_json


def summarize(samples):
    numeric = ~samples.is_maximal
    residual = (samples.loc[numeric,'power_target_w']-samples.loc[numeric,'power_w']).to_numpy(float)
    result = dict(n=len(samples),numeric_n=int(numeric.sum()),maximal_n=int((~numeric).sum()),
        zero_n=int(samples.power_w.eq(0).sum()),paused_n=int(samples.timer_paused.sum()),
        power_mean_w=float(samples.power_w.mean()),power_variance_w2=float(samples.power_w.var(ddof=0)),
        baseline_n=len(residual),baseline_rmse_w=float(np.sqrt(np.mean(residual**2))) if len(residual) else None,
        baseline_mae_w=float(np.mean(abs(residual))) if len(residual) else None,
        baseline_bias_w=float(np.mean(residual)) if len(residual) else None,
        full_window_n=int(samples.full_window.sum()),abbreviated_window_n=int((~samples.full_window).sum()))
    for threshold in [325,390,488]:
        result[f'power_gt_{threshold}_pct'] = float(samples.power_w.gt(threshold).mean()*100)
    result['maximal_pct'] = float(samples.is_maximal.mean()*100)
    for name,mask in [('full',samples.full_window),('abbreviated',~samples.full_window)]:
        sub=samples.loc[mask]
        result[f'{name}_prescription_dynamic_pct']=float(sub.prescription_dynamic.mean()*100) if len(sub) else None
        for threshold in [10,20,30]:
            result[f'{name}_real_stable_sd_le_{threshold}_pct']=float(sub.window_sd_w.le(threshold).mean()*100) if len(sub) else None
    return result


def analyze_workout(frame, scaler, window):
    dataset=WindowDataset([frame],scaler,window)
    samples=frame.loc[eligible(frame)].reset_index(drop=True).copy()
    assert samples.record_index.tolist()==dataset.metadata.record_index.tolist()
    n=len(samples); index=np.arange(n)
    starts=np.maximum(dataset.starts,index-window+1)
    lengths=index-starts+1
    values=samples.power_w.to_numpy(float)
    sums=np.r_[0.,np.cumsum(values)]
    squares=np.r_[0.,np.cumsum(values**2)]
    variance=np.maximum(0,(squares[index+1]-squares[starts])/lengths-((sums[index+1]-sums[starts])/lengths)**2)
    change=dataset.metadata.transition_age_s.eq(0).to_numpy()
    cumulative=np.cumsum(change)
    # An event is inside a window only if both sides of the change are inside it.
    dynamic=(cumulative-cumulative[starts])>0
    samples['is_maximal']=dataset.metadata.is_maximal
    samples['segment_start_index']=dataset.starts
    samples['window_length']=lengths
    samples['full_window']=lengths==window
    samples['window_variance_w2']=variance
    samples['window_sd_w']=np.sqrt(variance)
    samples['prescription_dynamic']=dynamic
    events=samples.loc[change,['workout_id','record_index','timestamp']].copy()
    events['kind']=dataset.metadata.loc[change,'transition'].to_numpy()
    numeric_change=events.kind.isin(['up','down'])
    deltas=samples.power_target_w.diff().loc[change].to_numpy()
    events['delta_prescribed_w']=np.where(numeric_change,deltas,np.nan)
    # Original laps remain the phase identifiers; gaps make fragments, not new laps.
    fragment_start=(samples.lap_index.ne(samples.lap_index.shift())
                    | pd.Series(dataset.starts).ne(pd.Series(dataset.starts).shift()))
    fragments=[]
    for number,sub in samples.groupby(fragment_start.cumsum(),sort=False):
        fragments.append(dict(workout_id=sub.workout_id.iloc[0],fragment=int(number),
            lap_index=int(sub.lap_index.iloc[0]),is_maximal=bool(sub.is_maximal.iloc[0]),
            first_record=int(sub.record_index.iloc[0]),last_record=int(sub.record_index.iloc[-1]),
            duration_observed_s=len(sub),timer_paused=bool(sub.timer_paused.iloc[0])))
    summary=summarize(samples)
    summary.update(workout_id=frame.workout_id.iloc[0],raw_n=len(frame),excluded_n=len(frame)-n,
                   transitions_n=len(events),transitions_per_observed_hour=len(events)/(n/3600))
    return samples,events,pd.DataFrame(fragments),summary


def ecdf(axis, values, label, color):
    values=np.sort(np.asarray(values,dtype=float))
    values=values[np.isfinite(values)]
    if len(values):
        axis.step(values,np.arange(1,len(values)+1)/len(values),where='post',label=label,color=color)
    axis.set_ylabel('Frazione cumulativa')
    axis.grid(alpha=.2)


def figures(output, samples, events, phases, fragments, workouts, summary, window):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'train':'#2166ac','validation':'#d6604d'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    saved=[]

    def save(fig,name):
        fig.tight_layout()
        fig.savefig(output/name,dpi=160)
        plt.close(fig)
        saved.append(name)

    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    bins=np.linspace(0,float(samples.power_w.max())+1,65)
    for split,color in colors.items():
        values=samples.loc[samples.split.eq(split),'power_w']
        axes[0].hist(values,bins=bins,weights=np.ones(len(values))*100/len(values),histtype='step',lw=1.6,label=split,color=color)
        ecdf(axes[1],values,split,color)
    axes[0].set(xlabel='Potenza reale (W)',ylabel='% campioni per intervallo',title='Distribuzione della potenza reale')
    axes[1].set(xlabel='Potenza reale (W)',title='Distribuzione cumulativa, tutti i campioni validi')
    for axis in axes: axis.legend()
    save(fig,'01_power_distribution.png')

    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for split,color in colors.items():
        sub=samples[samples.split.eq(split)&samples.full_window]
        ecdf(axes[0],sub.window_variance_w2,split,color)
    axes[0].set(xlabel='Varianza locale (W²)',title=f'Varianza nelle finestre complete di {window} s')
    axes[0].set_xscale('symlog',linthresh=1)
    axes[0].legend()
    positions=np.arange(len(workouts))
    axes[1].bar(positions,workouts.power_variance_w2,color=[colors[s] for s in workouts.split])
    axes[1].set_xticks(positions,workouts.workout_id,rotation=90,fontsize=8)
    axes[1].set(ylabel='Varianza per workout (W²)',title='Variabilità interna a ciascun workout')
    save(fig,'02_power_variance.png')

    fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    kinds=['up','down','enter_maximal','leave_maximal']; labels=['Salita','Discesa','Ingresso\nmax','Uscita\nmax']
    for j,(split,color) in enumerate(colors.items()):
        sub=events[events.split.eq(split)];hours=summary.loc[split,'n']/3600
        axes[0].bar(np.arange(4)+(j-.5)*.35,[sub.kind.eq(k).sum()/hours for k in kinds],width=.35,color=color,label=split)
        delta=sub.delta_prescribed_w.dropna()
        ecdf(axes[1],delta,split,color)
        ecdf(axes[2],abs(delta),split,color)
    axes[0].set_xticks(range(4),labels)
    axes[0].set(ylabel='Eventi / ora osservata',title='Frequenza delle transizioni')
    axes[1].set(xlabel='Δ prescrizione (W)',title='Ampiezza con segno: solo transizioni numeriche')
    axes[2].set(xlabel='|Δ prescrizione| (W)',title='Ampiezza assoluta')
    for axis in axes: axis.legend()
    save(fig,'03_transitions.png')

    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for split,color in colors.items():
        for maximal,style in [(False,'-'),(True,'--')]:
            label=f'{split}, '+('massimale' if maximal else 'numerica')
            for axis,table,column in [(axes[0],phases,'duration_s'),(axes[1],fragments,'duration_observed_s')]:
                sub=table[table.split.eq(split)&table.is_maximal.eq(maximal)]
                before=len(axis.lines)
                ecdf(axis,sub[column],label,color)
                if len(axis.lines)>before: axis.lines[-1].set_linestyle(style)
    axes[0].set(xlabel='Durata lap originale (s)',title='Fasi originali: durata registrata, può includere gap')
    axes[1].set(xlabel='Durata frammento osservato (s)',title='Frammenti continui validi, senza attraversare gap')
    for axis in axes:
        axis.set_xscale('log');axis.legend(fontsize=8)
    save(fig,'04_phase_durations.png')

    fig,axes=plt.subplots(1,2,figsize=(13,5))
    groups=[];stable=[];dynamic=[]
    for split in colors:
        for full in [True,False]:
            sub=samples[samples.split.eq(split)&samples.full_window.eq(full)]
            groups.append(f'{split}\n'+('complete' if full else 'abbreviate')+f'\nn={len(sub):,}')
            fraction=float(sub.prescription_dynamic.mean()*100) if len(sub) else 0.
            dynamic.append(fraction);stable.append(100-fraction)
    axes[0].bar(range(4),stable,label='Prescrizione invariata',color='#86bcb6')
    axes[0].bar(range(4),dynamic,bottom=stable,label='Prescrizione variata',color='#f2a541')
    axes[0].set_xticks(range(4),groups,fontsize=8)
    axes[0].set(ylabel='% finestre',ylim=(0,110),title='Stabilità della prescrizione nel contesto')
    axes[0].legend(fontsize=8,loc='upper center')
    for split,color in colors.items():
        for full,style in [(True,'-'),(False,'--')]:
            sub=samples[samples.split.eq(split)&samples.full_window.eq(full)]
            axes[1].plot([10,20,30],[sub.window_sd_w.le(v).mean()*100 for v in [10,20,30]],marker='o',ls=style,color=color,label=f'{split}, '+('complete' if full else 'abbreviate'))
    axes[1].set(xlabel='Soglia deviazione standard potenza reale (W)',ylabel='% finestre stabili',
                ylim=(0,105),xticks=[10,20,30],title='Stabilità reale: SD ≤ soglia; dinamiche = complemento')
    axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
    save(fig,'05_window_stability.png')

    fig,axes=plt.subplots(1,2,figsize=(13,5))
    columns=['maximal_pct','power_gt_325_pct','power_gt_390_pct','power_gt_488_pct']
    for j,(split,color) in enumerate(colors.items()):
        axes[0].bar(np.arange(4)+(j-.5)*.36,[summary.loc[split,c] for c in columns],width=.36,label=split,color=color)
        ecdf(axes[1],samples.loc[samples.split.eq(split)&samples.is_maximal,'power_w'],split,color)
    axes[0].set_xticks(range(4),['Flag massimale','P >325 W','P >390 W','P >488 W'])
    axes[0].set(ylabel='% campioni validi',title='Massimali e alte potenze: categorie sovrapponibili')
    axes[1].set(xlabel='Potenza reale (W)',title='Potenza osservata nei massimali categorici')
    for axis in axes:axis.legend()
    save(fig,'06_maximal_high_power.png')

    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for j,(split,color) in enumerate(colors.items()):
        value=summary.loc[split,'baseline_rmse_w']
        axes[0].bar(j,value,color=color)
        axes[0].text(j,value+1,f'{value:.2f} W',ha='center')
    axes[0].set_xticks([0,1],list(colors))
    axes[0].set(ylabel='RMSE (W)',title='Baseline P prescritta: solo campioni numerici')
    axes[0].set_ylim(0,float(summary.baseline_rmse_w.max())*1.18)
    axes[1].bar(np.arange(len(workouts)),workouts.baseline_rmse_w,color=[colors[s] for s in workouts.split])
    axes[1].set_xticks(np.arange(len(workouts)),workouts.workout_id,rotation=90,fontsize=8)
    axes[1].set(ylabel='RMSE baseline (W)',title='Baseline per workout, massimali esclusi')
    save(fig,'07_baseline_rmse.png')
    return saved


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=Path('reports/gru_v1/w030_gru32/fold_01'))
    parser.add_argument('--dataset',type=Path,default=Path('data/processed/gru_dataset_v1'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    run=json.loads((args.run/'run.json').read_text(encoding='utf-8'))
    manifest=load_manifest(args.dataset)
    if run['manifest_id']!=manifest['manifest_id']:raise ValueError('Dataset differs from training run')
    # Strictly preserve the source interpretation used by the frozen training run.
    data_code=Path(__file__).parent/'gru/data.py'
    if sha256(data_code)!=run['environment']['code']['data.py']:raise ValueError('Training data code changed')
    output=args.output or args.run/'diagnostics'
    if output.exists():raise FileExistsError(f'Use a new output directory: {output}')
    lookup={w['workout_id']:w for w in manifest['workouts']}
    frames={}
    for wid in run['split']['train']+run['split']['validation']:
        f=pd.read_csv(args.dataset/lookup[wid]['path'])
        f['workout_id']=wid;frames[wid]=f
    scaler=fit_scaler([frames[wid] for wid in run['split']['train']])
    if scaler!=run['scaler']:raise ValueError('Scaler mismatch')
    all_samples=[];all_events=[];all_fragments=[];all_workouts=[]
    for split in ['train','validation']:
        for wid in run['split'][split]:
            s,e,f,w=analyze_workout(frames[wid],scaler,run['config']['window'])
            all_samples.append(s.assign(split=split));all_events.append(e.assign(split=split))
            all_fragments.append(f.assign(split=split));all_workouts.append(dict(split=split,**w))
    samples=pd.concat(all_samples,ignore_index=True);events=pd.concat(all_events,ignore_index=True)
    fragments=pd.concat(all_fragments,ignore_index=True);workouts=pd.DataFrame(all_workouts)
    summaries=[]
    for split in ['train','validation']:
        sub=samples[samples.split.eq(split)];row=summarize(sub)
        row['transitions_n']=int(events.split.eq(split).sum())
        row['transitions_per_observed_hour']=row['transitions_n']/(len(sub)/3600)
        row['baseline_macro_rmse_w']=float(workouts.loc[workouts.split.eq(split),'baseline_rmse_w'].mean())
        summaries.append(dict(split=split,**row))
    summary=pd.DataFrame(summaries).set_index('split')
    source=(args.dataset/manifest['source_manifest']['path']).resolve().parent
    phase_path=source/'laps.csv'
    phases=pd.read_csv(phase_path,dtype={'workout_id':str})
    membership={wid:split for split in ['train','validation'] for wid in run['split'][split]}
    phases=phases[phases.workout_id.isin(membership)].copy()
    if not phases.prescription_kind.isin(['power','maximal']).all():
        raise ValueError('Phase diagnostics require numeric or maximal prescriptions')
    phases['split']=phases.workout_id.map(membership)
    phases['is_maximal']=phases.prescription_kind.eq('maximal')
    observed=samples.groupby(['workout_id','lap_index']).size().rename('eligible_samples')
    phases=phases.merge(observed,on=['workout_id','lap_index'],how='left')
    phases['eligible_samples']=phases.eligible_samples.fillna(0).astype(int)
    output.mkdir(parents=True)
    summary.to_csv(output/'split_summary.csv')
    workouts.to_csv(output/'workout_summary.csv',index=False)
    events.to_csv(output/'transitions.csv',index=False)
    fragments.to_csv(output/'phase_fragments.csv',index=False)
    phases[['workout_id','split','lap_index','is_maximal','duration_s','eligible_samples']].to_csv(output/'original_phases.csv',index=False)
    samples[['workout_id','split','record_index','window_length','full_window','window_variance_w2',
             'window_sd_w','prescription_dynamic']].to_csv(output/'window_diagnostics.csv.gz',index=False)
    names=figures(output,samples,events,phases,fragments,workouts,summary,run['config']['window'])
    metadata=dict(run=str(args.run),manifest_id=manifest['manifest_id'],split=run['split'],window_s=run['config']['window'],
                  script_sha256=sha256(Path(__file__)),run_sha256=sha256(args.run/'run.json'),laps_sha256=sha256(phase_path),
                  scaler_verified_train_only=True,stable_sd_thresholds_w=[10,20,30],high_power_thresholds_w=[325,390,488],
                  interpolation=False,variance_ddof=0,output_sha256={p.name:sha256(p) for p in output.iterdir() if p.is_file()})
    lines=[f"# Diagnostiche GRU: fold {run['split']['fold']:02d}, train vs validation",'',
           'Analisi descrittiva dei soli workout del fold. Nessun retraining o uso del test finale.',
           'Prescrizioni inferite dalle tracce reali: la baseline non misura aderenza a un piano indipendente.','',
           '| Indicatore | Train | Validation |','|---|---:|---:|']
    keys=[('Campioni validi','n'),('Varianza potenza (W²)','power_variance_w2'),('Massimali (%)','maximal_pct'),
          ('Transizioni / ora osservata','transitions_per_observed_hour'),('Finestre complete','full_window_n'),
          ('Finestre abbreviate','abbreviated_window_n'),('Finestre complete con cambio prescrizione (%)','full_prescription_dynamic_pct'),
          ('Finestre complete stabili, SD ≤20 W (%)','full_real_stable_sd_le_20_pct'),
          ('Campioni baseline numerica','baseline_n'),('RMSE baseline globale (W)','baseline_rmse_w'),
          ('Media RMSE baseline per workout (W)','baseline_macro_rmse_w')]
    for label,key in keys:lines.append(f'| {label} | {summary.loc["train",key]:.3f} | {summary.loc["validation",key]:.3f} |')
    magnitude=events.assign(amplitude=events.delta_prescribed_w.abs()).groupby('split').amplitude.median()
    duration=phases.groupby(['split','is_maximal']).duration_s.median()
    lines+=['', '## Lettura dei risultati',
        f"- Baseline numerica: train {summary.loc['train','baseline_rmse_w']:.2f} W, validation {summary.loc['validation','baseline_rmse_w']:.2f} W. Il divario train/validation esiste già senza GRU.",
        f"- Ampiezza assoluta mediana delle transizioni numeriche: train {magnitude.get('train',float('nan')):.1f} W, validation {magnitude.get('validation',float('nan')):.1f} W.",
        f"- Durata mediana dei lap numerici: train {duration.get(('train',False),float('nan')):.1f} s, validation {duration.get(('validation',False),float('nan')):.1f} s; lap massimali: {duration.get(('train',True),float('nan')):.1f} / {duration.get(('validation',True),float('nan')):.1f} s.",
        '- Confrontare frequenza dei cambi prescritti e variabilità reale separatamente. Queste statistiche descrittive non attribuiscono causalmente il divario a una singola caratteristica.',
        '', '## Definizioni',
        '- Stessa maschera e stessi confini del training; scaler verificato sui soli workout train.',
        '- Statistiche globali e baseline: ogni campione valido pesa uno; la media per workout è separata.',
        '- Varianza di popolazione (ddof=0), globale, per workout e per finestra. Nessun filtro o interpolazione.',
        f"- Finestre causali da {run['config']['window']} campioni a 1 s; contesto abbreviato ai confini. Finestre sovrapposte, un endpoint per campione.",
        '- Prescrizione dinamica: almeno un cambio interno alla finestra. Il cambio esattamente al bordo sinistro non conta.',
        '- Stabilità reale: SD della potenza ≤20 W; sensibilità a 10/30 W. Una finestra di un campione ha SD=0, perciò le abbreviate sono separate.',
        '- Transizioni: cambi della prescrizione numerica o del flag massimale nello stesso segmento. Ampiezza in W solo per cambi numerici.',
        '- Frequenza eventi: eventi / (campioni validi / 3600). Sono ore osservate, inclusi gli eventuali campioni validi durante pause, non durata totale di calendario.',
        '- Fasi: lap originali con duration_s del dataset; frammenti lap-segmento in campioni ×1 s. Un gap non crea una nuova fase originale.',
        '- Massimale: categoria della prescrizione; alta potenza: soglia sulla misura istantanea. Categorie sovrapponibili, non classificazioni fisiologiche.',
        '- Baseline: predizione uguale alla prescrizione numerica, senza fitting. Massimali esclusi, nessun watt imputato. Non confrontare questa RMSE con la GRU valutata includendo i massimali.',
        '', '## Grafici']
    for name in names:lines += ['',f'![{name}]({name})']
    lines+=['','## Riproduzione','```powershell',
            '.venv/Scripts/python -B scripts/gru_fold_diagnostics.py --run reports/gru_v1/w030_gru32/fold_01 --output reports/gru_v1/w030_gru32/fold_01/diagnostics_rebuilt','```']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    metadata['output_sha256']['report.md']=sha256(output/'report.md')
    write_json(output/'manifest.json',metadata)
    print(summary.to_string());print(f'Output: {output}')


if __name__=='__main__':main()
