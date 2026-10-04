"""Descriptive split simulation on original CSVs; no dataset transformation."""
import csv,io,json,zipfile,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path.cwd();out=root/'reports/activity_split_simulation';out.mkdir(parents=True,exist_ok=True)
segments=[];acts=[];comparisons=[];total_samples=0
with zipfile.ZipFile(root/'dataset/cleaned_only_road_activities_csv.zip') as z:
 m=json.loads(z.read('manifest.json'));assert hashlib.sha256((root/'dataset/cleaned_only_road_activieties.zip').read_bytes()).hexdigest()==m['source_archive_sha256']
 for entry in m['segments']:
  blob=z.read(entry['csv_file']);assert hashlib.sha256(blob).hexdigest()==entry['csv_sha256'];rows=list(csv.DictReader(io.StringIO(blob.decode('utf-8-sig'))));t=np.array([float(r['elapsed_seconds']) for r in rows]);dt=np.diff(t);name=Path(entry['csv_file']).name;total_samples+=len(rows)
  def missing(c):return np.array([not r[c] or not np.isfinite(float(r[c])) for r in rows])
  pm=missing('power_w');hm=missing('heart_rate_bpm')
  for threshold in [10,30,60]:
   bounds=np.r_[0,np.flatnonzero(dt>threshold)+1,len(t)];local=[]
   for k,(a,b) in enumerate(zip(bounds[:-1],bounds[1:]),1):
    row=dict(filename=name,activity_id=entry['activity_id'],segment=k,first_row=int(a),last_row=int(b-1),samples=int(b-a),start_s=float(t[a]),end_s=float(t[b-1]),duration_s=float(t[b-1]-t[a]),missing_power=int(pm[a:b].sum()),missing_hr=int(hm[a:b].sum()),remaining_timestamp_gaps=int((dt[a:b-1]>1.5).sum()),preceding_gap_s=float(dt[a-1]) if a else None)
    local.append(row)
   if threshold==10:
    segments.extend(local);acts.append(dict(filename=name,segments=len(local),original_samples=len(rows),duration_s=float(t[-1]-t[0]),longest_segment_s=max(r['duration_s'] for r in local)))
   comparisons.extend(dict(threshold_s=threshold,**r) for r in local)
assert sum(s['samples'] for s in segments)==total_samples
for name,data in [('segments_gt10s.csv',segments),('activities.csv',acts)]:
 with (out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
d=np.array([s['duration_s'] for s in segments]);bins=[(0,60),(60,300),(300,600),(600,1200),(1200,1800),(1800,3600),(3600,float('inf'))];hist=[]
for lo,hi in bins:
 ss=[s for s in segments if lo<=s['duration_s']<hi];hist.append(dict(min_seconds=lo,max_seconds=hi if np.isfinite(hi) else None,segments=len(ss),samples=sum(s['samples'] for s in ss),sample_percent=100*sum(s['samples'] for s in ss)/total_samples))
retention=[]
for threshold in [10,30,60]:
 for minimum in [0,60,300,600,1200,1800]:
  ss=[s for s in comparisons if s['threshold_s']==threshold and s['duration_s']>=minimum];retention.append(dict(split_threshold_s=threshold,min_duration_s=minimum,segments=len(ss),activities=len({s['filename'] for s in ss}),samples=sum(s['samples'] for s in ss),sample_percent=100*sum(s['samples'] for s in ss)/total_samples,missing_power=sum(s['missing_power'] for s in ss),missing_hr=sum(s['missing_hr'] for s in ss)))
summary=dict(original_activities=len(acts),original_samples=total_samples,split_threshold_s=10,segments=len(segments),activities_split=sum(a['segments']>1 for a in acts),segments_per_activity_quantiles=dict(zip(['min','median','p90','max'],np.quantile([a['segments'] for a in acts],[0,.5,.9,1]).tolist())),duration_minutes_quantiles=dict(zip(['min','p25','median','p75','p90','p95','max'],(np.quantile(d,[0,.25,.5,.75,.9,.95,1])/60).tolist())),duration_bins=hist,retention=retention,segments_with_missing_signals=sum(s['missing_power']>0 or s['missing_hr']>0 for s in segments),segments_with_remaining_timestamp_gaps=sum(s['remaining_timestamp_gaps']>0 for s in segments),most_fragmented=sorted(acts,key=lambda a:a['segments'],reverse=True)[:5],method='Split before first sample after dt>10s. Duration=last-first timestamp; zero for singleton. Original samples partitioned exactly once. No interpolation, trimming, or model fitting. Percentages of all original recorded samples, including missing P/HR.')
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained');labels=['<1','1–5','5–10','10–20','20–30','30–60','>=60'];v=[r['segments'] for r in hist];bars=axs[0].bar(labels,v,color='#2878a6');axs[0].bar_label(bars);axs[0].set_ylim(0,max(v)*1.2);axs[0].set_xlabel('Durata del tratto (min), estremo superiore escluso');axs[0].set_ylabel('Numero di tratti')
sel=[r for r in retention if r['split_threshold_s']==10];bars=axs[1].bar([str(r['min_duration_s']//60) for r in sel],[r['sample_percent'] for r in sel],color='#639073');axs[1].bar_label(bars,fmt='%.1f%%');axs[1].set_ylim(0,115);axs[1].set_ylabel('Campioni originali conservati (%)');axs[1].set_xlabel('Durata minima ammessa (min)');fig.suptitle('Simulazione: split sui salti temporali >10 s\n131 attivita originali; nessuna trasformazione applicata',fontsize=13);fig.savefig(out/'split_distribution.png',dpi=145);plt.close(fig)
print(json.dumps(summary,indent=2))
