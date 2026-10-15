"""Summarize the masking benchmark and compare retention without editing data."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
sys.path.insert(0,str(ROOT/'src'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from power_hr_eda.prescription_gaps import power_gaps,dominant_window


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=ROOT/'reports/power_gap_interpolation_benchmark'
    output=ROOT/'reports/power_gap_interpolation_findings'
    if output.exists(): raise ValueError('Output must be new')
    metadata=json.loads((source/'manifest.json').read_text())
    for name,digest in metadata['output_sha256'].items(): assert sha(source/name)==digest,name
    errors=pd.read_csv(source/'error_summary.csv')
    windows=pd.read_csv(source/'masked_windows.csv.gz')
    gaps=pd.read_csv(source/'real_gaps_with_timer.csv')
    bounded=gaps[gaps.bounded]
    dataset=ROOT/'data/processed/prescribed_workouts_final'
    assert sha(dataset/'manifest.json')==metadata['input_manifest_sha256']
    frames={};segments=[];dominant=[]
    for w in [json.loads(s) for s in (dataset/'workouts.jsonl').read_text().splitlines()]:
        frame=pd.read_csv(dataset/w['sample_file']);frames[w['workout_id']]=frame
        p=frame.power_w.to_numpy();t=frame.elapsed_seconds.to_numpy()
        ix=np.flatnonzero(np.isfinite(p)&(p>=0))
        groups=np.split(ix,np.flatnonzero((np.diff(ix)!=1)|(np.diff(t[ix])!=1))+1)
        for group in groups:
            if not len(group):continue
            part=frame.iloc[group]
            segments.append(dict(workout_id=w['workout_id'],sample_count=len(group),
                valid_prescribed_samples=int(part.prescription_kind.isin(['power','maximal']).sum()),
                start_elapsed_s=float(t[group[0]]),end_elapsed_s=float(t[group[-1]])))
        dominant.append(dict(workout_id=w['workout_id'],**dominant_window(frame,power_gaps(frame),1)))
    segments=pd.DataFrame(segments);dominant=pd.DataFrame(dominant)
    retention=[];total=int(segments.valid_prescribed_samples.sum())
    for minimum in [1,5,15,30,60,120]:
        part=segments[segments.sample_count>=minimum]
        retention.append(dict(minimum_samples=minimum,segments=len(part),workouts=part.workout_id.nunique(),
            valid_prescribed_samples=int(part.valid_prescribed_samples.sum()),
            retained_fraction=float(part.valid_prescribed_samples.sum()/total)))
    numeric=bounded.same_numeric_lap.astype(bool)
    stable=bounded.stable_flanks_20w.fillna(False).astype(bool)
    candidates=bounded[(bounded.timer_pause_fraction==0)&numeric&stable&(bounded.missing_duration_s<=5)]
    summary=dict(bounded_gaps=len(bounded),unbounded_gaps=int((~gaps.bounded).sum()),
        bounded_missing_seconds=float(bounded.missing_duration_s.sum()),
        gaps_overlapping_recorded_timer_pause=int((bounded.timer_pause_fraction>0).sum()),
        timer_paused_missing_seconds=int(bounded.timer_paused_seconds.sum()),
        timer_paused_fraction=float(bounded.timer_paused_seconds.sum()/bounded.missing_duration_s.sum()),
        nonpause_bounded_gaps=int((bounded.timer_pause_fraction==0).sum()),
        nonpause_bounded_missing_seconds=float(bounded.loc[bounded.timer_pause_fraction==0,'missing_duration_s'].sum()),
        nonpause_workouts=int(bounded.loc[bounded.timer_pause_fraction==0,'workout_id'].nunique()),
        stable_nonpause_up_to5s_gaps=len(candidates),stable_nonpause_up_to5s_seconds=float(candidates.missing_duration_s.sum()),
        valid_prescribed_samples=total,segments=len(segments),retention=retention,
        dominant_by_complete_laps_valid_samples=int(dominant.valid_prescribed_samples.sum()),
        dominant_by_complete_laps_retained_fraction=float(dominant.valid_prescribed_samples.sum()/total))
    output.mkdir(parents=True)
    segments.to_csv(output/'observed_segments.csv',index=False)
    dominant.to_csv(output/'dominant_segments.csv',index=False)
    pd.DataFrame(retention).to_csv(output/'retention.csv',index=False)
    candidates.to_csv(output/'interpolation_candidates_diagnostic_only.csv',index=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    hold=errors[errors.split=='holdout']
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for name,label,color in [('all','Tutti i contesti','#247c9a'),
                              ('same_numeric_lap','Stesso lap numerico','#d06625'),
                              ('stable_same_numeric','Stesso lap + estremi stabili*','#7a4795')]:
        data=hold[hold.context==name].sort_values('missing_seconds')
        axes[0].plot(data.missing_seconds,data.linear_mae_w,'o-',label=label,color=color)
        axes[0].fill_between(data.missing_seconds,data.linear_mae_ci_low_w,data.linear_mae_ci_high_w,color=color,alpha=.12)
        axes[1].plot(data.missing_seconds,100*data.variation_retained_fraction,'o-',label=label,color=color)
    base=hold[hold.context=='all']
    axes[0].plot(base.missing_seconds,base.hold_mae_w,'--',color='gray',label='Ultimo valore, tutti i contesti')
    for ax in axes:
        ax.set_xscale('log');ax.set_xticks(metadata['grid_seconds'],labels=metadata['grid_seconds'])
        ax.set_xlabel('Secondi nascosti');ax.grid(alpha=.2)
    axes[0].set_ylabel('MAE [W] - media con uguale peso per allenamento')
    axes[1].set_ylabel('Variazione totale conservata [%]')
    axes[0].legend(fontsize=8);axes[1].set_ylim(0,100)
    fig.suptitle('Interpolazione lineare: verifica su 20 allenamenti successivi\n*Range dei 5 campioni prima + 5 dopo <=20 W; solo 4-36 finestre per durata')
    fig.savefig(output/'error_and_dynamics.png',dpi=170)
    examples=[]
    fig2,axes2=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for i,duration in enumerate([5,60]):
        pool=windows[(windows.split=='holdout')&(windows.missing_seconds==duration)]
        for j,q in enumerate([.5,.9]):
            target=pool.linear_mae_w.quantile(q)
            row=pool.iloc[np.abs(pool.linear_mae_w.to_numpy()-target).argmin()]
            frame=frames[str(row.workout_id)];left=int(row.left_index);right=int(row.right_index)
            part=frame.iloc[left-4:right+5];origin=float(frame.elapsed_seconds.iloc[left])
            ax=axes2[i,j];ax.plot(part.elapsed_seconds-origin,part.power_w,'o-',ms=2,color='#247c9a',label='Potenza vera, nascosta nel test')
            tx=np.arange(duration+2);py=np.linspace(frame.power_w.iloc[left],frame.power_w.iloc[right],duration+2)
            ax.plot(tx,py,'o-',ms=2,color='#d06625',label='Interpolazione')
            ax.axvspan(.5,duration+.5,alpha=.1,color='gray');ax.set_xlabel('Secondi dal campione precedente il buco');ax.set_ylabel('W')
            ax.set_title(f'{duration} s - caso vicino al percentile {int(q*100)} del MAE\n{row.workout_id}, MAE {row.linear_mae_w:.1f} W')
            ax.grid(alpha=.2)
            examples.append(dict(workout_id=str(row.workout_id),missing_seconds=duration,left_index=left,right_index=right,
                                 mae_percentile=q,mae_w=float(row.linear_mae_w)))
    axes2[0,0].legend(fontsize=8)
    fig2.suptitle('Esempi selezionati per percentile di errore, non manualmente')
    fig2.savefig(output/'observed_vs_interpolated.png',dpi=170)
    with PdfPages(output/'interpolation_benchmark.pdf') as pdf:
        pdf.savefig(fig);pdf.savefig(fig2)
    plt.close(fig);plt.close(fig2)
    (output/'example_windows.json').write_text(json.dumps(examples,indent=2)+'\n')
    (output/'manifest.json').write_text(json.dumps(dict(source_manifest_sha256=sha(source/'manifest.json'),
        script_sha256=sha(__file__),output_sha256={p.name:sha(p) for p in output.iterdir()}),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
