from .repository import digest
from .prescriptions import resolve_targets
from study_app.scientific.adapters import simulate_chain

POLICY={'origin':'first_timer_start_else_first_sample','clock':'elapsed','gaps':'diagnostic_reset_train_references',
        'hr_initial':'train_mean','B':'train_A_plus_K_P0','alignment_shift':0,'bands':'pointwise_95_partial_variability'}


def predict(repo,prescription_id,model_id,choices,paths=1000,seed=42):
    prescription=repo.get(prescription_id);model=repo.get(model_id,prescription['athlete_id'])
    if model['kind']!='models':raise ValueError('Versione modello richiesta')
    scenarios=resolve_targets(prescription['draft'],choices)
    if sum(len(s['target']) for s in scenarios)*paths>20_000_000:
        raise ValueError('Simulazione oltre il budget memoria locale: ridurre numero traiettorie o durata/scenari')
    result=[];warnings=[]
    low,*_,high=model['domain']['power_quantiles_w']
    for scenario in scenarios:
        if min(scenario['target'])<low or max(scenario['target'])>high:warnings.append(f'{scenario["name"]}: target fuori intervallo di potenza train')
        if scenario['duration_s']>max(model['domain']['segment_durations_s']):warnings.append(f'{scenario["name"]}: durata oltre i tratti train')
        key=digest({'prescription':prescription['sha256'],'scenario':scenario['name'],'model':model['sha256']})
        simulation=simulate_chain(scenario['target'],model,paths,seed,key)
        result.append({**scenario,**simulation,'stream_key':key})
    return repo.create('predictions',prescription['athlete_id'],{'prescription_id':prescription_id,
        'prescription_original':prescription['draft'],'choices':choices,'model_id':model_id,'model_sha256':model['sha256'],
        'mc':{'paths':paths,'seed':seed},'policy':POLICY,'scenarios':result,'warnings':warnings})
