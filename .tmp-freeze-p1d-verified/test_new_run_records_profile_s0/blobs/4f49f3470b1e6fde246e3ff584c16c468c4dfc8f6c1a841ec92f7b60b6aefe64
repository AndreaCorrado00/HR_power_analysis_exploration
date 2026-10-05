"""Run one local service per storage directory; no automatic browser side effects."""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import socket

import uvicorn

from .app import APP_ROOT, create_app


@contextmanager
def exclusive_storage(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.service.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise SystemExit('Questo storage è già aperto da un altro servizio.') from exc
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt': msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766,help='0 per scegliere una porta libera')
    parser.add_argument('--storage',type=Path,default=APP_ROOT/'storage')
    args=parser.parse_args()
    port=args.port
    if port==0:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    if not (APP_ROOT/'dist/index.html').exists():
        raise SystemExit('Frontend non compilato: eseguire start.ps1 -Setup')
    with exclusive_storage(args.storage.resolve()):
        print(f'HR / Power: http://127.0.0.1:{port}',flush=True)
        print(f'Storage: {args.storage.resolve()}',flush=True)
        uvicorn.run(create_app(args.storage),host='127.0.0.1',port=port)


if __name__=='__main__': main()
