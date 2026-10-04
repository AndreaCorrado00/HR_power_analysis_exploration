"""Read-only gap analysis; run from repository root. No interpolation or fitting."""
import csv,json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path.cwd();store=root/'webapp/model_identification_app/storage';out=root/'reports/identification_errors_27a1bad7';m=json.loads(next((store/'runs').glob('*27a1bad7.json')).read_text());failed=json.loads((out/'failed_records.json').read_text());meta={s['id']:s for s in m['dataset']['segments']}
gaps=[];jumps=[];counts={};total=0
for r in failed:
 seg=meta[r['segment_id']];b=(store/'blobs'/seg['sha256']).read_bytes();assert hashlib.sha256(b).hexdigest()==seg['sha256'];d=list(csv.DictReader(b.decode('utf-8-sig').splitlines()));name=Path(r['filename']).name
 t=np.array([float(x['elapsed_seconds']) for x in d]);assert np.isfinite(t).all() and (np.diff(t)>0).all();dt=float(np.median(np.diff(t)));total+=len(t)
 counts[name]={'n':len(t),'dt':dt}
 for i in np.flatnonzero(np.diff(t)>1.5*dt):jumps.append(dict(filename=name,start_s=float(t[i]),end_s=float(t[i+1]),interval_s=float(t[i+1]-t[i]),excess_over_nominal_s=float(t[i+1]-t[i]-dt)))
 for signal,col in [('Potenza','power_w'),('HR','heart_rate_bpm')]:
  y=np.array([float(x[col]) if x[col] else np.nan for x in d]);bad=~np.isfinite(y);edges=np.diff(np.r_[False,bad,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
  for a,z in zip(starts,ends):
   internal=a>0 and z<len(t);span=float(t[z]-t[a-1]) if internal else None
   gaps.append(dict(filename=name,segment_id=r['segment_id'],signal=signal,start_index=int(a),end_index=int(z-1),start_s=float(t[a]),end_s=float(t[z-1]),missing_samples=int(z-a),nominal_missing_s=float((z-a)*dt),internal=bool(internal),anchor_span_s=span,unobserved_s=float(span-dt) if internal else None,crosses_recording_gap=bool(np.any(np.diff(t[max(a-1,0):min(z+1,len(t))])>1.5*dt)),endpoint_change=float(y[z]-y[a-1]) if internal else None))
for name,data in [('gap_events.csv',gaps),('timestamp_gaps.csv',jumps)]:
 with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
summary={'run_id':m['id'],'failed_records':len(failed),'total_samples':total,'sampling_intervals_s':sorted(set(x['dt'] for x in counts.values())),'signals':{},'thresholds':[]}
for signal in ['Potenza','HR']:
 gs=[g for g in gaps if g['signal']==signal];a=np.array([g['missing_samples'] for g in gs]);summary['signals'][signal]={'events':len(gs),'missing_samples':int(a.sum()),'missing_percent':float(100*a.sum()/total),'sample_quantiles_p50_p90_p95_p99_max':np.quantile(a,[.5,.9,.95,.99,1]).tolist(),'edge_events':sum(not g['internal'] for g in gs),'cross_recording_gap_events':sum(g['crosses_recording_gap'] for g in gs),'histogram_samples':{str(v):int((a==v).sum()) for v in sorted(set(a))}}
for threshold in [1,2,3,5,10,30,60]:
 eligible=lambda g:g['internal'] and not g['crosses_recording_gap'] and g['unobserved_s']<=threshold
 row={'max_missing_s':threshold,'signals':{sig:{'events':sum(eligible(g) for g in gaps if g['signal']==sig),'samples':sum(g['missing_samples'] for g in gaps if g['signal']==sig and eligible(g))} for sig in ['Potenza','HR']},'records_all_missing_eligible':sum(all(eligible(g) for g in gaps if g['filename']==name) for name in counts)};summary['thresholds'].append(row)
j=np.array([g['interval_s'] for g in jumps]);summary['timestamp_gaps']={'events':len(jumps),'records':len(set(g['filename'] for g in jumps)),'interval_quantiles_p50_p90_p95_max':np.quantile(j,[.5,.9,.95,1]).tolist(),'total_excess_s':sum(g['excess_over_nominal_s'] for g in jumps)}
(out/'gap_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));print('LONGEST',json.dumps(sorted(gaps,key=lambda g:g['missing_samples'],reverse=True)[:5]));print('EDGES',json.dumps([g for g in gaps if not g['internal']]))
fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained');labels=['1','2','3-5','6-10','11-30','>30'];bounds=[(1,1),(2,2),(3,5),(6,10),(11,30),(31,float('inf'))]
for ax,sig,color in zip(axes,['Potenza','HR'],['#25749b','#c34d42']):
 a=[g['missing_samples'] for g in gaps if g['signal']==sig];v=[sum(lo<=x<=hi for x in a) for lo,hi in bounds];bars=ax.bar(labels,v,color=color);ax.bar_label(bars);ax.set_title(f'{sig}: {len(a)} buchi, {sum(a)} campioni assenti');ax.set_xlabel('Campioni consecutivi mancanti (passo nominale: 1 s)');ax.set_ylabel('Numero di buchi');ax.set_ylim(0,max(v)*1.18);ax.spines[['top','right']].set_visible(False)
fig.suptitle('34 record falliti | Distribuzione dei valori mancanti\nI salti nei timestamp sono conteggiati separatamente',fontsize=13);fig.savefig(out/'gap_distribution.png',dpi=150);plt.close(fig)
(out/'gap_method.md').write_text('Diagnostica descrittiva sui 34 record falliti del run '+m['id']+'.\nUn buco e una sequenza massimale di righe consecutive con valore non finito, separatamente per segnale. Zeri validi non sono mancanti. Nessun ricampionamento, filtro, interpolazione o fitting.\nLunghezza nominale = numero righe mancanti x mediana dt. Durata tra ancore = timestamp valido successivo meno precedente; tempo non osservato riportato = durata tra ancore meno dt nominale. Buchi agli estremi non hanno due ancore.\nSalti di registrazione: dt > 1.5 x mediana dt. Le soglie di recuperabilita sono scenari descrittivi, non un protocollo approvato: richiedono due ancore e nessun salto di registrazione nel tratto. Un record recuperabile in tabella ha tutti i valori mancanti ammissibili secondo la soglia; puo comunque contenere altri salti nei timestamp. Nessuna garanzia di convergenza o accuratezza dopo interpolazione.\nRiproduzione: .venv/Scripts/python.exe reports/identification_errors_27a1bad7/analyze_gaps.py dalla radice repository.\n',encoding='utf-8')
