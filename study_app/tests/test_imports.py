import io,zipfile
import pytest
from study_app.backend.imports import unpack_upload
from study_app.backend.imports import import_files
from study_app.backend.repository import Repository
from study_app.tests.helpers import fit_bytes


@pytest.mark.parametrize('name',['../evil.fit','/evil.fit','C:/evil.fit','nested.zip'])
def test_unsafe_archive_is_rejected(name):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z: z.writestr(name,b'bad')
    with pytest.raises(ValueError): list(unpack_upload('dataset.zip',b.getvalue()))


def test_fit_upload_and_nested_directory():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z: z.writestr('folder/a.fit',b'fit')
    assert list(unpack_upload('x.zip',b.getvalue()))==[('folder/a.fit',b'fit')]


def test_actual_fit_parser_preserves_missing_and_targets(tmp_path):
    r=Repository(tmp_path);a=r.create_athlete(dict(first_name='A',last_name='B',age=30,ftp_w=260))
    raw=fit_bytes(missing=True)
    batch=import_files(r,a['id'],[('real-format.fit',raw)])
    assert len(batch['added'])==1,batch['outcomes']
    w=r.get(batch['added'][0]);assert len(w['series']['power_w'])==601
    assert w['series']['power_w'][10] is None and w['series']['heart_rate_bpm'][11] is None
    assert w['series']['power_target_w'][100]==150
    assert w['rules']['ftp_w']==260
    assert (r.root/w['raw_path']).read_bytes()==raw
    again=import_files(r,a['id'],[('renamed.fit',raw)])
    assert again['outcomes'][0]['status']=='duplicate'
    assert len(r.get(again['dataset_revision_id'])['workout_ids'])==1


def test_no_ftp_allows_inspection_but_no_target(tmp_path):
    r=Repository(tmp_path);a=r.create_athlete(dict(first_name='A',last_name='B',age=30))
    batch=import_files(r,a['id'],[('a.fit',fit_bytes())]);assert batch['added'],batch
    w=r.get(batch['added'][0])
    assert not w['eligible_power'] and all(v is None for v in w['series']['power_target_w'])
