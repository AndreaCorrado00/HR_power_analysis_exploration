"""No scientific estimation is permitted in this development test suite."""
from pathlib import Path
from uuid import uuid4
import pytest


@pytest.fixture
def tmp_path():
    # pytest's mode=0700 directories are inaccessible under this Windows sandbox.
    path=Path(__file__).resolve().parents[2]/'tmp'/('study-test-'+str(uuid4()))
    path.mkdir(parents=True)
    return path


@pytest.fixture(autouse=True)
def prohibit_fitting(monkeypatch):
    import numpy as np
    from study_app.scientific.frozen.hr.models import p1d,profile_search
    from study_app.scientific.frozen.hr import population
    from study_app.scientific.frozen.power import dynamics,ar
    def forbidden(*args,**kwargs): raise AssertionError('Fitting vietato durante lo sviluppo')
    monkeypatch.setattr(np.linalg,'lstsq',forbidden)
    for module,name in [(p1d,'fit'),(p1d,'least_squares'),(dynamics,'fit_response'),
                        (dynamics,'least_squares'),(ar,'fit_ar'),(population,'fit_reml'),(population,'minimize')]:
        monkeypatch.setattr(module,name,forbidden)
