"""Package the combined split CSV as one CSV per segment, for the app importer."""
import csv,io,json,hashlib,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 source=ROOT/'dataset/road_segments_gt10s_min5min.csv';dest=source.with_suffix('.zip');parent=json.loads(source.with_suffix('.manifest.json').read_text(encoding='utf-8'))
 if dest.exists():raise ValueError('Output already exists')
 h=hashlib.sha256()
 with source.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 assert h.hexdigest()==parent['output_sha256']
 metas={s['segment_id']:s for s in parent['segments']};entries=[];expected=hashlib.sha256();total=0
 def add(z,name,blob):
  info=zipfile.ZipInfo(name,date_time=(2026,9,29,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,blob)
 with source.open(encoding='utf-8',newline='') as f,zipfile.ZipFile(dest,'x') as z:
  reader=csv.DictReader(f);fields=reader.fieldnames;current=None;buffer=[]
  def flush():
   if not buffer:return
   meta=metas[current];assert len(buffer)==meta['samples'];times=[float(r['elapsed_seconds']) for r in buffer];assert times[0]==0 and all(b>a for a,b in zip(times,times[1:]));assert {r['activity_id'] for r in buffer}=={meta['activity_id']}
   stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(buffer);blob=stream.getvalue().encode();name='segments/'+Path(meta['source_file']).stem+f'_segment_{meta["segment_number"]:03d}.csv';add(z,name,blob)
   warnings=[]
   if meta['missing_power']:warnings.append('missing_power')
   if meta['missing_hr']:warnings.append('missing_hr')
   gaps=sum(b-a>1.5 for a,b in zip(times,times[1:]))
   if gaps:warnings.extend(['recording_gaps','irregular_sampling'])
   entries.append(dict(meta,csv_file=name,csv_sha256=sha(blob),kind='segment',duration_group='unknown',empirical_label='unknown',warnings=warnings,quality=dict(missing_power_samples=meta['missing_power'],missing_hr_samples=meta['missing_hr'],gap_count=gaps,max_gap_seconds=max(b-a for a,b in zip(times,times[1:])))))
  for r in reader:
   if current!=r['segment_id']:
    flush();buffer=[];current=r['segment_id']
   buffer.append(r);expected.update((json.dumps([r[c] for c in fields],ensure_ascii=False)+'\n').encode());total+=1
  flush();assert len(entries)==357 and total==848634
  manifest=dict(format_version=1,dataset_kind='activity_segments',source_csv=source.name,source_csv_sha256=h.hexdigest(),protocol=parent['protocol'],summary=parent['summary'],segments=entries)
  add(z,'manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False))
  add(z,'metadata/source_manifest.json',json.dumps(parent,indent=2,ensure_ascii=False))
 from webapp.model_identification_app.backend.datasets import DatasetService,unpack
 data=dest.read_bytes();records,_,_=unpack([(dest.name,data)]);actual=hashlib.sha256();seen=0
 for _,blob,_ in records:
  for r in csv.DictReader(io.StringIO(blob.decode())):
   actual.update((json.dumps([r[c] for c in fields],ensure_ascii=False)+'\n').encode());seen+=1
 assert actual.digest()==expected.digest() and seen==total
 # Exercise the actual importer, without registering a duplicate dataset or storing blobs.
 class ValidationStore:
  def blob(self,data):return sha(data)
  def write(self,*args):pass
 service=DatasetService(ValidationStore(),ROOT/'dataset');ds=service.import_files([(dest.name,data)],'ZIP validation only');assert len(ds['segments'])==357;assert sum(s['samples'] for s in ds['segments'])==total;assert len({s['activity_id'] for s in ds['segments']})==130
 report=dict(output=str(dest),zip_bytes=len(data),segments=357,activities=130,samples=total,sha256=sha(data),all_cells_unchanged=True,actual_app_import_validation='passed; no application dataset created',missing_values='preserved')
 dest.with_suffix('.verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
