import importlib.util
from pathlib import Path

import numpy as np


def test_direction_latency_and_ambiguity():
    path = Path(__file__).parents[1] / 'scripts' / 'plot_segment_groups.py'
    assert path.exists(), 'Missing visualization script'
    spec = importlib.util.spec_from_file_location('segment_groups', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    t = np.arange(100, dtype=float)
    up = np.linspace(120, 170, 100)
    down = up[::-1]
    high_low = np.r_[np.full(30, 400), np.full(70, 100)]
    bell = np.interp(t, [0, 30, 99], [130, 175, 145])
    assert module.classify(t, high_low, down)['label'] == 'UtD'
    assert module.classify(t, high_low, bell)['label'] == 'UtD'
    assert module.classify(t, high_low[::-1], up)['label'] == 'DtU'
    assert module.classify(t, high_low, up)['label'] == 'Ambiguo'
    assert module.classify(t, np.full(100, 200), up)['label'] == 'Ambiguo'
    assert module.classify(t, high_low, np.full(100, 150))['label'] == 'Ambiguo'
