import argparse
from contextlib import contextmanager
from pathlib import Path
import os
import socket
import webbrowser
import uvicorn
from .app import create_app


@contextmanager
def exclusive(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.service.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise SystemExit('Storage già aperto da un altro servizio')
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            if os.name=='nt':lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8770)
    parser.add_argument('--storage',type=Path,default=Path(__file__).parents[2]/'storage');parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    with exclusive(args.storage.resolve()):
        if args.port==0:
            with socket.socket() as s:s.bind(('127.0.0.1',0));args.port=s.getsockname()[1]
        print(f'Studio HR · Power: http://127.0.0.1:{args.port}',flush=True)
        if args.open:webbrowser.open(f'http://127.0.0.1:{args.port}')
        uvicorn.run(create_app(args.storage),host='127.0.0.1',port=args.port)


if __name__=='__main__':main()
