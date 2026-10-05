"""Each model supplies metadata, defaults, config validation and segment fitting."""
from . import p1d

REGISTRY = {'p1d': p1d}


def get_model(model_id):
    if model_id not in REGISTRY:
        raise ValueError('Modello sconosciuto')
    return REGISTRY[model_id]
