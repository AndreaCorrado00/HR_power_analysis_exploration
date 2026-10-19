import csv
import io
import json
import math
import numpy as np


def number(value):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0:
        raise ValueError('Potenza finita non negativa richiesta')
    return float(value)


def parse_prescription(content,format):
    if format=='json':
        result=json.loads(content)
        if not isinstance(result,dict):raise ValueError('Oggetto JSON richiesto')
        return result
    if format!='csv':raise ValueError('Prescrizioni: JSON v1 o CSV duration_s,target_w')
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    if reader.fieldnames!=['duration_s','target_w']:raise ValueError('Header CSV: duration_s,target_w')
    blocks=[]
    for i,row in enumerate(reader,2):
        try:blocks.append({'duration_s':int(row['duration_s']),'target':{'kind':'constant','watts':float(row['target_w'])}})
        except (ValueError,TypeError):raise ValueError(f'Riga CSV {i}: durata intera e potenza numerica richieste')
    return {'schema_version':1,'name':'Import CSV','blocks':blocks}


def resolve_targets(draft,choices):
    if draft.get('schema_version')!=1:raise ValueError('schema_version deve essere 1')
    flattened=[]
    def expand(blocks,prefix='',depth=0):
        if depth>2 or not isinstance(blocks,list) or not blocks:raise ValueError('Blocchi assenti o ripetizioni oltre profondità 2')
        for i,b in enumerate(blocks):
            key=f'{prefix}{i}'
            if 'repeat' in b:
                count=b['repeat']
                if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=1000:raise ValueError(f'{key}: ripetizioni 1–1000')
                for _ in range(count): expand(b.get('blocks'),key+'.',depth+1)
            else:
                n=b.get('duration_s')
                if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=86400:raise ValueError(f'{key}: durata intera positiva in secondi')
                flattened.append((key,b))
            if len(flattened)>20000:raise ValueError('Troppi blocchi')
    expand(draft.get('blocks'))
    total=sum(b['duration_s'] for _,b in flattened)
    if total>86400:raise ValueError('Durata massima 24 ore')
    scenario_names=None
    for key,b in flattened:
        target=b.get('target',{})
        if target.get('kind')=='range':
            choice=choices.get(key,{})
            if choice.get('mode')=='scenarios':
                names=set(choice.get('values',{}))
                if not names or len(names)>10:raise ValueError('Fornire 1–10 scenari nominati')
                if scenario_names is not None and names!=scenario_names:raise ValueError('Ogni range deve definire gli stessi scenari completi')
                scenario_names=names
    outputs=[]
    for scenario in sorted(scenario_names or {'centrale'}):
        values=[];blocks=[]
        for key,b in flattened:
            endpoint=None
            n=b['duration_s'];t=b.get('target',{});kind=t.get('kind')
            if kind=='constant': v=np.full(n,number(t.get('watts')))
            elif kind=='range':
                low=number(t.get('low_w'));high=number(t.get('high_w'))
                if low>high:raise ValueError(f'{key}: range invertito')
                c=choices.get(key,{})
                if c.get('mode')=='center':v=np.full(n,(low+high)/2)
                elif c.get('mode')=='scenarios':v=np.full(n,number(c['values'][scenario]))
                elif c.get('mode')=='profile':
                    points=c.get('points',[])
                    if len(points)<2:raise ValueError('Profilo: almeno due punti [tempo_s,watt]')
                    times=np.array([number(p[0]) for p in points]);watts=np.array([number(p[1]) for p in points])
                    if times[0]!=0 or times[-1]!=n or np.any(np.diff(times)<=0):raise ValueError('Profilo deve coprire 0–durata con tempi crescenti')
                    if np.any((watts<low)|(watts>high)):raise ValueError('Profilo fuori range')
                    v=np.interp(np.arange(n),times,watts)
                    endpoint=float(watts[-1])
                else:raise ValueError(f'{key}: scegliere centro, profilo o scenari per il range')
                if np.any((v<low)|(v>high)):raise ValueError('Scenario fuori range')
            else:raise ValueError(f'{key}: target kind constant o range richiesto')
            blocks.append({'key':key,'start_s':len(values),'end_s':len(values)+n})
            values.extend(v.tolist())
        outputs.append({'name':scenario,'target':values+[values[-1] if endpoint is None else endpoint],'duration_s':total,'blocks':blocks})
    return outputs
