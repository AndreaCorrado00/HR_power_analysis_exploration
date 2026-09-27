"""Reproducible post-hoc analysis of saved P1D fits; never refits or writes sources."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import zipfile

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
RUN = '00e47e9c0e2b41b0911e978afd611905'
COLORS = ['#2878a6','#af6447','#639073','#8a6ea4','#b29542']
HR, PRED, POWER, RES = '#c34739', '#257969', '#2878a6', '#625483'
CRITERIA = {
    'observed_flat_range_bpm': 1., 'predicted_flat_range_bpm': 1.,
    'attenuation_ratio': .35, 'min_observed_range_for_attenuation_bpm': 3.,
    'residual_hr_correlation': .90, 'plateau_slope_bpm_per_s': .05,
    'plateau_min_seconds': 5., 'plateau_observed_change_bpm': 3.,
    'equivalent_sse_relative': .01, 'equivalent_sse_absolute': 1e-8,
    'start_agreement_rtol': .05, 'start_agreement_atol': .01,
    'acf_max_lag_samples': 10, 'end_window_fraction': .20,
}


def digest(data): return hashlib.sha256(data).hexdigest()


def simulation(t, p, hr0, theta):
    """Independent step-superposition identity for exact continuous-delay ZOH P1D."""
    K,L,tau=theta
    elapsed=np.maximum(t[:,None]-t[None,1:]-L,0.)
    return hr0 + K*((-np.expm1(-elapsed/tau)) @ np.diff(p))


def acf(e, lag):
    e=e-e.mean(); den=e@e
    return float(e[lag:]@e[:-lag]/den) if den>1e-20 and lag<len(e) else np.nan


def corr(a,b):
    return float(np.corrcoef(a,b)[0,1]) if np.std(a)>1e-10 and np.std(b)>1e-10 else np.nan


def plateau(t,y,threshold):
    moving=np.flatnonzero(np.abs(np.diff(y)/np.diff(t))>threshold)
    if not len(moving): return float(t[-1]),float(t[-1])
    return float(t[moving[0]]),float(t[-1]-t[moving[-1]+1])


def endpoint_flat(t,y,range_limit):
    start=0
    for i in range(1,len(t)):
        if np.ptp(y[:i+1])>range_limit: break
        start=i
    end=len(t)-1
    for i in range(len(t)-2,-1,-1):
        if np.ptp(y[i:])>range_limit: break
        end=i
    return float(t[start]),float(t[-1]-t[end])


def stats(values):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    if not len(a):return {'n':0}
    return dict(n=len(a),mean=float(a.mean()),sd=float(a.std(ddof=1)) if len(a)>1 else None,
                minimum=float(a.min()),q1=float(np.quantile(a,.25)),median=float(np.median(a)),
                q3=float(np.quantile(a,.75)),maximum=float(a.max()))


def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def analyze(manifest_path,out):
    store=manifest_path.parents[1]
    raw=manifest_path.read_bytes();m=json.loads(raw)
    assert m['id']==RUN, 'This report is deliberately specific to the approved 00e47e9c run'
    hashes={str(manifest_path.relative_to(ROOT)):digest(raw)}
    train=m['split']['assignments']['train'];meta={s['id']:s for s in m['dataset']['segments']}
    result_paths=sorted((store/'runs'/m['id']).glob('*.json'))
    assert {p.stem for p in result_paths}==set(train),'Results do not exactly match train'
    fits=sorted([json.loads(p.read_text(encoding='utf-8')) for p in result_paths],key=lambda f:f['filename'])
    assert len(fits)==34, 'The approved run must contain all 34 saved train fits'
    acts=sorted({meta[s]['activity_id'] for s in train});rows=[];starts=[];series=[]
    max_reconstruction=0.;max_sse_diff=0.;seen=set();duplicates=0
    for path in result_paths:hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes())
    for i,f in enumerate(fits,1):
        sid=f['segment_id'];blob=store/'blobs'/meta[sid]['sha256'];data=blob.read_bytes()
        assert digest(data)==meta[sid]['sha256'],'Source hash mismatch'
        hashes[str(blob.relative_to(ROOT))]=digest(data)
        records=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        t,p,y,yh,e=[np.asarray(f['series'][key],float) for key in ('time','power','observed','predicted','residual')]
        raw_series=[np.array([float(r[c]) for r in records]) for c in ('elapsed_seconds',*m['columns'])]
        np.testing.assert_allclose(t,raw_series[0]-raw_series[0][0],atol=1e-10)
        np.testing.assert_array_equal(p,raw_series[1]);np.testing.assert_array_equal(y,raw_series[2])
        np.testing.assert_allclose(e,y-yh,atol=1e-10)
        theta=np.array([f['parameters'][k]['estimate'] for k in ('K','L','tau')]);K,L,tau=theta
        reconstructed=simulation(t,p,y[0],theta)
        max_reconstruction=max(max_reconstruction,float(np.max(np.abs(reconstructed-yh))))
        np.testing.assert_allclose(reconstructed,yh,atol=1e-8,rtol=1e-10)
        n=len(t);T=t[-1];sse=float(e@e);sst=float(np.sum((y-y.mean())**2));sse0=float(np.sum((y-y[0])**2))
        for k,v in {'RMSE':np.sqrt(sse/n),'SSE':sse,'residual_mean':e.mean(),'residual_sd':e.std(ddof=1),'residual_autocorrelation_lag1':acf(e,1)}.items():
            np.testing.assert_allclose(v,f['metrics'][k],atol=1e-9)
        initial,final=plateau(t,yh,CRITERIA['plateau_slope_bpm_per_s'])
        h_initial,h_final=endpoint_flat(t,y,1.)
        head=t<=.2*T;tail=t>=.8*T
        pred_amp=float(np.ptp(yh));obs_amp=float(np.ptp(y));ratio=pred_amp/obs_amp if obs_amp else np.nan
        init_obs=float(np.ptp(y[t<=initial]));final_obs=float(np.ptp(y[t>=T-final]))
        initial_mismatch=initial>=5 and init_obs>=3
        final_mismatch=final>=5 and final_obs>=3
        identical_starts=[];eligible=[];equivalent=[];final_dead=0;initial_dead=0
        for j,st in enumerate(f['starts'],1):
            pred=simulation(t,p,y[0],st['theta']);ss=float(np.sum((y-pred)**2))
            max_sse_diff=max(max_sse_diff,abs(ss-st['SSE']))
            np.testing.assert_allclose(ss,st['SSE'],rtol=1e-8,atol=1e-7)
            dead_initial=st['initial'][1]>=T;dead_final=st['theta'][1]>=T
            initial_dead+=dead_initial;final_dead+=dead_final
            same=bool(np.allclose(st['theta'],theta,rtol=.05,atol=.01))
            equivalent_fit=ss<=sse+max(1e-8,.01*sse)
            if same:identical_starts.append(j)
            if not dead_final:eligible.append(j)
            if equivalent_fit:equivalent.append(j)
            starts.append(dict(segment=f'S{i:02}',start=j,initial_K=st['initial'][0],initial_L=st['initial'][1],initial_tau=st['initial'][2],
                               K=st['theta'][0],L=st['theta'][1],tau=st['theta'][2],SSE=ss,SSE_over_best=ss/sse,
                               success=st['success'],status=st['status'],nfev=st['nfev'],initial_dead=dead_initial,
                               terminal_dead=dead_final,unchanged=np.array_equal(st['initial'],st['theta']),
                               agrees_with_best=same,equivalent_sse=equivalent_fit,predicted_range=float(np.ptp(pred))))
        covariance=np.array(f['uncertainty']['covariance']);se=np.sqrt(np.diag(covariance))
        corr_mat=covariance/np.outer(se,se)
        for k,j in zip(('K','L','tau'),range(3)):
            np.testing.assert_allclose(se[j],f['parameters'][k]['se'],rtol=1e-8)
        row=dict(segment=f'S{i:02}',segment_id=sid,filename=Path(f['filename']).name,
                 activity=Path(meta[sid]['activity_id']).stem,activity_code=f'A{acts.index(meta[sid]["activity_id"])+1}',
                 samples=n,duration_s=float(T),sampling_median_s=float(np.median(np.diff(t))),max_gap_s=float(np.max(np.diff(t))),
                 K=K,L=L,tau=tau,K_over_tau=K/tau,L_over_T=L/T,effective_horizon_over_tau=max(0,T-L)/tau,
                 RMSE=np.sqrt(sse/n),MAE=float(np.mean(np.abs(e))),bias=float(e.mean()),residual_sd=float(e.std(ddof=1)),
                 SSE=sse,R2_centered=1-sse/sst,HR0_RMSE=np.sqrt(sse0/n),skill_HR0=1-sse/sse0,
                 normalized_RMSE=np.sqrt(sse/sst),HR_range=obs_amp,predicted_range=pred_amp,amplitude_ratio=ratio,
                 corr_residual_HR=corr(e,y),corr_residual_time=corr(e,t),
                 residual_slope_bpm_per_s=float(np.polyfit(t,e,1)[0]),
                 ACF1=acf(e,1),ACF5=acf(e,5),ACF10=acf(e,10),durbin_watson=float(np.sum(np.diff(e)**2)/sse),
                 RMSE_initial20=float(np.sqrt(np.mean(e[head]**2))),RMSE_final20=float(np.sqrt(np.mean(e[tail]**2))),
                 bias_initial20=float(e[head].mean()),bias_final20=float(e[tail].mean()),
                 HR_initial20_slope=float(np.polyfit(t[head],y[head],1)[0]),
                 predicted_plateau_initial_s=initial,predicted_plateau_final_s=final,
                 observed_plateau_initial_s=h_initial,observed_plateau_final_s=h_final,
                 observed_range_during_initial_plateau=init_obs,observed_range_during_final_plateau=final_obs,
                 initial_plateau_mismatch=initial_mismatch,final_plateau_mismatch=final_mismatch,
                 observed_flat=obs_amp<=1,predicted_flat=pred_amp<=1,attenuated=ratio<=.35 and obs_amp>=3,
                 residual_tracks_HR=ratio<=.35 and obs_amp>=3 and corr(e,y)>=.9,
                 optimizer_success=f['optimizer']['success'],optimizer_status=f['optimizer']['status'],
                 rank=f['uncertainty']['rank'],jacobian_condition=f['uncertainty']['jacobian_condition'],
                 cov_corr_K_tau=float(corr_mat[0,2]),cov_corr_K_L=float(corr_mat[0,1]),cov_corr_L_tau=float(corr_mat[1,2]),
                 initial_dead_starts=initial_dead,terminal_dead_starts=final_dead,
                 informative_terminal_starts=len(eligible),matching_starts=len(identical_starts),equivalent_sse_starts=len(equivalent),
                 all_informative_starts_agree=all(j in identical_starts for j in eligible),warnings=';'.join(f['warnings']))
        for key in ('K','L','tau'):
            q=f['parameters'][key];row.update({f'{key}_SE':q['se'],f'{key}_CI_low':q['ci95'][0],f'{key}_CI_high':q['ci95'][1],
                                             f'{key}_RSE_pct':q['rse_pct'],f'{key}_bound':q['at_bound']})
        for r in records:
            identity=(meta[sid]['activity_id'],r.get('timestamp'))
            if identity in seen:duplicates+=1
            seen.add(identity)
        rows.append(row);series.append(dict(fit=f,t=t,p=p,y=y,yh=yh,e=e,theta=theta,row=row,acf=np.array([acf(e,k) for k in range(1,11)])))
    activity_rows=[]
    for i,act in enumerate(acts,1):
        subset=[r for r in rows if r['activity_code']==f'A{i}']
        activity_rows.append(dict(activity=f'A{i}',fit_source=Path(act).name,n_segments=len(subset),N=sum(r['samples'] for r in subset),
                                 duration_mean_s=np.mean([r['duration_s'] for r in subset]),
                                 pooled_RMSE=np.sqrt(sum(r['SSE'] for r in subset)/sum(r['samples'] for r in subset)),
                                 mean_segment_RMSE=np.mean([r['RMSE'] for r in subset]),median_RMSE=np.median([r['RMSE'] for r in subset]),
                                 median_K=np.median([r['K'] for r in subset]),median_L=np.median([r['L'] for r in subset]),median_tau=np.median([r['tau'] for r in subset]),
                                 at_bound=sum(any(r[k+'_bound'] for k in ('K','L','tau')) for r in subset)))
    loo=[]
    for act in acts:
        subset=[r for r in rows if r['activity']!=Path(act).stem]
        loo.append(dict(excluded_activity=Path(act).stem,mean_RMSE=np.mean([r['RMSE'] for r in subset]),
                        median_K=np.median([r['K'] for r in subset]),median_L=np.median([r['L'] for r in subset]),median_tau=np.median([r['tau'] for r in subset])))
    for p,hashvalue in m['environment']['code_blobs'].items():
        if p=='backend/models/p1d.py':
            blob=store/'blobs'/hashvalue;assert digest(blob.read_bytes())==hashvalue
            hashes[str(blob.relative_to(ROOT))]=hashvalue
    archive=ROOT/'dataset/dataset_segments_G1_G2.zip'
    archive_bytes=archive.read_bytes()
    assert digest(archive_bytes)==m['dataset']['sources'][0]['sha256']
    hashes[str(archive.relative_to(ROOT))]=digest(archive_bytes)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        grouping_thresholds=json.loads(z.read('metadata/selection.json'))['duration_thresholds_seconds']
    total_sse=sum(r['SSE'] for r in rows);total_n=sum(r['samples'] for r in rows)
    summary=dict(run_id=m['id'],created_at=m['created_at'],dataset_name=m['dataset']['name'],criteria=CRITERIA,
                 n_segments=len(rows),n_activities=len(acts),n_records=total_n,unique_activity_timestamps=len(seen),repeated_records=duplicates,
                 original_grouping_thresholds_seconds=grouping_thresholds,
                 pooled_RMSE=np.sqrt(total_sse/total_n),pooled_MAE=sum(r['MAE']*r['samples'] for r in rows)/total_n,
                 pooled_bias=sum(r['bias']*r['samples'] for r in rows)/total_n,
                 equal_activity_mean_RMSE=np.mean([a['pooled_RMSE'] for a in activity_rows]),
                 aggregate_stats={k:stats([r[k] for r in rows]) for k in ('RMSE','MAE','bias','ACF1','ACF5','ACF10','K','L','tau','K_over_tau','K_RSE_pct','L_RSE_pct','tau_RSE_pct','R2_centered','skill_HR0','duration_s','amplitude_ratio','jacobian_condition','cov_corr_K_tau','effective_horizon_over_tau')},
                 counts={k:sum(bool(r[k]) for r in rows) for k in ('predicted_flat','observed_flat','attenuated','residual_tracks_HR','initial_plateau_mismatch','final_plateau_mismatch','all_informative_starts_agree')},
                 negative_R2=sum(r['R2_centered']<0 for r in rows),durations_above60=sum(r['duration_s']>60 for r in rows),
                 flags=dict(Counter(w for f in fits for w in f['warnings'])),
                 starts=dict(total=len(starts),initial_dead=sum(s['initial_dead'] for s in starts),terminal_dead=sum(s['terminal_dead'] for s in starts),
                             dead_initial_success=sum(s['initial_dead'] and s['success'] for s in starts),
                             dead_initial_unchanged=sum(s['initial_dead'] and s['unchanged'] for s in starts)),
                 ci_negative_lower={k:sum(r[k+'_CI_low']<0 for r in rows) for k in ('K','L','tau')},
                 RSE_above50={k:sum(r[k+'_RSE_pct'] is not None and r[k+'_RSE_pct']>50 for r in rows) for k in ('K','L','tau')},
                 attenuation_sensitivity={str(th):sum(r['amplitude_ratio']<=th for r in rows) for th in (.2,.25,.35,.5)},
                 loo=loo,checks=dict(max_prediction_reconstruction_error=max_reconstruction,max_start_sse_error=max_sse_diff),
                 source_hashes=hashes,script_sha256=digest(Path(__file__).read_bytes()),
                 analysis_versions={p:importlib.metadata.version(p) for p in ('numpy','matplotlib','reportlab','pypdf')})
    summary=clean(summary)
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'segment_metrics.csv',rows);write_csv(out/'multistart_metrics.csv',starts);write_csv(out/'activity_metrics.csv',activity_rows)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return m,series,rows,starts,activity_rows,summary


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.titlesize':11.5,'axes.labelsize':10.5,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#c6cfcd',
                         'grid.alpha':.2,'grid.color':'#9eafaa','figure.facecolor':'white','savefig.facecolor':'white'})


def save(fig,out,name):
    fig.savefig(out/(name+'.png'),dpi=180,bbox_inches='tight');plt.close(fig)
    return name+'.png'


def break_gaps(t,*ys):
    gaps=np.flatnonzero(np.diff(t)>1.5*np.median(np.diff(t)))+1
    return [np.insert(a,gaps,np.nan) for a in (t,*ys)]


def signal_axes(ax,rx,s,annotate=True):
    t,p,y,yh,e=s['t'],s['p'],s['y'],s['yh'],s['e'];r=s['row']
    tt,pp,yy,hh,ee=break_gaps(t,p,y,yh,e)
    ax.plot(tt,yy,color=HR,lw=1.8,label='HR osservata')
    ax.plot(tt,hh,color=PRED,lw=1.8,label='HR prevista')
    ax.axhline(y[0],color='#87918c',lw=.7,ls=':',label='HR(0)')
    pw=ax.twinx();pw.spines['right'].set_visible(True);pw.plot(tt,pp,color=POWER,lw=.9,alpha=.55)
    pw.set_ylabel('Potenza [W]',color=POWER);pw.tick_params(axis='y',colors=POWER,labelsize=9)
    pw.set_ylim(0,max(200,p.max()*1.1));ax.set_ylabel('HR [bpm]');ax.set_xlim(0,t[-1]);ax.grid()
    ymin,ymax=min(y.min(),yh.min()),max(y.max(),yh.max());pad=max(3.,(ymax-ymin)*.15)
    ax.set_ylim(ymin-pad,ymax+pad)
    rx.plot(tt,ee,color=RES,lw=1.5);rx.axhline(0,color='#87918c',lw=.8);rx.set_ylabel('Residuo [bpm]');rx.set_xlabel('Tempo nel segmento [s]');rx.set_xlim(0,t[-1]);rx.grid()
    for a in (ax,rx):a.axvspan(0,min(r['L'],t[-1]),color='#e6ba65',alpha=.14)
    if annotate:
        ax.set_title(f"{r['segment']} | {r['filename'].replace('.csv','')} | T={r['duration_s']:.0f} s",loc='left',fontweight='bold')
        ax.legend(loc='best',fontsize=7,framealpha=.9,ncol=3)
    return pw


def figures(out,m,series,rows,starts,activities,summary):
    style();figdir=out/'figures';figdir.mkdir(exist_ok=True);names=[]
    def arr(key):return np.array([r[key] for r in rows])
    colors=[COLORS[int(r['activity_code'][1:])-1] for r in rows]
    ids=[r['segment'] for r in rows]
    fig,axs=plt.subplots(1,3,figsize=(11.5,3.4),layout='constrained')
    for part,col in zip(('train','val','test'),[PRED,'#d7a454','#889ba8']):
        segs=[s for s in m['dataset']['segments'] if s['id'] in m['split']['assignments'][part]]
        axs[0].bar(part,len(segs),color=col);axs[0].text(part,len(segs)+.4,str(len(segs)),ha='center')
    axs[0].set_title('Ripartizione effettiva dei segmenti');axs[0].set_ylabel('Numero segmenti');axs[0].set_ylim(0,40)
    axs[1].bar([a['activity'] for a in activities],[a['n_segments'] for a in activities],color=COLORS)
    axs[1].set_title('34 segmenti train, 5 attività');axs[1].set_ylabel('Numero segmenti')
    axs[2].scatter(range(1,35),arr('duration_s'),c=colors,s=24);axs[2].axhline(60,color=HR,ls='--',lw=1,label='60 s')
    axs[2].set(xlabel='Indice segmento S01-S34',ylabel='Durata [s]',title='Il nome non impone un filtro <60 s');axs[2].legend(fontsize=8)
    names.append(save(fig,figdir,'01_dataset'))
    fig,axs=plt.subplots(1,3,figsize=(11.5,3.6),layout='constrained')
    for ax,key,unit in zip(axs,('K','L','tau'),('bpm/W','s','s')):
        values=arr(key);ax.boxplot([values],positions=[0],widths=.35,showfliers=False)
        jitter=np.linspace(-.12,.12,len(values));ax.scatter(jitter,values,c=colors,s=22,zorder=3)
        bound=arr(key+'_bound').astype(bool);ax.scatter(jitter[bound],values[bound],facecolors='none',edgecolors=HR,s=85,zorder=4)
        ax.set_xticks([0],['Tutti i segmenti']);ax.set_ylabel(f'{key} [{unit}]');ax.set_title(f'{key}: mediana e dispersione')
        if key!='L':ax.set_yscale('log')
        ax.grid(axis='y')
    names.append(save(fig,figdir,'02_parameters'))
    fig,axs=plt.subplots(1,3,figsize=(11.5,4.2),layout='constrained')
    for ax,key in zip(axs,('K','L','tau')):
        v=arr(key);lo=arr(key+'_CI_low');hi=arr(key+'_CI_high')
        ax.errorbar(range(1,35),v,yerr=[v-lo,hi-v],fmt='none',ecolor='#afbeb7',elinewidth=.9,capsize=1)
        ax.scatter(range(1,35),v,c=colors,s=16,zorder=3);ax.axhline(0,color=HR,lw=.7)
        ax.set_yscale('symlog',linthresh={'K':.1,'L':10,'tau':20}[key]);ax.grid(axis='y')
        ax.set(xlabel='Segmento',ylabel=key+(' [bpm/W]' if key=='K' else ' [s]'),title='CI95 Wald - scala symlog')
    names.append(save(fig,figdir,'03_uncertainty'))
    fig,axs=plt.subplots(1,3,figsize=(11.5,3.7),layout='constrained')
    axs[0].scatter(arr('tau'),arr('K'),c=colors,s=35);axs[0].set(xscale='log',yscale='log',xlabel='tau [s]',ylabel='K [bpm/W]',title='Relazione tra stime K e tau')
    axs[1].scatter(arr('effective_horizon_over_tau'),arr('cov_corr_K_tau'),c=colors,s=35);axs[1].set(xscale='log',xlabel='(T-L)/tau',ylabel='Correlazione locale K-tau',title='Confondibilità nel Jacobiano');axs[1].axhline(.95,color=HR,ls=':',lw=1)
    axs[2].scatter(arr('effective_horizon_over_tau'),arr('K_RSE_pct'),c=colors,s=35);axs[2].set(xscale='log',yscale='log',xlabel='(T-L)/tau',ylabel='RSE(K) [%]',title='Orizzonte informativo e precisione')
    for ax in axs:ax.grid()
    names.append(save(fig,figdir,'04_identifiability'))
    fig,axs=plt.subplots(1,2,figsize=(11.5,5.6),layout='constrained',gridspec_kw={'width_ratios':[1.1,1]})
    ypos=np.arange(34);axs[0].barh(ypos,arr('RMSE'),color=colors,height=.7);axs[0].scatter(arr('HR0_RMSE'),ypos,marker='|',color='#222',s=55,label='Costante HR(0)')
    axs[0].set_yticks(ypos,ids,fontsize=10);axs[0].invert_yaxis();axs[0].set(xlabel='RMSE [bpm]',title='Errore per segmento');axs[0].legend(fontsize=9)
    axs[1].scatter(arr('HR_range'),arr('RMSE'),c=colors,s=38)
    for r in rows:
        if r['R2_centered']<0 or r['segment']=='S34':axs[1].annotate(r['segment'],(r['HR_range'],r['RMSE']),xytext=(3,3),textcoords='offset points',fontsize=8)
    axs[1].set(xlabel='Escursione HR osservata [bpm]',ylabel='RMSE [bpm]',title='Errore assoluto e dinamica osservata');axs[1].grid()
    names.append(save(fig,figdir,'05_fit_quality'))
    fig,axs=plt.subplots(1,3,figsize=(11.5,3.6),layout='constrained')
    for ax,key,title in zip(axs,('K','L','tau'),('K [bpm/W]','L [s]','tau [s]')):
        for j,a in enumerate(activities):
            subset=[r for r in rows if r['activity_code']==a['activity']]
            vals=[r[key] for r in subset];xs=j+np.linspace(-.13,.13,len(vals))
            ax.scatter(xs,vals,color=COLORS[j],s=27);ax.plot([j-.2,j+.2],[np.median(vals)]*2,color='#283a32',lw=1.6)
        ax.set_xticks(range(5),[f"{a['activity']}\nn={a['n_segments']}" for a in activities]);ax.set_ylabel(title);ax.grid(axis='y')
        if key!='L':ax.set_yscale('log')
    names.append(save(fig,figdir,'06_activity'))
    fig,axs=plt.subplots(1,3,figsize=(11.5,4.6),layout='constrained')
    heat=np.array([s['acf'] for s in series]);im=axs[0].imshow(heat,aspect='auto',vmin=-1,vmax=1,cmap='RdBu_r')
    axs[0].set_xticks([0,4,9],[1,5,10]);axs[0].set_yticks(range(34),ids,fontsize=9);axs[0].set(xlabel='Lag [campioni]',title='ACF dei residui');fig.colorbar(im,ax=axs[0],shrink=.6)
    for i,s in enumerate(series):
        cen=s['e']-s['e'].mean();axs[1].scatter(cen[:-1],cen[1:],s=3,color=colors[i],alpha=.3)
    axs[1].set(xlabel='Residuo centrato e(t) [bpm]',ylabel='e(t+1) [bpm]',title='Dipendenza entro segmento');axs[1].grid()
    axs[2].scatter(arr('bias_initial20'),arr('bias_final20'),c=colors,s=30);axs[2].axhline(0,color='#999',lw=.7);axs[2].axvline(0,color='#999',lw=.7)
    axs[2].set(xlabel='Bias primo 20% [bpm]',ylabel='Bias ultimo 20% [bpm]',title='Struttura ai bordi');axs[2].grid()
    names.append(save(fig,figdir,'07_residuals'))
    fig,axs=plt.subplots(1,2,figsize=(11.5,5.2),layout='constrained')
    for i,s in enumerate(series):
        tt,ee=break_gaps(s['t']/s['t'][-1],s['e']);axs[0].plot(tt,ee,alpha=.38,color=colors[i],lw=.9)
    axs[0].axhline(0,color='#999',lw=.8);axs[0].set(xlabel='Tempo / durata del segmento',ylabel='Residuo [bpm]',title='Traiettorie originali, senza smoothing');axs[0].grid()
    axs[1].scatter(arr('amplitude_ratio'),arr('corr_residual_HR'),c=colors,s=32);axs[1].axvline(.35,color=HR,ls='--',lw=1);axs[1].axhline(.9,color=HR,ls='--',lw=1)
    for r in rows:
        if r['attenuated']:axs[1].annotate(r['segment'],(r['amplitude_ratio'],r['corr_residual_HR']),xytext=(4,2),textcoords='offset points',fontsize=7)
    axs[1].set(xlabel='Range HR prevista / range HR osservata',ylabel='corr(residuo, HR osservata)',title='Risposta attenuata e trend non catturato');axs[1].grid()
    names.append(save(fig,figdir,'08_shape'))
    fig,axs=plt.subplots(1,2,figsize=(11.5,5.3),layout='constrained')
    for i,r in enumerate(rows):
        axs[0].barh(i,r['predicted_plateau_initial_s']/r['duration_s'],color=colors[i],height=.65)
        if r['initial_plateau_mismatch']:axs[0].plot(r['predicted_plateau_initial_s']/r['duration_s'],i,'x',color=HR,ms=5)
    axs[0].set_yticks(range(34),ids,fontsize=10);axs[0].invert_yaxis();axs[0].set(xlabel='Durata plateau iniziale / T',title='Plateau iniziale; × = variazione HR >= 3 bpm')
    axs[1].scatter(arr('predicted_plateau_final_s'),arr('observed_plateau_final_s'),c=colors,s=30)
    for r in rows:
        if r['predicted_plateau_final_s']>=5:axs[1].annotate(r['segment'],(r['predicted_plateau_final_s'],r['observed_plateau_final_s']),xytext=(3,3),textcoords='offset points',fontsize=8)
    axs[1].set(xlabel='Plateau finale previsto [s]',ylabel='Plateau finale osservato [s]',title='Definizioni diverse: pendenza vs range');axs[1].grid()
    names.append(save(fig,figdir,'09_plateaus'))
    matrix=np.zeros((34,8));dead=np.zeros((34,8),bool)
    for st in starts:
        i=int(st['segment'][1:])-1;j=st['start']-1;matrix[i,j]=st['SSE_over_best'];dead[i,j]=st['initial_dead']
    fig,axs=plt.subplots(1,2,figsize=(11.5,5.5),layout='constrained')
    im=axs[0].imshow(matrix,aspect='auto',cmap='viridis',norm=LogNorm(vmin=1,vmax=max(2,matrix.max())))
    yi,xi=np.where(dead);axs[0].scatter(xi,yi,marker='x',c='white',s=15,linewidths=.65)
    axs[0].set_xticks(range(8),range(1,9));axs[0].set_yticks(range(34),ids,fontsize=9);axs[0].set(xlabel='Inizializzazione',title='SSE / SSE best; × = L iniziale >= T');fig.colorbar(im,ax=axs[0],shrink=.7)
    axs[1].barh(range(34),arr('informative_terminal_starts'),color='#9bbdb0',label='L finale < T');axs[1].barh(range(34),arr('matching_starts'),color=PRED,label='Parametri concordi col best')
    axs[1].set_yticks(range(34),ids,fontsize=9);axs[1].invert_yaxis();axs[1].set(xlabel='Numero start su 8',title='Copertura effettiva del multistart');axs[1].legend(fontsize=9)
    names.append(save(fig,figdir,'10_multistart'))
    fig,axs=plt.subplots(1,2,figsize=(11.5,3.9),layout='constrained')
    for ax,index in zip(axs,(0,24)):
        s=series[index];r=s['row'];Ls=np.linspace(0,120,361);cost=[np.sum((s['y']-simulation(s['t'],s['p'],s['y'][0],[r['K'],l,r['tau']]))**2)/r['SSE'] for l in Ls]
        ax.plot(Ls,cost,color=PRED);ax.axvline(r['duration_s'],color=HR,ls='--',label='T');ax.axvline(r['L'],color='#555',ls=':',label='L stimato')
        ax.axvspan(r['duration_s'],120,color='#e6ba65',alpha=.15);ax.set_yscale('log');ax.set(xlabel='L [s], K e tau fissati al best',ylabel='SSE / SSE migliore',title=f"{r['segment']}: zona piatta fuori dall'orizzonte");ax.legend(fontsize=8);ax.grid()
    names.append(save(fig,figdir,'11_delay_objective'))
    fig,axs=plt.subplots(1,2,figsize=(11.5,4.1),layout='constrained')
    for ax,index in zip(axs,(0,33)):
        s=series[index];r=s['row'];ks=np.geomspace(max(1e-4,r['K']/15),5,65);taus=np.geomspace(max(.01,r['tau']/15),1800,65)
        cost=np.array([[np.sum((s['y']-simulation(s['t'],s['p'],s['y'][0],[k,r['L'],tau]))**2)/r['SSE'] for k in ks] for tau in taus])
        im=ax.pcolormesh(ks,taus,cost,norm=LogNorm(vmin=1,vmax=min(100,float(cost.max()))),cmap='viridis',shading='auto')
        ax.contour(ks,taus,cost,levels=[1.01,1.1,2],colors=['white','#eab675','#e96d59'],linewidths=.8)
        ax.plot(ks,ks/(r['K']/r['tau']),color='white',ls=':',lw=1,label='K/tau costante')
        ax.plot(r['K'],r['tau'],'x',color='red',ms=8);ax.set(xscale='log',yscale='log',xlabel='K [bpm/W]',ylabel='tau [s]',title=f"{r['segment']}: sezione SSE, L fissato")
        ax.set_ylim(taus[0],taus[-1]);fig.colorbar(im,ax=ax,label='SSE / SSE migliore',shrink=.7)
    names.append(save(fig,figdir,'12_objective_ridges'))
    # Full atlas: one standalone figure per fit, plus grouped pages in the PDF.
    for s in series:
        fig=plt.figure(figsize=(10.5,5.3),layout='constrained');gs=fig.add_gridspec(2,1,height_ratios=[2.4,1.])
        ax=fig.add_subplot(gs[0]);rx=fig.add_subplot(gs[1],sharex=ax);signal_axes(ax,rx,s)
        r=s['row'];fig.supxlabel(f"RMSE {r['RMSE']:.2f} bpm | R² {r['R2_centered']:.2f} | ACF1 {r['ACF1']:.2f} | K {r['K']:.4g} bpm/W | L {r['L']:.2f} s | tau {r['tau']:.2f} s",fontsize=8)
        save(fig,figdir,'fit_'+r['segment'])
    # Two saved alternatives for the clearest attenuation case.
    s=series[24];fig,axs=plt.subplots(2,1,figsize=(11.5,5.3),layout='constrained',gridspec_kw={'height_ratios':[2,1]})
    signal_axes(axs[0],axs[1],s)
    alternatives=[st for st in s['fit']['starts'] if st['theta'][1]>=s['t'][-1]]
    if alternatives:
        yh=simulation(s['t'],s['p'],s['y'][0],alternatives[0]['theta']);axs[0].plot(s['t'],yh,color='#ae813b',ls='--',label='Start bloccato: HR(0)')
        axs[1].plot(s['t'],s['y']-yh,color='#ae813b',ls='--',label='Residuo dello start bloccato');axs[1].legend(fontsize=8)
    axs[0].legend(fontsize=8,ncol=2);names.append(save(fig,figdir,'13_flat_alternative'))
    return names


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'webapp/model_identification_app/storage/runs/20260926T060032Z__Up_to_Down_under60s__p1d__raw__70-10-20__s42__n8-f42__00e47e9c.json')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/model_identification_00e47e9c')
    parser.add_argument('--analysis-only',action='store_true')
    args=parser.parse_args();m,series,rows,starts,acts,summary=analyze(args.manifest.resolve(),args.output)
    images=figures(args.output,m,series,rows,starts,acts,summary)
    if not args.analysis_only:
        from report_model_identification_pdf import build_pdf
        build_pdf(args.output,m,series,rows,starts,acts,summary,images)
    for name,expected in summary['source_hashes'].items():
        assert digest((ROOT/name).read_bytes())==expected, f'Source changed during analysis: {name}'
    print(json.dumps({k:v for k,v in summary.items() if k not in ('source_hashes','analysis_versions')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
