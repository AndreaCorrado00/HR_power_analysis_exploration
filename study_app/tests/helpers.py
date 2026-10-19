import numpy as np
import struct
from fitdecode.utils import compute_crc
from study_app.scientific.adapters import load_frozen_config


def fit_bytes(n=601,missing=False):
    data=bytes([0x40,0,0])+struct.pack('<H',20)+bytes([3,253,4,0x86,7,2,0x84,3,1,2])
    for t in range(n): data+=bytes([0])+struct.pack('<IHB',1000000000+t,65535 if missing and t==10 else (100 if t<300 else 200),255 if missing and t==11 else 120)
    data+=bytes([0x41,0,0])+struct.pack('<H',19)+bytes([4,2,4,0x86,253,4,0x86,7,4,0x86,8,4,0x86])
    data+=bytes([1])+struct.pack('<IIII',1000000000,1000000000+n-1,(n-1)*1000,(n-1)*1000)
    header=struct.pack('<BBHI4s',12,0x10,100,len(data),b'.FIT')
    return header+data+struct.pack('<H',compute_crc(header+data))


def synthetic_workout(start='2026-10-20T10:00:00+00:00',raw='synthetic'):
    n=601
    return dict(source_name='synthetic.fit',raw_sha256=raw,raw_path='unused.fit',start_time=start,timer_start=None,duration_s=n-1,
        eligible_power=True,eligible_hr=True,reasons=[],quality={'total_samples':n,'valid_samples':n,'missing_hr':0,'non_1s_steps':0},
        series={'elapsed_seconds':list(range(n)),'power_w':([100]*300+[200]*301),'heart_rate_bpm':[120.]*n,
            'power_target_w':([100]*300+[200]*301),'timer_paused':[False]*n,'power_segment_id':[1]*n,'lap_index':[1]*n})


def synthetic_model(exp=None):
    config=load_frozen_config()
    return {'experiment_id':exp['id'] if exp else 'synthetic','config':config,
        'split':exp['split'] if exp else {'train':[],'validation':[]},'raw_hashes':{},'train_period':['2026-01-01T00:00:00Z','2026-02-01T00:00:00Z'],
        'domain':{'power_quantiles_w':[0,100,150,200,400],'samples':1000,'segment_durations_s':[1000],'workout_durations_s':[1000]},
        'power':{'dynamics':{'order':2,'a':[1,0,0],'b':[0,0,0],'mean':0},'ar':{'p':2,'coefficients':[.5,.1],'intercept':0,'hold_back':2,'sigma2':100},'seed':42,'paths':1000},
        'hr':{'manifest':{'parameter_bounds':{'keys':['K','L','tau','B'],'lower':[.000001,0,.01,60],'upper':[5,30,1800,200]}},
              'analysis':{'status':'estimated','model':{'keys':['K','L','tau'],'mean':[.2,5,50],'covariance':[[.0001,0,0],[0,1,0],[0,0,4]],'sd':[.01,1,2],'mean_ci95':[[.18,.22],[4,6],[48,52]]},
                          'B_reference':{'A':80},'HR0_reference':{'mean':120}},'static':{'beta':[80,.2]}},'validation':{'workouts':[],'aggregate':[]},'fits':[],'software':{'purpose':'synthetic test fixture; never fitted'}}
