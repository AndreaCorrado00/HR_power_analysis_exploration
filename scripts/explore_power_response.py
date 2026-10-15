"""Descriptive exploration only; no dynamic or AR fitting.

Run: .venv/Scripts/python -B scripts/explore_power_response.py
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import warnings

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.signal import welch

LAGS = np.arange(-30, 121)
COLORS = ['#26769A', '#D45A20', '#648447']
BINS = ['5–45 W', '50–95 W', '≥100 W']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def acf(x, maxlag=60):
    x = np.asarray(x, float) - np.mean(x)
    energy = x @ x
    if energy == 0:
        return np.full(maxlag + 1, np.nan)
    return np.array([x[:len(x)-k] @ x[k:] / energy for k in range(maxlag+1)])


def session_curves(meta, values):
    if not len(meta):
        return np.empty((0, values.shape[1]))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        return np.array([np.nanmean(values[meta.workout_id.to_numpy() == w], axis=0)
                         for w in meta.workout_id.unique()])


def band(ax, x, curves, color, label):
    if not len(curves):
        return
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        low, med, high = np.nanpercentile(curves, [10, 50, 90], axis=0)
        mean = np.nanmean(curves, axis=0)
    ax.fill_between(x, low, high, color=color, alpha=.14)
    ax.plot(x, mean, color=color, lw=2, label=label)
    ax.plot(x, med, color=color, lw=1, ls='--')


def style(axes):
    for ax in np.asarray(axes).ravel():
        ax.grid(alpha=.2)
        ax.spines[['top', 'right']].set_visible(False)


def save(fig, output, name, caption):
    fig.text(.02, .012, caption, fontsize=8, color='#465563')
    fig.tight_layout(rect=(0, .045, 1, .96))
    fig.savefig(output / name, dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'data/processed/prescribed_workouts_final')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/power_response_exploration')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = sorted((args.input/'samples').glob('*.csv.gz'))
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    events, trajectories, steady, acfs, psds = [], [], [], [], []
    counts = dict(workouts=len(paths), samples=0, numeric_changes=0,
                  rejected_discontinuous_changes=0, rejected_short_precontext=0)
    for path in paths:
        f = pd.read_csv(path)
        w = path.name.split('.')[0]
        p, q, t = (f[c].to_numpy(float) for c in ['power_w', 'power_target_w', 'elapsed_seconds'])
        sid = f.power_segment_id.to_numpy()
        valid = np.isfinite(p) & (p >= 0) & np.isfinite(q) & ~f.timer_paused.to_numpy(bool) & (sid > 0)
        link = (np.diff(t) == 1) & (np.diff(sid) == 0) & valid[:-1] & valid[1:]
        # Runs split both at target changes and at recording/validity boundaries.
        boundaries = np.r_[0, np.flatnonzero(~link | (q[1:] != q[:-1]))+1, len(f)]
        starts = np.zeros(len(f), int)
        ends = np.zeros(len(f), int)
        for a, b in zip(boundaries[:-1], boundaries[1:]):
            starts[a:b], ends[a:b] = a, b
        changes = np.flatnonzero(np.isfinite(q[:-1]) & np.isfinite(q[1:]) & (q[1:] != q[:-1]))+1
        counts['samples'] += len(f)
        counts['numeric_changes'] += len(changes)
        for i in changes:
            if not link[i-1]:
                counts['rejected_discontinuous_changes'] += 1
                continue
            a, b = starts[i-1], ends[i]
            if i-a < 5:
                counts['rejected_short_precontext'] += 1
                continue
            delta = q[i]-q[i-1]
            response = np.full(len(LAGS), np.nan)
            keep = (i+LAGS >= a) & (i+LAGS < b)
            response[keep] = p[i+LAGS[keep]]-q[i-1]
            amp = abs(delta)
            events.append(dict(workout_id=w, elapsed_s=t[i], delta_w=delta,
                               direction='Salite' if delta > 0 else 'Discese',
                               amplitude_bin=BINS[0 if amp < 50 else 1 if amp < 100 else 2],
                               pre_samples=i-a, post_samples=b-i))
            trajectories.append(response)
        # Age is measured from the actual numeric plateau start, including across gaps.
        target_start = 0
        age = np.zeros(len(f))
        for i in range(len(f)):
            if i == 0 or not np.isfinite(q[i-1]) or q[i] != q[i-1]:
                target_start = i
            age[i] = t[i]-t[target_start]
        for cutoff in [15, 30, 60]:
            for a, b in zip(boundaries[:-1], boundaries[1:]):
                if not valid[a]:
                    continue
                selected = np.arange(a, b)[age[a:b] >= cutoff]
                if len(selected) < 128:
                    continue
                x = p[selected]-q[selected]
                assert np.all(np.diff(t[selected]) == 1)
                assert np.all(q[selected] == q[selected[0]])
                freq, psd = welch(x, fs=1, window='hann', nperseg=128,
                                  noverlap=64, detrend='constant', scaling='density')
                rho = acf(x)
                steady.append(dict(workout_id=w, cutoff_s=cutoff, start_s=t[selected[0]],
                                   n=len(x), target_w=q[a], bias_w=x.mean(), sd_w=x.std(),
                                   zero_fraction=np.mean(p[selected] == 0), acf1=rho[1],
                                   acf5=rho[5], acf10=rho[10], acf30=rho[30]))
                acfs.append(rho)
                psds.append(psd)
    e, s = pd.DataFrame(events), pd.DataFrame(steady)
    y, r, d = np.array(trajectories), np.array(acfs), np.array(psds)
    assert len(e) and len(s), 'Insufficient eligible data'
    norm = y/e.delta_w.to_numpy()[:, None]
    e.to_csv(args.output/'transitions.csv', index=False)
    s.to_csv(args.output/'steady_segments.csv', index=False)
    np.savez_compressed(args.output/'curves.npz', lag_s=LAGS, response_w=y,
                        normalized=norm, acf=r, psd=d, frequency_hz=freq)
    coverage = []
    for direction in ['Salite', 'Discese']:
        mask = e.direction.eq(direction).to_numpy()
        for k, lag in enumerate(LAGS):
            ok = mask & np.isfinite(y[:, k])
            coverage.append(dict(direction=direction, lag_s=lag, transitions=int(ok.sum()),
                                 workouts=int(e.loc[ok, 'workout_id'].nunique())))
    pd.DataFrame(coverage).to_csv(args.output/'coverage.csv', index=False)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), gridspec_kw={'height_ratios':[3, 1]})
    for j, direction in enumerate(['Salite', 'Discese']):
        mask = e.direction.eq(direction).to_numpy()
        # Difference from contemporaneous target: target is always zero in this plot.
        error = y[mask] - (LAGS[None, :] >= 0)*e.loc[mask, 'delta_w'].to_numpy()[:, None]
        ax = axes[0, j]
        ax.plot(LAGS, error.T, color=COLORS[j], alpha=.025, lw=.5)
        band(ax, LAGS, session_curves(e[mask], error), COLORS[j], 'Media tra workout; mediana tratteggiata')
        ax.axhline(0, color='black', ls=':', label='Target'); ax.axvline(0, color='grey', ls=':')
        ax.set(title=f'{direction}: {mask.sum()} transizioni / {e[mask].workout_id.nunique()} workout',
               ylabel='Potenza reale − target [W]', ylim=(-300, 300))
        ax.legend(fontsize=8)
        c = pd.DataFrame(coverage).query('direction == @direction')
        axes[1,j].plot(LAGS,c.transitions,label='Transizioni')
        axes[1,j].plot(LAGS,c.workouts,label='Workout')
        axes[1,j].set(xlabel='Secondi dal cambio target',ylabel='N disponibili'); axes[1,j].legend(fontsize=8)
    style(axes)
    save(fig,args.output,'01_transizioni.png','Bande: P10–P90 delle medie di workout (dispersione, non IC). Tracce individuali; asse limitato a ±300 W solo nella figura.\nTarget inferiti; nessuno smoothing. La composizione cambia con il lag: i cambi successivi interrompono le finestre.')

    fig, axes = plt.subplots(3,2,figsize=(12,11))
    group_summary=[]
    for j,direction in enumerate(['Salite','Discese']):
        for b,color in zip(BINS,COLORS):
            mask = (e.direction.eq(direction) & e.amplitude_bin.eq(b)).to_numpy()
            label=f'{b}: {mask.sum()} eventi, {e[mask].workout_id.nunique()} workout'
            band(axes[0,j],LAGS,session_curves(e[mask],y[mask]),color,label)
            band(axes[1,j],LAGS,session_curves(e[mask],norm[mask]),color,label)
            if b != BINS[0]:
                band(axes[2,j],LAGS,session_curves(e[mask],norm[mask]),color,label)
            group_summary.append(dict(direction=direction,amplitude=b,n=int(mask.sum()),workouts=e[mask].workout_id.nunique()))
        axes[0,j].set(title=direction,ylabel='P − target precedente [W]'); axes[0,j].legend(fontsize=8)
        axes[1,j].step(LAGS,(LAGS>=0).astype(float),where='post',color='black',ls=':',label='Target normalizzato')
        axes[1,j].set(xlabel='Secondi dal cambio target',ylabel='(P − target precedente) / Δtarget')
        axes[1,j].legend(fontsize=8)
        axes[2,j].step(LAGS,(LAGS>=0).astype(float),where='post',color='black',ls=':')
        axes[2,j].set(xlabel='Secondi dal cambio target',ylabel='Risposta normalizzata',title='Dettaglio: salti ≥50 W')
        axes[2,j].legend(fontsize=8)
    style(axes)
    save(fig,args.output,'02_ampiezze.png','Media e mediana (tratteggio) tra workout; P10–P90 delle medie di workout. Classi fisse, non ottimizzate sui risultati.\nIl salto firmato porta anche le discese da 0 a 1. I piccoli salti amplificano rumore e scostamento iniziale.')

    fig,axes=plt.subplots(2,2,figsize=(12,8))
    repeat=[]
    for j,direction in enumerate(['Salite','Discese']):
        # Fixed support and moderate/large jumps for a fairer shape comparison.
        mask=(e.direction.eq(direction)&(e.delta_w.abs()>=50)&(e.pre_samples>=15)&(e.post_samples>=61)).to_numpy()
        local=e[mask].copy(); curves=norm[mask][:,(LAGS>=-15)&(LAGS<=60)]
        enough=local.groupby('workout_id').size(); ids=enough[enough>=3].index
        keep=local.workout_id.isin(ids).to_numpy(); local=local[keep];curves=curves[keep]
        xx=LAGS[(LAGS>=-15)&(LAGS<=60)]
        sc=session_curves(local,curves)
        axes[0,j].plot(xx,sc.T,alpha=.45,lw=.9)
        band(axes[0,j],xx,sc,COLORS[j],'Media; mediana tratteggiata')
        axes[0,j].step(xx,(xx>=0).astype(float),where='post',color='black',ls=':')
        axes[0,j].set(title=f'{direction}: {len(local)} eventi / {len(sc)} workout',ylabel='Risposta normalizzata',xlabel='Secondi dal cambio')
        for wid, c in zip(local.workout_id.unique(),sc):
            z=curves[local.workout_id.to_numpy()==wid]
            within=np.sqrt(np.mean(np.var(z,axis=0)))
            between=np.sqrt(np.mean((c-sc.mean(axis=0))**2))
            repeat.append(dict(workout_id=wid,direction=direction,n=len(z),within_rms=within,between_rms=between))
            axes[1,j].scatter(within,between,color=COLORS[j],s=20)
        axes[1,j].set(xlabel='Dispersione interna RMS [unità di salto]',ylabel='Distanza dalla media globale RMS')
    pd.DataFrame(repeat).to_csv(args.output/'repeatability.csv',index=False)
    style(axes)
    save(fig,args.output,'03_workout.png','Supporto fisso −15/+60 s, |Δtarget| ≥50 W, almeno 3 eventi per workout/direzione. Ogni linea superiore è una media di sessione.\nRMS descrittivi su tutta la finestra; differenze di ampiezza, contesto e livello iniziale restano possibili confondenti.')

    fig,axes=plt.subplots(2,2,figsize=(12,8))
    mainmask=s.cutoff_s.eq(30).to_numpy()
    sr=session_curves(s[mainmask],r[mainmask]); sd=session_curves(s[mainmask],d[mainmask])
    axes[0,0].plot(np.arange(61),sr.T,color=COLORS[0],alpha=.15,lw=.8)
    band(axes[0,0],np.arange(61),sr,COLORS[0],f'30 s: {len(sr)} workout')
    axes[0,0].axhline(0,color='black',lw=.6);axes[0,0].set(xlabel='Lag [s]',ylabel='ACF',title='Residuo centrato: persistenza per workout');axes[0,0].legend()
    axes[0,1].loglog(freq[1:],sd[:,1:].T,color=COLORS[0],alpha=.15,lw=.8)
    band(axes[0,1],freq[1:],sd[:,1:],COLORS[0],'Media; mediana tratteggiata')
    axes[0,1].set(xscale='log',yscale='log',xlabel='Frequenza [Hz]',ylabel='PSD [W²/Hz]',title='Welch: finestre 128 s, risoluzione 1/128 Hz')
    sensitivity=[]
    for cutoff,color in zip([15,30,60],COLORS):
        mask=s.cutoff_s.eq(cutoff).to_numpy(); sc=session_curves(s[mask],r[mask])
        axes[1,0].plot(np.arange(61),np.nanmean(sc,axis=0),color=color,label=f'Taglio {cutoff} s: {len(sc)} workout')
        sensitivity.append(dict(cutoff_s=cutoff,segments=int(mask.sum()),workouts=len(sc),
                                acf1=float(np.nanmean(sc[:,1])),acf10=float(np.nanmean(sc[:,10])),acf30=float(np.nanmean(sc[:,30]))))
    axes[1,0].set(xlabel='Lag [s]',ylabel='ACF media',title='Sensibilità al margine dopo il cambio');axes[1,0].legend(fontsize=8)
    ss=s[mainmask].groupby('workout_id')[['bias_w','sd_w']].mean()
    axes[1,1].scatter(ss.bias_w,ss.sd_w,color=COLORS[0],s=25)
    axes[1,1].set(xlabel='Bias medio dei tratti [W]',ylabel='SD media nei tratti [W]',title='Bias e fluttuazioni separati, per workout')
    style(axes)
    save(fig,args.output,'04_residui.png','Tratti continui ≥128 campioni dopo il margine; target costante non implica potenza stazionaria. Media per tratto, poi per workout.\nACF centrata per tratto, denominatore fisso; PSD Hann, overlap 64 s, centratura per finestra. Nessuna concatenazione o fitting.')
    summary=dict(counts=counts,groups=group_summary,sensitivity=sensitivity,
                 steady30=dict(segments=int(mainmask.sum()),samples=int(s[mainmask].n.sum()),
                               workouts=len(sr),acf1_percentiles=np.nanpercentile(sr[:,1],[10,50,90]).tolist(),
                               acf10_percentiles=np.nanpercentile(sr[:,10],[10,50,90]).tolist(),
                               acf30_percentiles=np.nanpercentile(sr[:,30],[10,50,90]).tolist(),
                               bias_percentiles=np.percentile(ss.bias_w,[10,50,90]).tolist(),
                               sd_percentiles=np.percentile(ss.sd_w,[10,50,90]).tolist()))
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    assert hashes == {str(p.relative_to(ROOT)):sha(p) for p in paths}, 'Input changed'
    manifest=dict(input_sha256=hashes,script_sha256=sha(__file__),python=platform.python_version(),
                  numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,
                  command='.venv/Scripts/python -B scripts/explore_power_response.py',
                  configuration=dict(lags=[-30,120],minimum_pre_samples=5,amplitude_edges_w=[5,50,100],
                                     steady_cutoffs_s=[15,30,60],minimum_steady_samples=128,acf_maxlag=60,
                                     psd_nperseg=128,psd_overlap=64,fit=False,interpolation=False))
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=True))


if __name__=='__main__':
    main()
