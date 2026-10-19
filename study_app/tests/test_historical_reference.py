"""Optional local oracle. No scientific outputs are copied into the test suite."""
import json
from pathlib import Path
import numpy as np
import pytest
from study_app.scientific.adapters import simulate_hr


def test_existing_validation_forward_without_refitting():
    root=Path(__file__).resolve().parents[2]/'archive/experiments/prescribed_joint/results'
    if not (root/'validation.json').exists(): pytest.skip('Riferimento storico locale assente')
    bundle=json.loads((root/'hr_model.json').read_text())
    validation=json.loads((root/'validation.json').read_text())
    # Locate one stored trajectory without assuming a private output ordering.
    def find(value):
        if isinstance(value,dict):
            if 'hr_real_power' in value and 'power' in value:return value
            for child in value.values():
                result=find(child)
                if result is not None:return result
        if isinstance(value,list):
            for child in value:
                result=find(child)
                if result is not None:return result
    series=find(validation);assert series is not None
    a=bundle['analysis']
    predicted=simulate_hr(np.array(series['power'])[None,:],np.array(a['model']['mean'])[None,:],a['B_reference']['A'],a['HR0_reference']['mean'])[0]
    np.testing.assert_allclose(predicted,series['hr_real_power'],rtol=1e-10,atol=1e-10)
