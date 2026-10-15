import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('prescription_plot',Path(__file__).parents[1]/'scripts/plot_prescribed_workouts.py')
plot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(plot)


def test_plot_breaks_at_single_missing_timestamp():
    x,y=plot.broken_line(np.array([0.,1.,3.]),np.array([100.,100.,90.]))
    assert np.isnan(x[2]) and np.isnan(y[2])


def test_plot_breaks_segment_boundary_and_masks_invalid_values():
    x,y=plot.broken_line(np.array([0.,1.,2.]),np.array([100.,0.,90.]),np.array([1,0,2]))
    assert np.isfinite(y).sum()==2
    assert np.isnan(y[1:4]).all()


def test_maximal_band_does_not_cover_a_missing_second():
    frame=pd.DataFrame(dict(elapsed_seconds=[0.,2.],prescription_kind=['maximal','maximal'],power_segment_id=[1,2]))
    assert list(plot.spans(frame,'maximal'))==[(0.,1/60),(2/60,3/60)]
