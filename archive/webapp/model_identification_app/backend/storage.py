"""Atomic JSON metadata and content-addressed immutable source blobs."""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid


def sha(data):
    return hashlib.sha256(data).hexdigest()


def slug(text):
    return re.sub(r'[^a-zA-Z0-9_-]+', '-', text).strip('-')[:60] or 'dataset'


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        for folder in ['datasets','blobs','runs','archived_manifests']:
            (self.root/folder).mkdir(parents=True, exist_ok=True)

    def path(self, collection, key):
        if collection not in {'datasets','runs','archived_manifests','blobs'} or not re.fullmatch(r'[a-zA-Z0-9_-]+', key):
            raise ValueError('Identificativo non valido')
        return self.root/collection/(key+'.json')

    def write_path(self, path, value):
        data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        with self.lock:
            temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
            with temp.open('w',encoding='utf-8') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)

    def write(self, collection, key, value):
        self.write_path(self.path(collection,key),value)

    def read(self, collection, key):
        with self.lock:
            return json.loads(self.path(collection,key).read_text(encoding='utf-8'))

    def list(self, collection):
        # Windows readers can otherwise prevent atomic replacement by the worker.
        with self.lock:
            return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((self.root/collection).glob('*.json'))]

    def blob(self, data):
        digest = sha(data)
        path = self.root/'blobs'/digest
        with self.lock:
            if not path.exists():
                with path.open('xb') as f: f.write(data)
        return digest

    def read_blob(self, digest):
        if not re.fullmatch('[a-f0-9]{64}', digest): raise ValueError('Hash non valido')
        data = (self.root/'blobs'/digest).read_bytes()
        if sha(data) != digest: raise ValueError('Integrità del CSV non verificata')
        return data
