import pytest
from study_app.backend.prescriptions import parse_prescription,resolve_targets


def test_repeat_expansion_and_csv():
    p=parse_prescription('duration_s,target_w\n2,100\n3,200\n','csv')
    out=resolve_targets(p,{})[0]
    assert out['target']==[100,100,200,200,200,200]
    assert out['duration_s']==5


def test_range_requires_explicit_choice():
    p={'schema_version':1,'name':'Range','blocks':[{'duration_s':2,'target':{'kind':'range','low_w':100,'high_w':200}}]}
    with pytest.raises(ValueError): resolve_targets(p,{})
    assert resolve_targets(p,{'0':{'mode':'center'}})[0]['target']==[150,150,150]
    assert len(resolve_targets(p,{'0':{'mode':'scenarios','values':{'easy':110,'hard':190}}}))==2


@pytest.mark.parametrize('duration',[0,-1,1.5,True])
def test_duration_must_be_positive_integer(duration):
    with pytest.raises(ValueError): resolve_targets({'schema_version':1,'blocks':[{'duration_s':duration,'target':{'kind':'constant','watts':100}}]}, {})


def test_explicit_profile_includes_its_final_endpoint():
    p={'schema_version':1,'blocks':[{'duration_s':2,'target':{'kind':'range','low_w':100,'high_w':200}}]}
    result=resolve_targets(p,{'0':{'mode':'profile','points':[[0,100],[2,200]]}})
    assert result[0]['target']==[100,150,200]
