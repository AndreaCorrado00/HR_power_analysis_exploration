"""Explicit midpoint correction of lap support, without changing signal samples."""
from copy import deepcopy


def close_lap_gaps(laps, end, origin):
    result = deepcopy(laps)
    for lap in result:
        lap.setdefault('boundary_adjustment', {'method': 'midpoint-gaps-v1',
            'input_start': lap['start'], 'input_end': lap['end'], 'time_origin': str(origin)})
    for left, right in zip(result, result[1:]):
        if left['end'] < right['start']:
            midpoint = (left['end'] + right['start']) / 2
            left['end'] = right['start'] = midpoint
    if result:
        result[-1]['end'] = end
    return result
