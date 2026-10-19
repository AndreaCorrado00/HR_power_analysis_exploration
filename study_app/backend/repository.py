"""SQLite index plus atomic, versioned JSON artifacts under athlete UUIDs."""
import hashlib
import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now(): return datetime.now(timezone.utc).isoformat()


def clean(value):
    if hasattr(value,'tolist'): value=value.tolist()
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,datetime): return value.isoformat()
    return value


def encode(value): return json.dumps(clean(value),ensure_ascii=False,allow_nan=False,sort_keys=True).encode('utf-8')
def digest(value): return hashlib.sha256(encode(value)).hexdigest()


class Repository:
    def __init__(self,root):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY,kind TEXT,athlete_id TEXT,path TEXT,created_at TEXT)')
        # Index is authoritative: incomplete staging/orphan files are never listed.
        # Retain them for inspection; no destructive startup cleanup.

    def connect(self): return sqlite3.connect(self.root/'study.sqlite3',timeout=30)

    def create(self,kind,athlete_id,payload,*,key=None):
        key=key or str(uuid4()); key=str(__import__('uuid').UUID(key))
        if kind!='athletes' and self.get(athlete_id)['kind']!='athletes':raise ValueError('Identificativo atleta richiesto')
        allowed={'athletes','imports','workouts','datasets','experiments','jobs','models','prescriptions','predictions','comparisons','diagnostics'}
        if kind not in allowed: raise ValueError('Tipo artefatto non valido')
        aid=key if kind=='athletes' else str(__import__('uuid').UUID(athlete_id))
        obj=clean({**payload,'schema_version':1,'id':key,'athlete_id':aid,'kind':kind,'created_at':now()})
        obj['sha256']=digest(obj)
        relative=Path('athletes')/aid/kind/(key+'.json')
        path=self.root/relative; path.parent.mkdir(parents=True,exist_ok=True)
        with self.lock, self.connect() as db:
            if path.exists(): raise ValueError('Artefatto già presente')
            tmp=path.with_suffix('.tmp'); tmp.write_bytes(encode(obj)); os.replace(tmp,path)
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(key,kind,aid,str(relative),obj['created_at']))
        return obj

    def get(self,key,athlete_id=None):
        with self.connect() as db: row=db.execute('SELECT path,athlete_id FROM artifacts WHERE id=?',(key,)).fetchone()
        if row is None: raise FileNotFoundError('Risorsa non trovata')
        if athlete_id is not None and athlete_id!=row[1]: raise ValueError('Risorsa di un altro atleta')
        obj=json.loads((self.root/row[0]).read_text(encoding='utf-8'))
        expected=obj.get('sha256')
        if expected!=digest({k:v for k,v in obj.items() if k!='sha256'}):
            raise ValueError('Verifica integrità artefatto fallita: nessuna elaborazione eseguita')
        return obj

    def list(self,kind,athlete_id=None):
        query='SELECT id FROM artifacts WHERE kind=?'; args=[kind]
        if athlete_id: query+=' AND athlete_id=?'; args.append(athlete_id)
        with self.connect() as db: ids=db.execute(query+' ORDER BY created_at DESC',args).fetchall()
        return [self.get(x[0]) for x in ids]

    def mutate(self,key,changes):
        with self.lock:
            obj=self.get(key)
            if obj['kind'] not in ('athletes','jobs'): raise ValueError('Artefatto immutabile')
            obj.update(changes); obj['updated_at']=now(); obj.pop('sha256',None);obj['sha256']=digest(obj)
            with self.connect() as db: rel=db.execute('SELECT path FROM artifacts WHERE id=?',(key,)).fetchone()[0]
            path=self.root/rel; tmp=path.with_suffix('.tmp'); tmp.write_bytes(encode(obj)); os.replace(tmp,path)
            return obj

    def create_athlete(self,data):
        data=self.validate_athlete(data)
        return self.create('athletes',None,{**data,'age_recorded_at':now(),'revisions':[]})

    def update_athlete(self,key,data):
        old=self.get(key)
        if old['kind']!='athletes': raise ValueError('Atleta non valido')
        permitted={k:old.get(k) for k in ('first_name','last_name','age','ftp_w')}
        if set(data)-set(permitted): raise ValueError('Campo anagrafico sconosciuto')
        permitted.update(data); permitted=self.validate_athlete(permitted)
        return self.mutate(key,{**permitted,'age_recorded_at':now() if 'age' in data else old['age_recorded_at'],
            'revisions':old['revisions']+[{k:old.get(k) for k in ('first_name','last_name','age','ftp_w','age_recorded_at')}]})

    @staticmethod
    def validate_athlete(data):
        first=str(data.get('first_name','')).strip(); last=str(data.get('last_name','')).strip()
        age=data.get('age'); ftp=data.get('ftp_w')
        if not first or not last or len(first)>100 or len(last)>100: raise ValueError('Nome e cognome obbligatori (massimo 100 caratteri)')
        if isinstance(age,bool) or not isinstance(age,int) or not 1<=age<=120: raise ValueError('Età intera tra 1 e 120 anni')
        if ftp is not None and (not isinstance(ftp,(float,int)) or isinstance(ftp,bool) or not math.isfinite(ftp) or ftp<=0): raise ValueError('FTP positiva o assente')
        return dict(first_name=first,last_name=last,age=age,ftp_w=ftp)
