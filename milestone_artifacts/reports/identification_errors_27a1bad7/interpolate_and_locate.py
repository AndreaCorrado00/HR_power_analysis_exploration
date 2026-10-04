"""Linear interpolation of eligible failed records, plus locations of unresolved gaps.
Run from repository root. Source blobs remain immutable; no refit or app import.
"""
import csv,json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path.cwd();report=root/'reports/identification_errors_27a1bad7';store=root/'webapp/model_identification_app/storage';out=root/'data/processed/identification_27a1bad7_interpolated_lt5s';out.mkdir(parents=True,exist_ok=True)
m=json.loads(next((store/'runs').glob('*27a1bad7.json')).read_text());meta={s['id']:s for s in m['dataset']['segments']}
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
gaps=read(report/'gap_events.csv');jumps=read(report/'timestamp_gaps.csv');records=read(report/'failed_records.csv');changes=[];locations=[];summary=[];hashes={}
def eligible(g):return g['internal']=='True' and g['crosses_recording_gap']=='False' and float(g['unobserved_s'])<5
for rec in sorted(records,key=lambda r:r['filename']):
 name=rec['filename'];seg=meta[rec['segment_id']];source=store/'blobs'/seg['sha256'];b=source.read_bytes();assert hashlib.sha256(b).hexdigest()==seg['sha256'];hashes[str(source)]=seg['sha256'];d=list(csv.DictReader(b.decode('utf-8-sig').splitlines()));fields=list(d[0]);t=np.array([float(x['elapsed_seconds']) for x in d]);duration=t[-1]-t[0];gs=[g for g in gaps if g['filename']==name];js=[j for j in jumps if j['filename']==name];ok=all(eligible(g) for g in gs)
 summary.append(dict(filename=name,segment_id=rec['segment_id'],duration_s=float(duration),values_interpolated=ok,missing_events=len(gs),blocking_missing_events=sum(not eligible(g) for g in gs),timestamp_gaps=len(js),all_analyzed_anomalies_resolved=ok and not js,source_sha256=seg['sha256']))
 if ok:
  for g in gs:
   col='power_w' if g['signal']=='Potenza' else 'heart_rate_bpm';a=int(g['start_index']);z=int(g['end_index'])+1;y0=float(d[a-1][col]);y1=float(d[z][col]);vals=np.interp(t[a:z],[t[a-1],t[z]],[y0,y1])
   for i,v in zip(range(a,z),vals):
    changes.append(dict(filename=name,row_index=i,elapsed_seconds=float(t[i]),column=col,original=d[i][col],interpolated=float(v),left_anchor_s=float(t[a-1]),right_anchor_s=float(t[z])))
    d[i][col]=format(float(v),'.17g')
  with (out/name).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(d)
  check=read(out/name);orig=list(csv.DictReader(b.decode('utf-8-sig').splitlines()));assert len(check)==len(orig)
  allowed={(c['row_index'],c['column']) for c in changes if c['filename']==name}
  for i,(old,new) in enumerate(zip(orig,check)):
   for col in fields:
    if (i,col) not in allowed:assert old[col]==new[col]
   assert all(np.isfinite(float(new[col])) for col in ['power_w','heart_rate_bpm'])
  summary[-1]['processed_sha256']=hashlib.sha256((out/name).read_bytes()).hexdigest()
 for g in gs:
  start=float(g['start_s']);end=float(g['end_s']);pct=100*((start+end)/2-t[0])/duration
  reason='interpolated' if ok else ('short_but_record_deferred' if eligible(g) else ('edge' if g['internal']=='False' else ('recording_gap' if g['crosses_recording_gap']=='True' else 'length_ge_5s')))
  locations.append(dict(filename=name,signal=g['signal'],type='missing_value',start_min=start/60,end_min=end/60,start_percent=100*(start-t[0])/duration,end_percent=100*(end-t[0])/duration,location='inizio (0-10%)' if pct<10 else ('fine (90-100%)' if pct>=90 else 'centrale (10-90%)'),missing_samples=g['missing_samples'],anchor_span_s=g['anchor_span_s'],reason=reason,resolved=ok))
 for j in js:
  start=float(j['start_s']);end=float(j['end_s']);pct=100*((start+end)/2-t[0])/duration
  locations.append(dict(filename=name,signal='Timestamp',type='recording_gap',start_min=start/60,end_min=end/60,start_percent=100*(start-t[0])/duration,end_percent=100*(end-t[0])/duration,location='inizio (0-10%)' if pct<10 else ('fine (90-100%)' if pct>=90 else 'centrale (10-90%)'),missing_samples='',anchor_span_s=j['interval_s'],reason='recording_gap_not_interpolated',resolved=False))
def write(p,data):
 fields=list(dict.fromkeys(k for r in data for k in r))
 with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
write(out/'interpolation_log.csv',changes);write(report/'recovery_status.csv',summary);write(report/'gap_locations.csv',locations)
protocol={'source_run':m['id'],'scope':'34 previously failed train records only','method':'linear interpolation in elapsed_seconds at existing rows only','threshold':'strictly <5 seconds; anchor span minus nominal dt (1s)','eligibility':'all missing-value runs in record internal, below threshold, no recording gap between anchors','recording_gaps':'preserved, no rows inserted; separately flagged, including in interpolated files','unchanged':'all original finite values, columns, timestamps and row counts; immutable source blobs','refit':False,'app_import':False,'records':summary,'changed_cells':len(changes)}
(out/'manifest.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
for path,sha in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
remaining=[x for x in locations if not x['resolved']];names=[r['filename'] for r in summary if not r['all_analyzed_anomalies_resolved']]
fig,ax=plt.subplots(figsize=(13,11),layout='constrained');colors={'Potenza':'#25749b','HR':'#c34d42','Timestamp':'#999999'}
for x in remaining:
 y=names.index(x['filename']);offset={'Potenza':-.2,'HR':0,'Timestamp':.2}[x['signal']];a=x['start_percent'];b=x['end_percent'];ax.plot([a,b],[y+offset,y+offset],color=colors[x['signal']],lw=2);ax.scatter([(a+b)/2],[y+offset],color=colors[x['signal']],s=10,marker='|' if x['signal']!='Timestamp' else 's')
ax.set_yticks(range(len(names)),[n.replace('.csv','')+(' *' if next(r for r in summary if r['filename']==n)['values_interpolated'] else '') for n in names],fontsize=8);ax.invert_yaxis();ax.set_xlim(-1,101);ax.axvspan(0,10,color='#eeeeee');ax.axvspan(90,100,color='#eeeeee');ax.set_xlabel('Posizione nel tempo trascorso dell’attivita (%)');ax.grid(axis='x',alpha=.2)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([0],[0],color=c,lw=3,label=k) for k,c in colors.items()],loc='upper center',bbox_to_anchor=(.5,1.04),ncol=3)
ax.set_title('Posizione dei buchi ancora irrisolti\n* Valori mancanti interpolati; restano salti nei timestamp',pad=42);fig.savefig(report/'remaining_gap_locations.png',dpi=150);plt.close(fig)
from collections import Counter
stats={'interpolated_records':[r['filename'] for r in summary if r['values_interpolated']],'changed_cells':len(changes),'resolved_missing_events':sum(x['resolved'] for x in locations),'remaining_missing_locations':dict(Counter(x['location'] for x in remaining if x['type']=='missing_value')),'remaining_blocking_missing_locations':dict(Counter(x['location'] for x in remaining if x['type']=='missing_value' and x['reason']!='short_but_record_deferred')),'recording_gap_locations':dict(Counter(x['location'] for x in remaining if x['type']=='recording_gap')),'verified':'Source hashes unchanged; only logged missing cells changed; output row counts and all other cells identical; all processed signal values finite'}
(report/'recovery_summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8');print(json.dumps(stats,indent=2))
