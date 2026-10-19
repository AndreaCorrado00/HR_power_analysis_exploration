"""Deterministic lap-based prescriptions: hypotheses, never original coach plans."""
from __future__ import annotations

from copy import deepcopy
import math
from statistics import median

import numpy as np
import pandas as pd

from .fit_reader import FitActivity


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def rounded(value, step=1):
    return math.floor(value / step + .5) * step


def is_assigned(row):
    return row.get('prescription_kind')=='maximal' or row.get('power_target_w') is not None


def classify(mean_power, duration, rules):
    """Classify observed power; never use duration as an exclusion criterion."""
    power, duration = number(mean_power), number(duration)
    result = dict(base_zone=None, category=None, power_target_w=None, prescription_kind='unassigned',
                  reference_low_w=None, reference_high_w=None,
                  candidate_categories=[], flags=[])
    if power is None or power < 0 or duration is None or duration <= 0:
        result['flags'].append('invalid_power_or_duration')
        return result
    if power>488 and rules.get('above_z6_policy')=='categorical_maximal':
        result.update(base_zone='Z7',category='Z7',prescription_kind='maximal',
                      reference_low_w=488,candidate_categories=['Z7'])
        result['flags'].append('maximal_by_dataset_convention')
        if not 5<=duration<=15:
            result['flags'].append('outside_indicative_duration')
        return result
    membership = rounded(power)
    for label, low, high in [('Z1',0,179),('Z2',180,244),('Z3',245,293),
                             ('Z4',294,341),('Z5',342,390),('Z6',391,488)]:
        if low <= membership <= high:
            result.update(base_zone=label, reference_low_w=low, reference_high_w=high)
            break
    candidates = [z for z in rules['zones'] if z['low_w'] <= membership <= z['high_w']]
    result['candidate_categories'] = [z['id'] for z in candidates]
    if rules.get('power_model')=='rounded_observed_mean':
        value=rounded(power,rules['target_rounding_w'])
        result.update(power_target_w=value,prescription_kind='power',category=result['base_zone'])
        if candidates:
            chosen=min(candidates,key=lambda z:abs(power-(z['low_w']+z['high_w'])/2))
            result.update(category=chosen['id'],reference_low_w=chosen['low_w'],reference_high_w=chosen['high_w'])
            if not chosen['min_s']<=duration<=chosen['max_s']:
                result['flags'].append('outside_indicative_duration')
        else:
            result['flags'].append('no_matching_subzone')
        if len(candidates)>1:
            result['flags'].append('overlapping_categories')
        if result['reference_low_w'] is not None and not result['reference_low_w']<=value<=result['reference_high_w']:
            result['flags'].append('rounded_target_outside_observed_category')
        return result
    if not candidates:
        result['flags'].append('z4_subzone_gap' if result['base_zone']=='Z4' else 'above_defined_power_ranges')
        if membership > 488 and 5 <= duration <= 15:
            result['flags'].append('sprint_duration_compatible_not_proof_of_z7')
        return result
    if len(candidates)>1:
        result['flags'].append('overlapping_categories')
    def target(zone):
        if zone['id']=='Z1':
            if rules['z1_policy']=='rounded_lap_mean':
                return min(179, max(0, rounded(power, rules['z1_rounding_w'])))
            return None
        if not zone['linear'] and not (zone['id']=='Z2' and rules['z2_open_upper_policy']=='cap_at_6h'):
            return None
        fraction = min(1, max(0,(duration-zone['min_s'])/(zone['max_s']-zone['min_s'])))
        return zone['high_w']-(zone['high_w']-zone['low_w'])*fraction
    ranked = sorted(enumerate(candidates), key=lambda pair:
                    (abs(target(pair[1])-power) if target(pair[1]) is not None else math.inf, pair[0]))
    chosen = ranked[0][1]
    value = target(chosen)
    result.update(category=chosen['id'], power_target_w=round(value,3) if value is not None else None,
                  prescription_kind='power' if value is not None else 'unassigned',
                  reference_low_w=chosen['low_w'], reference_high_w=chosen['high_w'])
    if value is None:
        result['flags'].append('undefined_duration_power_rule')
    if duration < chosen['min_s'] or duration > chosen['max_s']:
        result['flags'].append('outside_indicative_duration')
    return result


def extract_laps(activity: FitActivity, rules):
    """Inclusive FIT endpoints; a sample shared by laps belongs to the later lap.

    No gap filling, midpoint correction, interpolation or replacement of records.
    Assignment retains original record order and is zero outside recorded laps.
    """
    records = activity.records
    times = pd.to_datetime(records.get('timestamp',pd.Series(index=records.index,dtype=object)),utc=True,errors='coerce')
    powers = pd.to_numeric(records.get('power',pd.Series(index=records.index,dtype=float)),errors='coerce')
    origin = times.min()
    assignment = np.zeros(len(records), dtype=int)
    rows=[]
    for i,lap in enumerate(activity.messages.get('lap',[]),1):
        start = pd.to_datetime(lap.get('start_time'),utc=True,errors='coerce')
        end = pd.to_datetime(lap.get('timestamp'),utc=True,errors='coerce')
        duration = number(lap.get('total_timer_time'))
        flags=[]
        if pd.isna(start) or pd.isna(end) or end<start:
            flags.append('invalid_lap_boundaries')
        else:
            assignment[((times>=start)&(times<=end)).to_numpy()] = i
        if duration is None or duration<=0:
            flags.append('invalid_timer_duration')
        elapsed = number(lap.get('total_elapsed_time'))
        if elapsed is not None and duration is not None and elapsed-duration>1:
            flags.append('timer_elapsed_difference')
        rows.append(dict(lap_index=i,start_timestamp=None if pd.isna(start) else start.isoformat(),
                         end_timestamp=None if pd.isna(end) else end.isoformat(),
                         start_elapsed_s=None if pd.isna(start) or pd.isna(origin) else (start-origin).total_seconds(),
                         end_elapsed_s=None if pd.isna(end) or pd.isna(origin) else (end-origin).total_seconds(),
                         duration_s=duration,fit_elapsed_s=elapsed,lap_trigger=lap.get('lap_trigger'),
                         fit_avg_power_w=number(lap.get('avg_power')),flags=flags))
    for row in rows:
        selected = powers[assignment==row['lap_index']]
        valid = selected[np.isfinite(selected)&(selected>=0)]
        mean = float(valid.mean()) if len(valid) else None
        result = classify(mean,row['duration_s'],rules)
        result['flags'] = row['flags']+result['flags']
        if len(valid)<len(selected): result['flags'].append('missing_or_invalid_power_samples')
        if row['fit_avg_power_w'] is not None and mean is not None and abs(row['fit_avg_power_w']-mean)>5:
            result['flags'].append('fit_average_differs_from_sample_mean')
        sample_times = times[assignment==row['lap_index']]
        delta = sample_times.diff().dt.total_seconds()
        if delta.gt(2).any(): result['flags'].append('recording_gaps')
        if delta.le(0).any(): result['flags'].append('non_increasing_timestamps')
        row.update(mean_power_w=mean,sample_count=len(selected),valid_power_samples=len(valid),
                   missing_power_samples=len(selected)-len(valid),zero_power_samples=int(valid.eq(0).sum()),
                   **result)
        row['individual_power_target_w']=row['power_target_w']
        row['individual_prescription_kind']=row['prescription_kind']
        row['individual_category']=row['category']
        row['ideal_duration_s']=None
        row['block_id']=None
        row['family_id']=None
        row['phase_index']=None
        row['phase_role']=None
    return rows,assignment


def _close(a,b,absolute,fraction):
    return abs(a-b)<=max(absolute,fraction*min(a,b))


def _domain(row):
    if 'assignment_domain' in row:
        return row['assignment_domain']
    if row.get('prescription_kind')=='maximal':
        return 'maximal'
    return 'resolved' if row.get('power_target_w') is not None else f"unresolved:{row.get('base_zone')}"


def _compatible(a,b,cfg):
    if _domain(a)!=_domain(b):
        return False
    if any(number(row.get(key)) is None or row[key]<=0
           for row in (a,b) for key in ('duration_s',)):
        return False
    if any(number(row.get('mean_power_w')) is None for row in (a,b)):
        return False
    if cfg.get('power_match_mode')=='relative_to_shared_target':
        power_ok=abs(a['mean_power_w']-b['mean_power_w'])<=cfg['power_tolerance_fraction']*(a['mean_power_w']+b['mean_power_w'])+1e-9
    else:
        power_ok=_close(a['mean_power_w'],b['mean_power_w'],cfg['power_tolerance_floor_w'],cfg['power_tolerance_fraction'])
    return (_close(a['duration_s'],b['duration_s'],cfg['duration_tolerance_floor_s'],cfg['duration_tolerance_fraction']) and power_ok)


def _shared_power_valid(group,rules):
    if rules['patterns'].get('power_match_mode')!='relative_to_shared_target':
        return True
    values=[row['mean_power_w'] for row in group]
    target=median(values)
    if group[0]['prescription_kind']=='power':
        target=rounded(target,rules['target_rounding_w'])
    return all(abs(value-target)<=rules['patterns']['power_tolerance_fraction']*target+1e-9 for value in values)


def _snap(duration,cfg):
    for upper,step in cfg['snap_grids_s']:
        if duration<=upper:
            return max(step,rounded(duration,step))
    return duration


def _profiles(rows,indices,period):
    return [dict(duration_s=median(rows[i]['duration_s'] for i in indices[j::period]),
                 mean_power_w=median(rows[i]['mean_power_w'] for i in indices[j::period]),
                 assignment_domain=_domain(rows[indices[j]]))
            for j in range(period)]


def recognize_blocks(rows,rules):
    """Find repeated 2..N-phase motifs, then share targets by session-local family.

    Complete-link matching prevents gradually drifting efforts from being merged.
    Greedy longest non-overlapping motifs have deterministic tie breaks.
    """
    cfg=rules['patterns']; candidates=[]
    for start in range(len(rows)):
        for period in range(2,cfg['max_period_laps']+1):
            seed=rows[start:start+period]
            if len(seed)!=period or not all(_compatible(r,r,cfg) for r in seed): continue
            powers=[r['mean_power_w'] for r in seed]
            if max(powers)-min(powers)<cfg['minimum_phase_contrast_w']: continue
            # Two-phase blocks begin with ON. Multi-phase motifs may start below
            # their peak (e.g. threshold -> tempo -> sprint -> recovery).
            if period==2 and powers[0]!=max(powers): continue
            indices=[]
            for i in range(start,len(rows)):
                if i>start:
                    end=number(rows[i-1].get('end_elapsed_s'))
                    begin=number(rows[i].get('start_elapsed_s'))
                    if end is None or begin is None: break
                    gap=begin-end
                    if gap>cfg['maximum_boundary_gap_s'] or gap < -cfg['maximum_boundary_overlap_s']: break
                phase=(i-start)%period
                if not _compatible(rows[i],seed[phase],cfg): break
                if not all(_compatible(rows[i],rows[j],cfg) for j in indices[phase::period]): break
                indices.append(i)
            minimum=(cfg['min_short_complete_cycles'] if seed[0]['duration_s']<cfg['short_on_limit_s']
                     else cfg['min_complete_cycles'])
            # A prefix median can fail even when the completed motif is valid.
            # Evaluate the longest candidate first, then trim only invalid tails.
            while len(indices)//period>=minimum and not all(
                    _shared_power_valid([rows[j] for j in indices[phase::period]],rules)
                    for phase in range(period)):
                indices.pop()
            if len(indices)//period<minimum: continue
            candidates.append((indices,period))
    used=set(); selected=[]
    for indices,period in sorted(candidates,key=lambda c:(-len(c[0]),c[1],c[0][0])):
        if used.intersection(indices): continue
        selected.append((indices,period)); used.update(indices)
    selected.sort(key=lambda c:c[0][0])
    families=[]; blocks=[]
    for indices,period in selected:
        profile=_profiles(rows,indices,period)
        compatible=[]
        for f,family in enumerate(families):
            if family['period']!=period: continue
            if not all(_shared_power_valid([rows[i] for _, prior_indices in family['blocks'] for i in prior_indices[phase::period]]+
                                           [rows[i] for i in indices[phase::period]],rules) for phase in range(period)):
                continue
            if all(all(_compatible(a,b,cfg) for a,b in zip(profile,prior)) for prior in family['profiles']):
                compatible.append(f)
        if compatible:
            f=compatible[0]
        else:
            f=len(families)
            families.append(dict(period=period,profiles=[],blocks=[]))
        family=families[f]; family['profiles'].append(profile)
        block=dict(block_id=len(blocks)+1,family_id=f+1,period_laps=period,
                   lap_indices=[rows[i]['lap_index'] for i in indices],
                   complete_repetitions=len(indices)//period,partial_phase_count=len(indices)%period,
                   protocol=None,phases=[])
        family['blocks'].append((block,indices)); blocks.append(block)
    for family in families:
        period=family['period']
        members=[[] for _ in range(period)]
        for block,indices in family['blocks']:
            for j,i in enumerate(indices): members[j%period].append(i)
        durations=[median(rows[i]['duration_s'] for i in group) for group in members]
        powers=[median(rows[i]['mean_power_w'] for i in group) for group in members]
        ideal=[_snap(d,cfg) for d in durations]
        protocol='multiphase_repeats_candidate'
        if period==2:
            if (_close(durations[0],30,cfg['duration_tolerance_floor_s'],cfg['duration_tolerance_fraction']) and
                _close(durations[1],15,cfg['duration_tolerance_floor_s'],cfg['duration_tolerance_fraction'])):
                ideal=[30,15]; protocol='30_15_candidate'
            elif durations[0]>=cfg['extensive_on_min_s']:
                protocol='extensive_repeats_candidate'
            else:
                protocol='alternating_repeats_candidate'
        phases=[]
        for phase,group in enumerate(members):
            inferred=classify(powers[phase],ideal[phase],rules)
            if any(not is_assigned(rows[i]) for i in group):
                inferred['power_target_w']=None
                inferred['prescription_kind']='unassigned'
                inferred['flags'].append('unresolved_phase_members')
            role=('on' if phase==0 else 'off') if period==2 else f'phase_{phase+1}'
            phases.append(dict(phase_index=phase+1,phase_role=role,ideal_duration_s=ideal[phase],
                               representative_duration_s=durations[phase],
                               representative_mean_power_w=powers[phase],**deepcopy(inferred)))
            for i in group:
                row=rows[i]
                row.setdefault('individual_power_target_w',row['power_target_w'])
                row.setdefault('individual_prescription_kind',row['prescription_kind'])
                row.setdefault('individual_category',row['category'])
                prior_flags=row['flags']
                row.update(deepcopy(inferred))
                row['flags']=sorted(set(prior_flags+inferred['flags']+['shared_repeat_phase_target']))
                row.update(phase_index=phase+1,phase_role=role,ideal_duration_s=ideal[phase])
        for block,indices in family['blocks']:
            block.update(protocol=protocol,phases=deepcopy(phases))
            for i in indices:
                rows[i].update(block_id=block['block_id'],family_id=block['family_id'])
    return blocks
