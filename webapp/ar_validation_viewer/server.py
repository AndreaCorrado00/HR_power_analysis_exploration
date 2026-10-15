"""Read-only, local-network viewer for saved AR validation simulations."""
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
sys.path.insert(0, str(ROOT/'src'))
from power_hr_eda.power_residual_ar.fit import ARModel
from power_hr_eda.power_residual_ar.simulation import stationary_state, simulate_workout, pooled_acf
from power_hr_eda.power_residual_ar.data import Segment, segment_frame, sha256


def acf_comparison(real, simulated, max_lag=60):
    """Within-segment biased ACF; empirical pointwise simulation quantiles."""
    rows = []
    for lag in range(1, min(max_lag, max(map(len, real), default=0)-1)+1):
        observed = pooled_acf(real, lag)
        generated = pooled_acf(simulated, lag)
        finite = generated[np.isfinite(generated)] if generated is not None else np.array([])
        quantiles = np.quantile(finite, [.1, .5, .9]).tolist() if len(finite) else [None]*3
        value = float(observed[0]) if observed is not None and np.isfinite(observed[0]) else None
        rows.append([lag, value, *quantiles, sum(max(0,len(x)-lag) for x in real)])
    return dict(rows=rows)


class ViewerData:
    def __init__(self, run):
        self.run = Path(run).resolve()
        manifest = json.loads((self.run/'manifest.json').read_text(encoding='utf-8'))
        self.manifest = manifest
        self.acf_cache = {}
        self.ids = [str(wid) for wid in manifest['split']['validation']]
        if not self.ids or len(self.ids) != len(set(self.ids)):
            raise ValueError('Validation IDs must be nonempty and unique')
        self.files = {}
        for wid in self.ids:
            if not wid.isdigit() or len(wid) != 12:
                raise ValueError('Expected twelve-digit workout identifiers')
            path = self.run/'validation'/f'{wid}.csv.gz'
            if not path.is_file() or not path.resolve().is_relative_to(self.run):
                raise ValueError(f'Missing validation file: {wid}')
            self.files[wid] = path
        model = ARModel.from_dict(json.loads((self.run/'train_model.json').read_text(encoding='utf-8')))
        self.ar_model = model
        mean, covariance = stationary_state(model)
        self.model = dict(p=model.p, residual_mean_w=float(mean[0]), residual_sd_w=float(np.sqrt(covariance[0,0])),
                          scaling_source='Distribuzione stazionaria AR stimata sul training')

    def catalog(self):
        return dict(model=self.model, workouts=[dict(id=wid,date=datetime.strptime(wid,'%y%m%d%H%M%S').strftime('%d/%m/%Y'))
                                                for wid in self.ids])

    def workout(self, wid):
        frame = pd.read_csv(self.files[wid])  # allowlist lookup, never construct a path from the URL
        columns = ['elapsed_seconds','observed_power_w','prescribed_power_w','simulated_power_w',
                   'observed_residual_w','simulated_residual_w']
        values = frame[columns].to_numpy(float)
        if not len(values) or not np.isfinite(values).all() or np.any(np.diff(values[:,0]) <= 0):
            raise ValueError('Expected finite values and strictly increasing elapsed times')
        mean, sd = self.model['residual_mean_w'], self.model['residual_sd_w']
        frame['z_observed'] = (frame.observed_residual_w-mean)/sd
        frame['z_simulated'] = (frame.simulated_residual_w-mean)/sd
        segments = []
        # Preserve existing segments, and also guard against timestamp gaps in an artifact.
        boundary = np.r_[True, (np.diff(values[:,0]) != 1)
                         | (frame.segment_id.to_numpy()[1:] != frame.segment_id.to_numpy()[:-1])]
        for _, part in frame.groupby(np.cumsum(boundary),sort=False):
            segments.append(dict(rows=part[columns+['z_observed','z_simulated']].to_numpy(float).tolist()))
        return dict(id=wid,samples=len(frame),start_s=float(values[0,0]),end_s=float(values[-1,0]),segments=segments,
                    acf=self.workout_acf(wid, segments))

    def workout_acf(self, wid, segments):
        if wid in self.acf_cache:
            return self.acf_cache[wid]
        if 'source_run' not in self.manifest:
            return dict(rows=[], paths=0, unavailable='Metadati sorgente assenti')
        source = json.loads((Path(self.manifest['source_run'])/'manifest.json').read_text(encoding='utf-8'))
        record = next(r for r in source['records'] if r['workout_id'] == wid)
        if sha256(record['path']) != record['sha256']:
            raise ValueError('Source changed since fitting')
        diagnostic, _ = segment_frame(pd.read_csv(record['path']), wid, split_at_prescription=True)
        continuous = []
        for i, segment in enumerate(segments):
            a = np.asarray(segment['rows'])
            continuous.append(Segment(wid,i,a[:,0],a[:,4],a[:,2]))
        config = self.manifest['configuration']
        generated = simulate_workout(self.ar_model,continuous,seed=config['seed'],paths=config['paths'])
        for segment, paths in zip(segments, generated):
            if not np.allclose(paths[0], np.asarray(segment['rows'])[:,5], rtol=1e-10, atol=1e-10):
                raise ValueError('Regenerated simulation differs from saved trajectory')
        times = np.concatenate([s.time for s in continuous])
        paths = np.concatenate(generated,axis=1)
        real, simulated = [], []
        for part in diagnostic:
            indices = np.searchsorted(times,part.time)
            if np.any(indices >= len(times)) or not np.array_equal(times[indices],part.time):
                raise ValueError('Diagnostic samples do not match saved validation')
            real.append(part.residual)
            simulated.append(paths[:,indices])
        result = acf_comparison(real,simulated)
        result.update(paths=config['paths'],seed=config['seed'])
        self.acf_cache[wid] = result
        return result


def create_server(run, host='0.0.0.0', port=8767):
    store = ViewerData(run)
    assets = {'/': ('index.html','text/html; charset=utf-8'),
              '/app.js': ('app.js','text/javascript; charset=utf-8'),
              '/style.css': ('style.css','text/css; charset=utf-8'),
              '/vendor/echarts.min.js': ('vendor/echarts.min.js','text/javascript; charset=utf-8')}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            try:
                if path == '/api/workouts':
                    payload = store.catalog()
                elif path.startswith('/api/workouts/'):
                    payload = store.workout(path.removeprefix('/api/workouts/'))
                elif path in assets:
                    filename, content_type = assets[path]
                    self.send_content((APP/filename).read_bytes(),content_type)
                    return
                else:
                    self.send_error(404)
                    return
                self.send_content(json.dumps(payload,allow_nan=False,separators=(',',':')).encode(), 'application/json')
            except KeyError:
                self.send_error(404)
            except (ValueError, OSError):
                self.send_error(500, 'Validation artifact unavailable or invalid')

        def send_content(self, body, content_type):
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'reports/power_residual_ar_simulation')
    parser.add_argument('--host',default='0.0.0.0')
    parser.add_argument('--port',type=int,default=8767)
    args = parser.parse_args()
    server = create_server(args.run,args.host,args.port)
    print(f'Locale: http://127.0.0.1:{server.server_port}',flush=True)
    if args.host == '0.0.0.0':
        for ip in sorted(set(socket.gethostbyname_ex(socket.gethostname())[2])):
            if not ip.startswith('127.'):
                print(f'Rete locale: http://{ip}:{server.server_port}',flush=True)
    print('Solo lettura; Ctrl+C per arrestare.',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
