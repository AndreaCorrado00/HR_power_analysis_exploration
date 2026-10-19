from pathlib import Path
import json
from uuid import uuid4

import pandas as pd
import pytest

from power_hr_eda.prescription_cli import export_dataset, resolve_fit_source
from test_prescriptions import activity


@pytest.fixture
def tmp_path():
    # Python 3.14's mode=0o700 used by pytest tmpdir conflicts with this
    # Windows sandbox. Use a normal repository-local directory instead.
    path=Path(__file__).parent/'_generated'/f'prescriptions-{uuid4().hex}'
    path.mkdir(parents=True)
    return path


@pytest.fixture
def rules():
    return json.loads((Path(__file__).parents[1]/'references/prescription_rules.json').read_text())


def test_export_preserves_samples_and_accounts_for_every_source(tmp_path, rules):
    source=tmp_path/'input'; source.mkdir()
    for name in ['lap.fit','no_laps.fit','broken.fit']:
        (source/name).write_bytes(b'12345678.FIT')
    a=activity([(0,2),(3,5)], [300,301,302,0,None,150])
    no_laps=activity([], [100,200])
    def read(path):
        if path.name=='broken.fit':
            from dataclasses import replace
            return replace(no_laps,parse_error='test error')
        return a if path.name=='lap.fit' else no_laps
    output=tmp_path/'out'
    manifest=export_dataset(source,output,rules,reader=read)
    assert manifest['summary']['input_files']==3
    assert manifest['summary']['exported_workouts']==1
    assert manifest['summary']['excluded_no_laps']==1
    assert manifest['summary']['source_errors']==1
    samples=pd.read_csv(output/'samples/lap.csv.gz')
    assert samples.power_w.dropna().tolist()==[300,301,302,0,150]
    assert len(samples)==6
    assert samples.lap_index.tolist()==[1,1,1,2,2,2]
    laps=pd.read_csv(output/'laps.csv')
    assert len(laps)==2
    assert (output/'report.md').is_file()
    assert (output/'workouts.jsonl').is_file()
    assert len(manifest['output_sha256'])==5
    repeated=export_dataset(source,tmp_path/'repeat',rules,reader=read)
    assert repeated['output_sha256']==manifest['output_sha256']
    with pytest.raises(FileExistsError):
        export_dataset(source,output,rules,reader=read)


def test_text_reference_and_binary_fit_are_resolved(tmp_path):
    binary=tmp_path/'original.fit'; binary.write_bytes(b'12345678.FIT')
    pointer=tmp_path/'pointer.fit'; pointer.write_text(binary.as_posix())
    assert resolve_fit_source(binary)==binary.resolve()
    assert resolve_fit_source(pointer)==binary.resolve()
    pointer.write_text('missing.fit')
    with pytest.raises((ValueError,FileNotFoundError)):
        resolve_fit_source(pointer)


def test_output_inside_source_is_rejected_without_writes(tmp_path,rules):
    with pytest.raises(ValueError):
        export_dataset(tmp_path,tmp_path/'output',rules)
    assert not (tmp_path/'output').exists()


def test_excludes_whole_workout_with_unassigned_lap_but_keeps_maximal(tmp_path,rules):
    source=tmp_path/'input'; source.mkdir()
    for name in ['maximal.fit','incomplete.fit']:
        (source/name).write_bytes(b'12345678.FIT')
    complete=activity([(0,2),(3,5)], [600]*3+[300]*3)
    incomplete=activity([(0,2),(3,5)], [600]*3+[310]*3)
    result=export_dataset(source,tmp_path/'out',rules,
                          reader=lambda p:complete if p.name=='maximal.fit' else incomplete)
    assert result['summary']['exported_workouts']==1
    assert result['summary']['excluded_unassigned_laps']==1
    assert result['summary']['unassigned_laps']==0
    assert result['summary']['maximal_laps']==1
    assert not (tmp_path/'out/samples/incomplete.csv.gz').exists()
    laps=pd.read_csv(tmp_path/'out/laps.csv')
    assert set(laps.workout_id)=={'maximal'}
    samples=pd.read_csv(tmp_path/'out/samples/maximal.csv.gz')
    assert samples.prescription_kind.tolist()==['maximal']*3+['power']*3
    excluded=next(e for e in result['activities'] if e['workout_id']=='incomplete')
    assert excluded['unassigned_lap_indices']==[2]


def test_pin_previous_workout_selection(tmp_path,rules):
    source=tmp_path/'input'; source.mkdir()
    for name in ['keep.fit','previously_excluded.fit']:
        (source/name).write_bytes(b'12345678.FIT')
    previous=tmp_path/'selection.json'
    previous.write_text(json.dumps({'activities':[{'workout_id':'keep','status':'exported'},
                                                 {'workout_id':'previously_excluded','status':'excluded_unassigned_laps'}]}))
    result=export_dataset(source,tmp_path/'out',rules,
                          reader=lambda _:activity([(0,2)],[200]*3),selection_manifest=previous)
    assert result['summary']['input_files']==1
    assert [entry['workout_id'] for entry in result['activities']]==['keep']
    assert result['selection_manifest_sha256']
