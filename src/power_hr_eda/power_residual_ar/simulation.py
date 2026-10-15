"""Free Gaussian AR trajectories. No observed residual enters generation."""
import hashlib

import numpy as np
import pandas as pd

from .validation import error_metrics


def stationary_state(model):
    """Exact Gaussian state moments from the discrete Lyapunov equation."""
    phi = np.asarray(model.coefficients, float)
    if (len(phi) != model.p or model.p < 1 or not np.isfinite(phi).all()
            or not np.isfinite(model.intercept) or not np.isfinite(model.sigma2)
            or model.sigma2 <= 0 or not model.stable):
        raise ValueError('Stationary simulation needs a stable AR with positive finite variance')
    transition = np.zeros((model.p, model.p))
    transition[0] = phi
    transition[1:, :-1] = np.eye(model.p-1)
    noise = np.zeros_like(transition)
    noise[0,0] = model.sigma2
    covariance = np.linalg.solve(np.eye(model.p**2)-np.kron(transition, transition),
                                 noise.ravel(order='F')).reshape((model.p,model.p), order='F')
    covariance = (covariance+covariance.T)/2
    mean = np.full(model.p, model.intercept/(1-phi.sum()))
    return mean, covariance


def simulate_residual(model, n, paths, rng):
    """All n samples simulated, including the start; no teacher forcing."""
    if n < 1 or paths < 1:
        raise ValueError('Need positive sample and trajectory counts')
    mean, covariance = stationary_state(model)
    history = rng.multivariate_normal(mean, covariance, size=paths, check_valid='raise')
    innovations = rng.normal(0, np.sqrt(model.sigma2), size=(paths,n))
    values = np.empty((paths,n))
    phi = np.asarray(model.coefficients)
    for t in range(n):
        values[:,t] = model.intercept+history@phi+innovations[:,t]
        history[:,1:] = history[:,:-1].copy()
        history[:,0] = values[:,t]
    return values


def simulate_workout(model, segments, seed=42, paths=100):
    if not segments or len({s.workout_id for s in segments}) != 1 or seed < 0:
        raise ValueError('Need one nonempty workout and a nonnegative seed')
    # Stable across input ordering, processes, and Python hash randomization.
    digest = hashlib.sha256(segments[0].workout_id.encode()).digest()
    words = [int.from_bytes(digest[i:i+4], 'little') for i in range(0,16,4)]
    rng = np.random.default_rng(np.random.SeedSequence([seed, *words]))
    return [simulate_residual(model, len(s.target), paths, rng) for s in segments]


def pooled_acf(parts, lag):
    """Biased ACF pooled by within-segment energy; never cross a real gap."""
    numerator, denominator = None, None
    for part in parts:
        x = np.atleast_2d(part)
        if x.shape[1] <= lag:
            continue
        x = x-x.mean(axis=1, keepdims=True)
        num = np.sum(x[:,:-lag]*x[:,lag:], axis=1)
        den = np.sum(x*x, axis=1)
        numerator = num if numerator is None else numerator+num
        denominator = den if denominator is None else denominator+den
    if numerator is None:
        return None
    return np.divide(numerator, denominator, out=np.full_like(numerator,np.nan), where=denominator > 0)


def summarize_workout(segments, simulations, residual_mean):
    frames = []
    for s, simulated in zip(segments, simulations, strict=True):
        low, high = np.quantile(simulated, [.1,.9], axis=0)
        frames.append(pd.DataFrame(dict(segment_id=s.segment_id, elapsed_seconds=s.time,
            observed_power_w=s.target+s.residual, prescribed_power_w=s.target, observed_residual_w=s.residual,
            simulated_residual_w=simulated[0], simulated_power_w=s.target+simulated[0],
            mean_power_w=s.target+residual_mean, p10_power_w=s.target+low, p90_power_w=s.target+high)))
    table = pd.concat(frames, ignore_index=True)
    observed = np.concatenate([s.residual for s in segments])
    simulated = np.concatenate(simulations, axis=1)  # moments only, never lag construction
    target = np.concatenate([s.target for s in segments])
    std = simulated.std(axis=1)
    summary = dict(workout_id=segments[0].workout_id, n_samples=len(observed),
        observed_residual_mean_w=float(observed.mean()), observed_residual_sd_w=float(observed.std()),
        simulated_residual_mean_w=float(simulated.mean()), simulated_sd_p10_w=float(np.quantile(std,.1)),
        simulated_sd_median_w=float(np.median(std)), simulated_sd_p90_w=float(np.quantile(std,.9)),
        simulated_negative_power_fraction=float(np.mean(simulated+target < 0)),
        empirical_p10_p90_coverage=float(np.mean((table.observed_power_w >= table.p10_power_w)
                                                & (table.observed_power_w <= table.p90_power_w))))
    for name, errors in [('baseline', observed), ('mean_prediction',observed-residual_mean),
                         ('example_simulation', observed-simulated[0])]:
        metrics = error_metrics(errors)
        summary.update({name+'_'+k: v for k,v in metrics.items() if k != 'n'})
    for lag in [1,5,10,30]:
        real = pooled_acf([s.residual for s in segments], lag)
        generated = pooled_acf(simulations, lag)
        summary[f'observed_acf{lag}'] = float(real[0]) if real is not None else np.nan
        summary[f'simulated_acf{lag}_median'] = float(np.nanmedian(generated)) if generated is not None else np.nan
    return table, summary


def plot_workout(table, path, workout_id, paths):
    from .plots import plt, save
    fig, axes = plt.subplots(2,1,figsize=(15,8),sharex=True)
    for first, (_, part) in enumerate(table.groupby('segment_id',sort=False)):
        label = lambda text: text if first == 0 else None
        t = part.elapsed_seconds/60
        axes[0].plot(t,part.observed_power_w,color='#697780',alpha=.65,lw=.7,label=label('Potenza reale'))
        axes[0].step(t,part.prescribed_power_w,where='post',color='#c5892d',ls='--',lw=1.1,label=label('Prescrizione'))
        axes[0].plot(t,part.simulated_power_w,color='#167ca5',alpha=.8,lw=.7,label=label('Prescrizione + residuo simulato'))
        axes[1].fill_between(t,part.p10_power_w-part.prescribed_power_w,
                            part.p90_power_w-part.prescribed_power_w,color='#167ca5',alpha=.13,
                            label=label(f'P10-P90 puntuali, {paths} simulazioni'))
        axes[1].plot(t,part.observed_residual_w,color='#697780',alpha=.7,lw=.7,label=label('Residuo osservato'))
        axes[1].plot(t,part.simulated_residual_w,color='#167ca5',alpha=.8,lw=.7,label=label('Residuo simulato, prima traiettoria'))
    axes[0].set_ylabel('Potenza [W]')
    axes[1].set(ylabel='Residuo [W]',xlabel='Tempo trascorso nel workout [min]')
    axes[1].axhline(0,color='black',lw=.6)
    for ax in axes:
        ax.legend(ncol=3,fontsize=8,loc='upper right')
    fig.suptitle(f'Workout {workout_id} - simulazione AR libera dell\'intera sessione',fontsize=14)
    save(fig,path,'Storia simulata continua ai cambi di lap e prescrizione; nessun modello del transitorio. Reset solo sui tratti non continui/validi.\nInizializzazione stazionaria e innovazioni gaussiane; nessun residuo misurato alimenta la simulazione. I picchi casuali non devono coincidere.')
