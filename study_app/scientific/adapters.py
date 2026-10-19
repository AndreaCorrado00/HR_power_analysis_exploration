"""Explicit, train-only forward interface to the frozen scientific code."""
import json
from pathlib import Path
import numpy as np
from .frozen.joint.simulation import hr_trajectories, stream
from .frozen.power.model import DecompositionModel
from .frozen.power.ar import simulate_residual

HERE = Path(__file__).parent


def load_frozen_config():
    return json.loads((HERE/'frozen_config.json').read_text(encoding='utf-8'))


def rules_for_ftp(ftp):
    if ftp is None or not np.isfinite(ftp) or ftp <= 0:
        raise ValueError('FTP positiva necessaria per applicare le regole congelate.')
    rules = json.loads((HERE/'prescription_rules.json').read_text(encoding='utf-8'))
    ratio = ftp/325
    rules.update(ftp_w=ftp, ftp_ratio=ratio, reference_ftp_w=325)
    for zone in rules['zones']:
        for key in ('low_w', 'high_w'):
            zone[key] *= ratio
    return rules


def simulate_hr(power_w, theta, intercept_bpm, hr0_bpm):
    return hr_trajectories(power_w, theta, intercept_bpm, hr0_bpm)


def simulate_power(target_w, config, paths=1000, seed=42, key='prediction'):
    target = np.asarray(target_w, float)
    model = DecompositionModel.from_dict(config)
    noise = simulate_residual(model.ar, len(target), paths, stream(key, 'power', seed))
    return np.maximum(0, target[None,:] + model.dynamics.response(target)[None,:] + noise)


def simulate_chain(target, model, paths=1000, seed=42, key='prediction', observed_power=None):
    if not isinstance(paths, int) or not 1 <= paths <= 1000 or not isinstance(seed,int) or seed < 0:
        raise ValueError('Monte Carlo: 1–1000 traiettorie, seed intero non negativo.')
    analysis = model['hr']['analysis']
    if analysis['status'] != 'estimated':
        raise ValueError('Popolazione HR non stimabile; nessun fallback.')
    pop = analysis['model']
    if pop['keys'] != ['K','L','tau']:
        raise ValueError('Ordine dei parametri HR incompatibile.')
    candidates = stream(key,'hr',seed).multivariate_normal(pop['mean'],pop['covariance'],size=20*paths,check_valid='raise')
    bounds = model['hr']['manifest']['parameter_bounds']
    lo = np.asarray(bounds['lower'][:3]); hi = np.asarray(bounds['upper'][:3])
    theta = candidates[np.all((candidates>=lo)&(candidates<=hi),axis=1)][:paths]
    if len(theta) != paths:
        raise ValueError('Estrazioni HR ammissibili insufficienti.')
    p = simulate_power(target,model['power'],paths,seed,key) if observed_power is None else np.broadcast_to(np.asarray(observed_power,float),(paths,len(observed_power)))
    h = simulate_hr(p,theta,analysis['B_reference']['A'],analysis['HR0_reference']['mean'])
    result = {}
    for name, values in [('power',p),('hr',h)]:
        result[name] = {'mean':values.mean(axis=0).tolist(),'lower':np.quantile(values,.025,axis=0).tolist(),'upper':np.quantile(values,.975,axis=0).tolist()}
    return result
