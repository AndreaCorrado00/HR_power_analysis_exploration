from dataclasses import dataclass
import math
import pandas as pd
class NormalizationError(ValueError): pass
@dataclass(frozen=True)
class NormalizationRequest:
    weight_kg: object=None; hr_max_bpm: object=None; hr_threshold_bpm: object=None
    normalize_power: bool=False; normalize_hr_max: bool=False; normalize_hr_threshold: bool=False
def _valid(v:object,label:str)->float:
    try: n=float(v)
    except (TypeError,ValueError) as e: raise NormalizationError(f'{label} deve essere numerico') from e
    if not math.isfinite(n) or n<=0: raise NormalizationError(f'{label} deve essere finito e maggiore di zero')
    return n
def apply_normalizations(frame:pd.DataFrame,r:NormalizationRequest)->pd.DataFrame:
    out=frame.copy()
    if r.normalize_power: out['power_w_kg']=pd.to_numeric(out['power'],errors='coerce')/_valid(r.weight_kg,'Peso')
    if r.normalize_hr_max: out['hr_pct_max']=100*pd.to_numeric(out['heart_rate'],errors='coerce')/_valid(r.hr_max_bpm,'FC massima')
    if r.normalize_hr_threshold: out['hr_pct_threshold']=100*pd.to_numeric(out['heart_rate'],errors='coerce')/_valid(r.hr_threshold_bpm,'FC di soglia')
    return out
