import hashlib
import io
import os
import stat
import zipfile
from pathlib import PurePosixPath
from .preprocessing import prepare_workout

MAX_UPLOAD=2*1024**3
MAX_EXPANDED=10*1024**3


def unpack_upload(name,content):
    if len(content)>MAX_UPLOAD: raise ValueError('Upload oltre 2 GiB')
    suffix=PurePosixPath(name).suffix.lower()
    if suffix=='.fit': return [(PurePosixPath(name).name,content)]
    if suffix!='.zip': raise ValueError('Formati attività supportati: FIT e ZIP di FIT')
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        infos=z.infolist()
        if len(infos)>20000 or sum(x.file_size for x in infos)>MAX_EXPANDED: raise ValueError('Archivio oltre i limiti')
        for x in infos:
            path=PurePosixPath(x.filename.replace('\\','/'))
            if path.is_absolute() or '..' in path.parts or ':' in str(path) or stat.S_ISLNK(x.external_attr>>16) or x.flag_bits&1:
                raise ValueError('Percorso ZIP, link o cifratura non consentiti')
            if not x.is_dir() and path.suffix.lower()!='.fit': raise ValueError('ZIP deve contenere soltanto FIT; archivi annidati non supportati')
        return [(x.filename,z.read(x)) for x in infos if not x.is_dir()]


def import_files(repo,athlete_id,uploads):
    with repo.lock:
        return _import_files(repo,athlete_id,uploads)


def _import_files(repo,athlete_id,uploads):
    athlete=repo.get(athlete_id); existing=repo.list('workouts',athlete_id)
    revisions=repo.list('datasets',athlete_id)
    active_ids=list(revisions[0]['workout_ids']) if revisions else []
    hashes={w['raw_sha256'] for w in existing}; identities={w['start_time']:w['raw_sha256'] for w in existing}
    outcomes=[]; added=[]
    for filename,content in uploads:
        try: entries=unpack_upload(filename,content)
        except (ValueError,zipfile.BadZipFile,RuntimeError) as exc:
            outcomes.append(dict(file=filename,status='failed',reason=str(exc)));continue
        for name,raw in entries:
            h=hashlib.sha256(raw).hexdigest()
            if h in hashes: outcomes.append(dict(file=name,status='duplicate'));continue
            path=repo.root/'athletes'/athlete_id/'raw'/h/'source.fit';path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():
                staging=path.with_suffix('.tmp');staging.write_bytes(raw);os.replace(staging,path)
            try:
                prepared=prepare_workout(path,athlete.get('ftp_w'))
                if prepared['start_time'] in identities: raise ValueError('Conflitto: stessa data iniziale, contenuto diverso; originale preservato, nessuna sostituzione')
                w=repo.create('workouts',athlete_id,{**prepared,'source_name':name,'raw_sha256':h,'raw_path':str(path.relative_to(repo.root))})
                added.append(w['id']);hashes.add(h);identities[w['start_time']]=h
                outcomes.append(dict(file=name,status='imported',workout_id=w['id']))
            except (ValueError,KeyError,TypeError) as exc: outcomes.append(dict(file=name,status='failed',reason=str(exc)))
    current=active_ids+added
    revision=repo.create('datasets',athlete_id,{'workout_ids':current,'ftp_w':athlete.get('ftp_w')})
    return repo.create('imports',athlete_id,{'outcomes':outcomes,'added':added,'dataset_revision_id':revision['id']})
