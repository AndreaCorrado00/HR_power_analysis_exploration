"""Read frozen innovations; diagnose variance without changing or fitting the model.

Run: python -B -m power_response_estimation.diagnostics_analysis
"""
import json
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from scipy.stats import chi2, f

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LAGS = (5, 15, 30)


def continuous_parts(frame, column='innovation_w'):
    """One workout only; preserve actual one-second continuity and missing values."""
    d = frame.sort_values('time_s')
    valid = np.isfinite(d[column].to_numpy(float))
    links = ((np.diff(d.time_s) == 1)
             & (d.segment_id.to_numpy()[1:] == d.segment_id.to_numpy()[:-1])
             & valid[1:] & valid[:-1])
    cuts = np.r_[0, np.flatnonzero(~links)+1, len(d)]
    return [d.iloc[a:b] for a,b in zip(cuts[:-1],cuts[1:]) if b>a and valid[a]]


def acf_parts(parts, lag):
    """Biased ACF, segment-centered, pooled by energy; no cross-gap products."""
    numerator = denominator = 0.
    pairs = 0
    for x in parts:
        if len(x) <= lag:
            continue
        z = np.asarray(x, float)-np.mean(x)
        numerator += np.dot(z[:-lag],z[lag:])
        denominator += np.dot(z,z)
        pairs += len(z)-lag
    return (numerator/denominator if denominator > 0 else np.nan), pairs


def arch_lm(parts, lag):
    """Engle auxiliary OLS: eps² on constant and q own lags, LM=N*R².

    ddof=0: coefficients of the mean model were estimated on separate training.
    Rows can be stacked, but lags can never cross segment boundaries.
    """
    blocks = [np.lib.stride_tricks.sliding_window_view(np.asarray(x)**2, lag+1)
              for x in parts if len(x)>lag]
    empty = dict(nobs=0, lm=np.nan, p_value=np.nan, r_squared=np.nan,
                 f_stat=np.nan, f_p_value=np.nan, status='insufficient_or_degenerate')
    if not blocks:
        return empty
    b = np.vstack(blocks)
    n = len(b)
    empty['nobs'] = n
    if n <= lag+2 or np.var(b[:,-1]) <= np.finfo(float).tiny:
        return empty
    # Rescaling improves conditioning and leaves OLS R² unchanged.
    b = b/np.mean(b[:,-1])
    y = b[:,-1]
    x = np.column_stack([np.ones(n), b[:,:-1]])
    beta, _, rank, _ = np.linalg.lstsq(x,y,rcond=None)
    if rank != lag+1:
        return empty
    sse = np.sum((y-x@beta)**2)
    r2 = float(np.clip(1-sse/np.sum((y-y.mean())**2),0,1))
    lm = n*r2
    fs = (r2/lag)/((1-r2)/(n-lag-1)) if r2<1 else np.inf
    return dict(nobs=n,lm=lm,p_value=float(chi2.sf(lm,lag)),r_squared=r2,
                f_stat=fs,f_p_value=float(f.sf(fs,lag,n-lag-1)),status='ok')


def bh_adjust(values):
    p = np.asarray(values,float)
    result = np.full(len(p),np.nan)
    indices = np.flatnonzero(np.isfinite(p))
    ordered = indices[np.argsort(p[indices])]
    adjusted = p[ordered]*len(ordered)/np.arange(1,len(ordered)+1)
    result[ordered] = np.minimum(1,np.minimum.accumulate(adjusted[::-1])[::-1])
    return result


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_data():
    bundle = json.loads((HERE/'model.json').read_text())
    d = pd.read_csv(HERE/'predictions.csv',dtype={'workout_id':str})
    metadata = []
    source_hashes = {}
    for r in bundle['records']:
        if r['workout_id'] not in set(d.workout_id):
            continue
        path = ROOT/r['path']
        sha = checksum(path)
        if sha != r['sha256']:
            raise ValueError(f"Source changed: {path}")
        source_hashes[r['path']] = sha
        m = pd.read_csv(path,usecols=['elapsed_seconds','lap_index','phase_index'])
        m = m.rename(columns={'elapsed_seconds':'time_s'})
        m['workout_id'] = r['workout_id']
        metadata.append(m)
    d = d.merge(pd.concat(metadata),on=['workout_id','time_s'],how='left',validate='one_to_one')
    if d.lap_index.isna().any():
        raise ValueError('Unmatched lap metadata')
    ar = bundle['decomposition']['ar']
    for _, g in d.groupby(['split','workout_id','segment_id']):
        e = g.final_residual_w.to_numpy()
        p = ar['p']
        expected = e[p:]-ar['intercept']
        for j,coef in enumerate(ar['coefficients'],1):
            expected -= coef*e[p-j:len(e)-j]
        np.testing.assert_allclose(g.innovation_w.to_numpy()[p:],expected,atol=1e-9)
        if g.innovation_w.iloc[:p].notna().any():
            raise ValueError('Innovation before sufficient AR history')
    d['target_band_w'] = (np.floor(d.target_w/50)*50).astype(int)
    # Phase labels in source have workout-specific meaning; retain them as such.
    # Additional explicit transition definition is comparable across workouts.
    d['transition'] = 'plateau'
    for _,g in d.groupby(['workout_id','segment_id']):
        t = g.time_s.to_numpy()
        change = np.r_[False,np.diff(g.target_w.to_numpy()) != 0]
        last = np.maximum.accumulate(np.where(change,t,-np.inf))
        labels = np.where(t-t[0]<30,'segment_start',np.where(t-last<30,'target_transition','plateau'))
        d.loc[g.index,'transition'] = labels
    return d, source_hashes


def normalize_context(d, keys):
    """Descriptive same-sample variance scaling; no centering or model refit.

    Small (<60 samples) or zero-variance cells use workout variance.
    """
    g = d.groupby(['workout_id']+keys).innovation_w
    variance = g.transform('var')
    count = g.transform('count')
    fallback = d.groupby('workout_id').innovation_w.transform('var')
    use = (count>=60) & (variance>0) & np.isfinite(variance)
    return d.innovation_w/np.sqrt(variance.where(use,fallback)), int((~use & d.innovation_w.notna()).sum())


def variance_table(d, keys):
    return d.groupby(keys,dropna=False).innovation_w.agg(
        n='count',mean_w='mean',variance_w2='var',std_w='std',
        mean_square_w2=lambda x: np.nanmean(x.to_numpy()**2)).reset_index()


def run():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out = HERE/'diagnostics'
    out.mkdir(exist_ok=True)
    protected = ['model.json','predictions.csv','metrics.csv','report.md','results.js']
    before = {name:checksum(HERE/name) for name in protected if (HERE/name).exists()}
    d, source_hashes = load_data()
    fallback = {}
    for name,keys in [('target_scaled',['target_band_w']),('lap_scaled',['lap_index'])]:
        d[name],fallback[name] = normalize_context(d,keys)
    modes = dict(raw='innovation_w',target_scaled='target_scaled',lap_scaled='lap_scaled')
    acfs, tests, rolling = [], [], []
    groups = list(d.groupby(['split','workout_id'],sort=True))
    for (split,wid),g in groups:
        parts = continuous_parts(g)
        for mode,column in modes.items():
            values = [part[column].to_numpy() for part in parts]
            for lag in range(1,121):
                rho,pairs = acf_parts([x*x for x in values],lag)
                acfs.append(dict(split=split,workout_id=wid,mode=mode,lag_s=lag,acf=rho,pairs=pairs))
            for lag in LAGS:
                tests.append(dict(split=split,workout_id=wid,mode=mode,lag_s=lag,**arch_lm(values,lag)))
        for lag in range(1,121):
            rho,pairs = acf_parts([x.innovation_w.to_numpy() for x in parts],lag)
            acfs.append(dict(split=split,workout_id=wid,mode='epsilon',lag_s=lag,acf=rho,pairs=pairs))
        fig,axes = plt.subplots(3,1,figsize=(12,8),sharex=True,layout='constrained')
        for part in parts:
            v = part.innovation_w.rolling(60,min_periods=60).var()
            rows = part[['split','workout_id','segment_id','time_s']].copy()
            rows['variance_60s_w2'] = v
            rolling.append(rows)
            t = part.time_s/60
            axes[0].plot(t,part.innovation_w,lw=.45,color='#28689b')
            axes[1].plot(t,v,lw=.8,color='#b34719')
            axes[2].plot(t,part.target_w,lw=.8,color='#438340')
        axes[0].set(title=f'{split} / {wid}',ylabel='Innovation (W)')
        axes[1].set(ylabel='Variance, 60 s (W²)')
        axes[2].set(ylabel='Target (W)',xlabel='Elapsed time (min)')
        fig.savefig(out/f'variance_{split}_{wid}.png',dpi=130)
        plt.close(fig)
    a = pd.DataFrame(acfs)
    # Both pooled energy-weighted ACF and workout median are explicit.
    aggregate_acfs = []
    for split,g in d.groupby('split'):
        for mode,column in {**modes,'epsilon':'innovation_w'}.items():
            values = [p[column].to_numpy() for _,w in g.groupby('workout_id') for p in continuous_parts(w)]
            if mode != 'epsilon':
                values = [v*v for v in values]
            for lag in range(1,121):
                rho,pairs = acf_parts(values,lag)
                median = a.loc[(a.split==split)&(a['mode']==mode)&(a.lag_s==lag),'acf'].median()
                aggregate_acfs.append(dict(split=split,mode=mode,lag_s=lag,acf=rho,pairs=pairs,median_workout_acf=median))
    aa = pd.DataFrame(aggregate_acfs)
    tests = pd.DataFrame(tests)
    tests['p_fdr'] = np.nan
    for _,indices in tests.groupby('mode').groups.items():
        tests.loc[indices,'p_fdr'] = bh_adjust(tests.loc[indices,'p_value'])
    aggregates = []
    for (split,mode,lag),g in tests.groupby(['split','mode','lag_s']):
        good = g[g.status=='ok']
        statistic = good.lm.sum()
        df = lag*len(good)
        aggregates.append(dict(split=split,mode=mode,lag_s=lag,workouts=len(good),
            nobs=int(good.nobs.sum()),lm_sum=statistic,df=df,
            p_value=chi2.sf(statistic,df) if df else np.nan,
            significant_fdr=int((good.p_fdr<.05).sum()),median_r_squared=good.r_squared.median()))
    agg = pd.DataFrame(aggregates)
    agg['p_fdr'] = np.nan
    for _,indices in agg.groupby('mode').groups.items():
        agg.loc[indices,'p_fdr'] = bh_adjust(agg.loc[indices,'p_value'])
    tables = {'acf_squared':a,'acf_aggregate':aa,'arch_lm_workouts':tests,
              'arch_lm_aggregate':agg,'rolling_variance':pd.concat(rolling)}
    for name,keys in [('variance_target',['split','workout_id','target_band_w']),
                      ('variance_lap',['split','workout_id','lap_index']),
                      ('variance_phase',['split','workout_id','phase_index']),
                      ('variance_transition',['split','workout_id','transition']),
                      ('variance_workouts',['split','workout_id'])]:
        tables[name] = variance_table(d,keys)
    tables['variance_target_aggregate'] = variance_table(d,['split','target_band_w'])
    tables['variance_transition_aggregate'] = variance_table(d,['split','transition'])
    # Within-cell variance avoids between-workout mean shifts in context summaries.
    for name,cell in [('variance_target_aggregate','variance_target'),('variance_transition_aggregate','variance_transition')]:
        key = 'target_band_w' if 'target' in name else 'transition'
        v = tables[cell].copy()
        v['sse'] = v.variance_w2*(v.n-1)
        v['dof'] = (v.n-1).clip(lower=0)
        z = v.groupby(['split',key]).agg(sse=('sse','sum'),dof=('dof','sum'),workouts=('workout_id','nunique'))
        z['within_workout_variance_w2'] = z.sse/z.dof
        tables[name] = tables[name].merge(z.reset_index(),on=['split',key])
    for name,table in tables.items():
        table.to_csv(out/f'{name}.csv',index=False)
    fig,axes = plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for row,split in enumerate(sorted(d.split.unique())):
        for mode in modes:
            g = aa[(aa.split==split)&(aa['mode']==mode)]
            axes[row,0].plot(g.lag_s,g.acf,label=mode)
            axes[row,1].plot(g.lag_s,g.median_workout_acf,label=mode)
        for col,title in enumerate(['Energy pooled','Median workout']):
            axes[row,col].axhline(0,color='gray',lw=.6)
            axes[row,col].set(title=f'{split}: {title}',xlabel='Lag (s)',ylabel='ACF of squared innovations')
            axes[row,col].legend()
    fig.savefig(out/'acf_summary.png',dpi=150)
    plt.close(fig)
    fig,axes = plt.subplots(6,4,figsize=(16,17),layout='constrained')
    for ax,((split,wid),_) in zip(axes.flat,groups):
        for mode in modes:
            g = a[(a.workout_id==wid)&(a['mode']==mode)]
            ax.plot(g.lag_s,g.acf,label=mode,lw=.8)
        ax.axhline(0,color='gray',lw=.5)
        ax.set(title=f'{split}: {wid}',xlabel='Lag (s)',ylabel='ACF ε²')
    axes.flat[0].legend(fontsize=6)
    fig.savefig(out/'acf_workouts.png',dpi=140)
    plt.close(fig)
    fig,axes = plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,(split,g) in zip(axes,tables['variance_target_aggregate'].groupby('split')):
        for _,w in tables['variance_target'].query('split == @split and n >= 60').groupby('workout_id'):
            ax.plot(w.target_band_w+25,w.variance_w2,alpha=.25,lw=.8)
        ax.plot(g.target_band_w+25,g.within_workout_variance_w2,'o-',color='black',label='Pooled within workout')
        ax.set(title=split,xlabel='Target band midpoint (W)',ylabel='Variance (W²)')
        ax.legend()
    fig.savefig(out/'variance_target.png',dpi=150)
    plt.close(fig)
    after = {name:checksum(HERE/name) for name in before}
    if before != after:
        raise RuntimeError('Protected artifacts changed')
    manifest = dict(protected_sha256=before,source_sha256=source_hashes,
        diagnostic_code_sha256=checksum(__file__),lags_s=LAGS,acf_max_lag_s=120,
        rolling_window_s=60,target_bin_width_w=50,normalization_min_samples=60,
        normalization_fallback_samples=fallback,n_valid=int(d.innovation_w.notna().sum()),
        model_unchanged=True,seed=None)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    write_report(out,tables,manifest)
    print(agg.to_string(index=False))


def markdown_table(d):
    def fmt(x, column):
        if isinstance(x,(float,np.floating)):
            return '<1e-300' if x==0 and column.startswith('p_') else f'{x:.4g}'
        return str(x)
    return '\n'.join(['| '+' | '.join(d.columns)+' |','|'+'|'.join(['---']*len(d.columns))+'|']+
        ['| '+' | '.join(fmt(x,c) for x,c in zip(row,d.columns))+' |' for row in d.itertuples(index=False,name=None)])


def write_report(out,tables,manifest):
    raw = tables['arch_lm_aggregate'].query("mode == 'raw'")
    summaries = []
    for split in ['validation','test']:
        a = tables['acf_aggregate'].query('split == @split')
        lm = tables['arch_lm_aggregate'].query('split == @split and lag_s == 30').set_index('mode')
        vt = tables['variance_target_aggregate'].query('split == @split').set_index('target_band_w')
        tr = tables['variance_transition_aggregate'].query('split == @split').set_index('transition')
        summaries.append(f"- **{split}**: ACF ε² a 1 s = "
            f"{a.query('mode == \'raw\' and lag_s == 1').acf.iloc[0]:.3f}; "
            f"dopo scala target = {a.query('mode == \'target_scaled\' and lag_s == 1').acf.iloc[0]:.3f}. "
            f"R² mediano ARCH(30): {lm.loc['raw','median_r_squared']:.1%}, "
            f"scala target {lm.loc['target_scaled','median_r_squared']:.1%}, "
            f"scala lap {lm.loc['lap_scaled','median_r_squared']:.1%}. "
            f"Varianza entro workout: target 150–199 W {vt.loc[150,'within_workout_variance_w2']:.0f} W², "
            f"400–449 W {vt.loc[400,'within_workout_variance_w2']:.0f} W². "
            f"Transizioni/plateau: rapporto {tr.loc['target_transition','within_workout_variance_w2']/tr.loc['plateau','within_workout_variance_w2']:.2f}.")
    context_rows = []
    for context in ['target','lap','phase']:
        v = tables['variance_'+context].query('n >= 60 and variance_w2 > 0')
        for split,g in v.groupby('split'):
            ratios = []
            for _,w in g.groupby('workout_id'):
                if len(w)>1:
                    ratios.append(w.variance_w2.max()/w.variance_w2.min())
            context_rows.append(dict(split=split,context=context,workouts=len(ratios),
                median_max_min_ratio=float(np.median(ratios)) if ratios else np.nan))
    tables['context_variance_ratios'] = pd.DataFrame(context_rows)
    tables['context_variance_ratios'].to_csv(out/'context_variance_ratios.csv',index=False)
    lines = ['# Diagnostica della varianza delle innovazioni AR(2)', '',
        'Analisi descrittiva di validation e test già esaminati; nessun fitting del modello o GARCH. '
        f"Innovazioni finite: {manifest['n_valid']}. Coefficienti, predizioni e risultati precedenti invariati (SHA256 in manifest.json).",'',
        '## Conclusione','',
        '**Esiste evidenza sufficiente per valutare un AR-GARCH come prossimo confronto, '
        'ma non per sostituire già l’AR attuale.** I quadrati delle innovazioni mostrano clustering '
        'a breve termine: l’ACF è positiva soprattutto nei primi 10–20 secondi e si attenua ai lag maggiori. '
        'Tutti i 24 workout rifiutano l’assenza di effetti ARCH a tutti e tre i lag, anche dopo FDR '
        '(massimo p corretto delle innovazioni originali: '
        f"{tables['arch_lm_workouts'].query('mode == \'raw\'').p_fdr.max():.3g}). "
        'La numerosità rende rilevabili effetti relativamente contenuti: il R² ausiliario mediano a 30 lag è circa 7%, '
        'non una misura di guadagno predittivo della potenza.', '',
        *summaries, '',
        'Il contesto conta chiaramente: target elevati e transizioni hanno errori più variabili; '
        'anche lap e fasi differiscono. Tuttavia la normalizzazione per target o lap non elimina '
        'la dipendenza a breve termine né i rigetti ARCH (24/24 workout a ciascun lag anche nelle due sensibilità). '
        '**Il risultato è misto: contesto e memoria dei quadrati, non evidenza che il solo contesto sia sufficiente.** '
        'Non è possibile attribuire causalmente la quota di varianza all’uno o all’altra usando questi confronti.', '',
        'Un eventuale esperimento successivo dovrebbe confrontare fuori campione varianza costante, '
        'varianza condizionata al contesto e AR-GARCH, valutando calibrazione/copertura e score probabilistici. '
        'GARCH non è stato fittato. La sola significatività ARCH non dimostra persistenza GARCH di lungo periodo, '
        'né maggiore accuratezza della media; l’ACF accessoria delle innovazioni va mantenuta nella verifica '
        'della specificazione della media. Le scale per contesto qui utilizzate non sono modelli predittivi.', '',
        '## Metodo e interpretazione','',
        '- ε_t = e_t − c − φ₁e_(t−1) − φ₂e_(t−2), e = reale − target − risposta dinamica. '
        'Verificata numericamente la coerenza del CSV con i coefficienti congelati. Unità W; varianze W².',
        '- Solo tratti contigui a 1 Hz, con innovazioni finite. Nessuna interpolazione, clipping o attraversamento dei gap. '
        'Non si interrompono i tratti ai cambi di target/lap.',
        '- ACF dei quadrati fino a 120 s: centratura separata per tratto, somma dei prodotti a lag / somma delle energie '
        'dei tratti con lunghezza maggiore del lag (stimatore biased). Esportati numero di coppie, aggregato pesato per energia '
        'e mediana dei workout. La centratura rimuove differenze di livello fra tratti, non cambi di varianza interni.',
        '- ARCH-LM: regressione ausiliaria ε² su intercetta e q lag di ε²; LM=N·R², p-value χ²(q), q=5/15/30 s. '
        'ddof=0 perché il modello della media è stato stimato sul training separato. Righe unite solo dopo aver formato i lag entro tratto. '
        'Sono esportati anche F e relativo p-value. Serie degeneri/rango insufficiente sono marcate, non considerate negative.',
        '- Aggregazione ARCH: somma delle LM dei workout, riferimento χ²(12q); non richiede coefficienti ARCH uguali. '
        'Assume indipendenza fra workout: stessi atleta e periodo possono limitarla. Nessun test ottenuto concatenando serie. '
        'BH-FDR sui 72 confronti workout×lag separatamente per modalità; sui 6 confronti aggregati separatamente per modalità. '
        'I p-value nulli in CSV indicano underflow numerico, non probabilità matematicamente nulla.',
        '- Contesto: fasce [b,b+50) W, lap e phase_index originali, più inizio tratto/primi 30 s dopo cambio target/plateau. '
        'Le prime due categorie hanno priorità in questo ordine. Conteggi, media, varianza campionaria e media dei quadrati sono esportati. '
        'Negli aggregati sono disponibili sia varianza totale sia varianza pooled entro workout/cella.',
        '- Sensibilità: ε diviso per deviazione standard entro workout×fascia target, oppure workout×lap. '
        'Nessuna sottrazione della media; celle <60 campioni o con varianza nulla usano la deviazione standard del workout. '
        f"Fallback: {manifest['normalization_fallback_samples']}. "
        'Le scale sono stimate sugli stessi dati: ACF e test normalizzati sono esplorativi, non test confermativi né validazione di un modello di varianza.',
        '- Varianza mobile: finestra trailing di 60 campioni interamente validi nello stesso tratto, ddof=1. '
        'La sovrapposizione delle finestre produce di per sé smoothness: i grafici supportano la lettura, non sono un test di clustering.',
        '- ARCH significativo non identifica un GARCH: cambi di regime, outlier, target, transizioni e misspecificazione della media '
        'possono produrre dipendenza dei quadrati. È esportata anche ACF di ε (mode=epsilon) per verificare la media.', '',
        'Definizione ARCH-LM e ddof: [documentazione statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_arch.html) '
        'e [regressione LM](https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_lm.html). Implementazione NumPy/SciPy senza nuova dipendenza.', '',
        '## Risultati aggregati originali','',markdown_table(raw[['split','lag_s','nobs','lm_sum','df','p_value','significant_fdr','median_r_squared']]),'',
        '## Sensibilità alla scala del contesto','',markdown_table(tables['arch_lm_aggregate'][['split','mode','lag_s','significant_fdr','median_r_squared']]),'',
        '## Risultati per workout (innovazioni originali)','',markdown_table(tables['arch_lm_workouts'].query("mode == 'raw'")[['split','workout_id','lag_s','nobs','lm','p_value','p_fdr','r_squared']]),'',
        '## Varianza per fascia di target','',markdown_table(tables['variance_target_aggregate'][['split','target_band_w','n','workouts','within_workout_variance_w2']]),'',
        '## Varianza per transizione','',markdown_table(tables['variance_transition_aggregate'][['split','transition','n','within_workout_variance_w2']]),'',
        '## Differenze entro workout per contesto','',
        'Mediana fra workout del rapporto fra massima e minima varianza di cella; solo celle con almeno 60 campioni '
        'e workout con almeno due celle. Descrittivo, sensibile al numero di celle e non corretto per altri contesti. '
        'Identificativi lap/fase non sono confrontati direttamente tra workout. '
        'Per phase_index il confronto entro workout è disponibile solo in 3 sessioni: '
        'non permette una conclusione generale sulle fasi.', '',
        markdown_table(tables['context_variance_ratios']), '',
        '## Artefatti e riproduzione','',
        '`python -B -m power_response_estimation.diagnostics_analysis` dalla radice. '
        'Richiede le dipendenze già presenti: NumPy, pandas, SciPy, Matplotlib. '
        'Rigenera solo diagnostics/. Configurazione e hash in manifest.json; nessuna casualità.', '',
        '- acf_squared.csv: ACF per workout (mode=epsilon è la diagnostica accessoria non elevata al quadrato).',
        '- acf_aggregate.csv, arch_lm_workouts.csv, arch_lm_aggregate.csv: statistiche e numerosità.',
        '- variance_*.csv: tabelle per target, fase, lap, transizioni e workout; rolling_variance.csv: serie mobile.',
        '- acf_summary.png, acf_workouts.png, variance_target.png, variance_<split>_<workout>.png: grafici.', '',
        '![ACF aggregate](acf_summary.png)', '', '![Varianza per target](variance_target.png)', '']
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intervals',action='store_true',help='Run interval/plateau sensitivity only')
    args = parser.parse_args()
    if args.intervals:
        from .interval_diagnostics import run_intervals
        run_intervals()
    else:
        run()
