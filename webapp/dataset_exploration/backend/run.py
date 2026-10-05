import socket
import argparse
import threading
import webbrowser
import uvicorn
from .app import create_app
def find_free_port(host='127.0.0.1'):
    with socket.socket() as s: s.bind((host,0)); return s.getsockname()[1]
def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args(argv)
    host='127.0.0.1'; port=args.port or find_free_port(host); url=f'http://{host}:{port}'
    print(f'Dataset Exploration: {url}',flush=True)
    threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    uvicorn.run(create_app(),host=host,port=port)
if __name__=='__main__': main()
