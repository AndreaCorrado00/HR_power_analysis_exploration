"""Distribution of recording intervals across all original activities; no cleaning."""
import csv,io,json,zipfile,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path.cwd();source=root/'dataset/cleaned_only_road_activities_csv.zip';out=root/'reports/timestamp_gap_distribution';out.mkdir(parents=True,exist_ok=True)
events=[];activities=[];bins=[(1,5),(5,10),(10,30),(30,60),(60,120),(120,300),(300,600),(600,float('inf'))]
with zipfile.ZipFile(source) as z:
 m=json.loads(z.read('manifest.json'));assert hashlib.sha256((root/'dataset/cleaned_only_road_activieties.zip').read_bytes()).hexdigest()==m['source_archive_sha256']
 for seg in m['segments']:
  data=z.read(seg['csv_file']);assert hashlib.sha256(data).hexdigest()==seg['csv_sha256'];rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))));t=np.array([float(r['elapsed_seconds']) for r in rows]);dt=np.diff(t);assert np.isfinite(t).all() and np.all(dt>0);nominal=float(np.median(dt));assert nominal==1
  gaps=dt>1.5*nominal;excess=float(np.sum(dt[gaps]-nominal));name=Path(seg['csv_file']).name
  activities.append(dict(filename=name,samples=len(t),duration_s=float(t[-1]-t[0]),gaps=int(gaps.sum()),max_interval_s=float(dt.max()),unrecorded_s=excess,unrecorded_percent=100*excess/(t[-1]-t[0])))
  for i in np.flatnonzero(gaps):events.append(dict(filename=name,left_timestamp=rows[i]['timestamp'],right_timestamp=rows[i+1]['timestamp'],start_s=float(t[i]),end_s=float(t[i+1]),interval_s=float(dt[i]),missing_nominal_seconds=float(dt[i]-nominal),position_percent=100*((t[i]+t[i+1])/2-t[0])/(t[-1]-t[0])))
def write(name,rows):
 with (out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
write('timestamp_events.csv',events);write('activity_summary.csv',activities)
d=np.array([e['interval_s'] for e in events]);total_duration=sum(a['duration_s'] for a in activities);total_missing=sum(a['unrecorded_s'] for a in activities);total_samples=sum(a['samples'] for a in activities)
distribution=[dict(interval=f'({lo}, {hi}]',events=sum(lo<e['interval_s']<=hi for e in events),activities=len({e['filename'] for e in events if lo<e['interval_s']<=hi}),unrecorded_s=sum(e['missing_nominal_seconds'] for e in events if lo<e['interval_s']<=hi)) for lo,hi in bins]
thresholds=[dict(threshold_s=s,events_gt=sum(e['interval_s']>s for e in events),activities_excluded=sum(a['max_interval_s']>s for a in activities),activities_retained=sum(a['max_interval_s']<=s for a in activities),recorded_samples_discarded=sum(a['samples'] for a in activities if a['max_interval_s']>s),discarded_sample_percent=100*sum(a['samples'] for a in activities if a['max_interval_s']>s)/total_samples) for s in [5,10,30,60,120,300,600,1200]]
summary=dict(activities=len(activities),recorded_samples=total_samples,activities_with_gaps=sum(a['gaps']>0 for a in activities),gap_events=len(events),interval_quantiles=dict(zip(['min','p25','p50','p75','p90','p95','p99','max'],np.quantile(d,[0,.25,.5,.75,.9,.95,.99,1]).tolist())),elapsed_hours=total_duration/3600,missing_hours=total_missing/3600,missing_percent=100*total_missing/total_duration,distribution=distribution,thresholds=thresholds,longest=sorted(events,key=lambda e:e['interval_s'],reverse=True)[:5],method='All 131 original activities; gap if dt>1.5*median dt; nominal dt=1s in all. Thresholds refer to full timestamp interval. Missing duration=dt-1s. Not classified as pause/dropout.')
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');write('distribution.csv',distribution);write('thresholds.csv',thresholds)
fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained');labels=['2–5','6–10','11–30','31–60','61–120','121–300','301–600','>600'];v=[r['events'] for r in distribution];bars=axs[0].bar(labels,v,color='#2878a6');axs[0].bar_label(bars);axs[0].set_xlabel('Distanza fra timestamp consecutivi (s)');axs[0].set_ylabel('Numero di intervalli');axs[0].tick_params(axis='x',rotation=35);axs[0].set_ylim(0,max(v)*1.16)
bars=axs[1].bar([str(x['threshold_s']) for x in thresholds],[x['activities_retained'] for x in thresholds],color='#639073');axs[1].bar_label(bars);axs[1].axhline(131,color='gray',ls='--');axs[1].set_ylim(0,145);axs[1].set_xlabel('Soglia di esclusione dell’intera attivita (s)');axs[1].set_ylabel('Attivita conservate (su 131)');fig.suptitle('Dataset originale completo | Intervalli senza registrazioni\nPossibili pause incluse; nessuna trasformazione dei dati',fontsize=13);fig.savefig(out/'distribution.png',dpi=145);plt.close(fig)
print(json.dumps(summary,indent=2))
