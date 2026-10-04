import csv,json,hashlib,math
from pathlib import Path
root=Path.cwd(); s=root/'webapp/model_identification_app/storage'; mp=next((s/'runs').glob('*27a1bad7.json'));m=json.loads(mp.read_text());out=root/'reports'/('identification_errors_'+m['id'][:8]);out.mkdir(exist_ok=True,parents=True)
meta={x['id']:x for x in m['dataset']['segments']}; rows=[]; originals=[]
for p in (s/'runs'/m['id']).glob('*.json'):
 r=json.loads(p.read_text())
 if r['status']!='failed':continue
 seg=meta[r['segment_id']];data=(s/'blobs'/seg['sha256']).read_bytes();assert hashlib.sha256(data).hexdigest()==seg['sha256']
 d=list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
 counts={c:sum(not x[c] or not math.isfinite(float(x[c])) for x in d) for c in ['elapsed_seconds','power_w','heart_rate_bpm']}
 rows.append(dict(filename=Path(r['filename']).name,segment_id=r['segment_id'],samples=len(d),missing_power=counts['power_w'],missing_hr=counts['heart_rate_bpm'],missing_time=counts['elapsed_seconds'],error=r['error'],result_path=str(p.relative_to(root)),source_sha256=seg['sha256']))
 originals.append(r)
rows.sort(key=lambda r:r['filename']);assert len(rows)==m['progress']['failed']==34
with (out/'failed_records.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(out/'failed_records.json').write_text(json.dumps(originals,indent=2,ensure_ascii=False),encoding='utf-8')
print('EXPORTED',out,flush=True)
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
selected=['106_260728062911.csv','002_250518083010.csv']
for name in selected:
 row=next(r for r in rows if r['filename']==name);seg=meta[row['segment_id']]
 with (s/'blobs'/seg['sha256']).open() as f:d=list(csv.DictReader(f))
 t,p,h=[np.array([float(x[c]) if x[c] else np.nan for x in d]) for c in ['elapsed_seconds','power_w','heart_rate_bpm']];t=t/60
 badp=~np.isfinite(p);badh=~np.isfinite(h);bad=badp|badh
 fig,axs=plt.subplots(3,2,figsize=(13,8),layout='constrained',gridspec_kw={'height_ratios':[2,2,1]})
 center=float(t[np.flatnonzero(bad)[0]]);bounds=[(float(t[0]),float(t[-1])),(max(t[0],center-1),min(t[-1],center+1))]
 for col,(lo,hi) in enumerate(bounds):
  axs[0,col].plot(t,p,color='#25749b',lw=.7);axs[1,col].plot(t,h,color='#c34d42',lw=.8)
  axs[0,col].set_title('Intera attivita' if col==0 else 'Zoom: primo campione mancante (+/- 1 min)')
  axs[2,col].scatter(t[badp],np.ones(badp.sum()),marker='|',s=160,color='#25749b');axs[2,col].scatter(t[badh],np.zeros(badh.sum()),marker='|',s=160,color='#c34d42')
  axs[2,col].set_yticks([0,1],['HR assente','Potenza assente']);axs[2,col].set_ylim(-.6,1.6);axs[2,col].set_xlabel('Tempo trascorso (min)')
  for ax in axs[:,col]:ax.set_xlim(lo,hi);ax.grid(alpha=.2)
  axs[0,col].set_ylabel('Potenza (W)');axs[1,col].set_ylabel('HR (bpm)')
  for ax in axs[:2,col]:
   for tx in t[bad & (t>=lo)&(t<=hi)]:ax.axvline(tx,color='#a53aa5',alpha=.22,lw=.8)
 fig.suptitle(f'{name} | Identificazione bloccata prima del fitting\n{len(t):,} campioni; potenza mancante: {badp.sum()}; HR mancante: {badh.sum()}\nDati originali, senza interpolazione; nessuna predizione disponibile',fontsize=13)
 dest=out/(Path(name).stem+'_diagnostic.png');fig.savefig(dest,dpi=145);plt.close(fig);print('PNG',dest,flush=True)
(out/'README.md').write_text(f'# Diagnostica errori identificazione\n\nRun `{m["id"]}`; manifest `{mp.relative_to(root)}`.\n34 fallimenti su 92 record train. Tutti bloccati dal controllo di finitezza prima del fitting; nessuna valutazione fuori campione.\n\nCSV: inventario completo con conteggi verificati sui blob originali (SHA-256 verificato). JSON: record falliti salvati, senza alterazioni.\n\nGrafici: selezione intenzionale di un caso con un solo dato potenza mancante (106) e un caso con entrambi i segnali incompleti (002); non rappresentano una selezione statistica. Linee viola: tempi con almeno un dato mancante. Zoom sul primo campione mancante, +/- 1 minuto. Nessun filtro, interpolazione, rifitting o modifica dei dati.\n\nIl messaggio "Servono almeno 4 osservazioni finite nel segmento" copre sia meno di 4 campioni sia qualsiasi valore non finito: qui tutti i record hanno oltre 4 campioni.\n',encoding='utf-8')
print('DONE')
