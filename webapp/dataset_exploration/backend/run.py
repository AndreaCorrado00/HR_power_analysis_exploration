import socket
import uvicorn
from .app import create_app
def find_free_port(host='127.0.0.1'):
    with socket.socket() as s: s.bind((host,0)); return s.getsockname()[1]
def main():
    host='127.0.0.1'; port=find_free_port(host); print(f'Dataset Exploration: http://{host}:{port}',flush=True); uvicorn.run(create_app(),host=host,port=port)
if __name__=='__main__': main()
