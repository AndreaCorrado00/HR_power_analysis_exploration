"""Export original road activity samples split at dt>10s, keeping duration>=300s.
Run from repository root. No imputation, interpolation, or resampling.
"""
import csv,io,json,hashlib,math
from pathlib import Path
import zipfile
ROOT=Path.cwd()
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def absent(value):
 try:return not math.isfinite(float(value))
 except (ValueError,TypeError):return True

def main():
 source=ROOT/'dataset/cleaned_only_road_activities_csv.zip';original=ROOT/'dataset/cleaned_only_road_activieties.zip';dest=ROOT/'dataset/road_segments_gt10s_min5min.csv';manifest_path=dest.with_suffix('.manifest.json');index_path=dest.with_name(dest.stem+'_index.csv')
 if any(p.exists() for p in [dest,manifest_path,index_path]):raise ValueError('Output exists; refusing overwrite')
 source_sha=digest(source);original_sha=digest(original);index=[];discarded=[];expected=hashlib.sha256();source_columns=None;row_count=0;missing_p=0;missing_h=0
 extra=['segment_id','segment_number','source_elapsed_seconds','source_row_index','source_file','activity_split','segment_selected_from_activity','power_missing','hr_missing']
 with zipfile.ZipFile(source) as z,dest.open('x',encoding='utf-8',newline='') as f:
  m=json.loads(z.read('manifest.json'));assert m['source_archive_sha256']==original_sha;writer=None
  for entry in m['segments']:
   blob=z.read(entry['csv_file']);assert hashlib.sha256(blob).hexdigest()==entry['csv_sha256'];reader=csv.DictReader(io.StringIO(blob.decode('utf-8-sig')));rows=list(reader)
   if source_columns is None:
    source_columns=reader.fieldnames;assert not set(extra)&set(source_columns);writer=csv.DictWriter(f,fieldnames=source_columns+extra);writer.writeheader()
   assert reader.fieldnames==source_columns
   t=[float(r['elapsed_seconds']) for r in rows];assert all(b>a for a,b in zip(t,t[1:]));bounds=[0]+[i+1 for i in range(len(t)-1) if t[i+1]-t[i]>10]+[len(t)]
   for number,(a,b) in enumerate(zip(bounds,bounds[1:]),1):
    sid=entry['activity_id']+f':segment:{number:03d}';duration=t[b-1]-t[a];meta=dict(segment_id=sid,activity_id=entry['activity_id'],source_file=entry['csv_file'],segment_number=number,source_first_row=a,source_last_row=b-1,source_start_s=t[a],source_end_s=t[b-1],duration_s=duration,samples=b-a,activity_split=len(bounds)>2,missing_power=sum(absent(r['power_w']) for r in rows[a:b]),missing_hr=sum(absent(r['heart_rate_bpm']) for r in rows[a:b]))
    if duration<300:discarded.append(meta);continue
    index.append(meta)
    for i in range(a,b):
     original_row=rows[i];row=dict(original_row);p=absent(row['power_w']);h=absent(row['heart_rate_bpm']);row.update(elapsed_seconds=format(t[i]-t[a],'.17g'),segment_id=sid,segment_number=number,source_elapsed_seconds=original_row['elapsed_seconds'],source_row_index=i,source_file=entry['csv_file'],activity_split=int(len(bounds)>2),segment_selected_from_activity=int(a!=0 or b!=len(rows)),power_missing=int(p),hr_missing=int(h));writer.writerow(row)
     expected.update((json.dumps([original_row[c] for c in source_columns],ensure_ascii=False)+'\n').encode());row_count+=1;missing_p+=p;missing_h+=h
 # Independent output readback: contiguous segment boundaries, durations, and original cell digest.
 actual=hashlib.sha256();seen={};output_count=0
 with dest.open(encoding='utf-8',newline='') as f:
  for r in csv.DictReader(f):
   sid=r['segment_id'];time=float(r['elapsed_seconds']);st=seen.setdefault(sid,dict(first=time,last=time,n=0));assert time==0 if st['n']==0 else 0<time-st['last']<=10;st.update(last=time,n=st['n']+1)
   restored=[r['source_elapsed_seconds'] if c=='elapsed_seconds' else r[c] for c in source_columns];actual.update((json.dumps(restored,ensure_ascii=False)+'\n').encode());output_count+=1
 assert expected.digest()==actual.digest();assert output_count==row_count==848634;assert len(seen)==len(index)==357
 assert all(s['first']==0 and s['last']>=300 for s in seen.values());assert len({r['activity_id'] for r in index})==130
 with index_path.open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=index[0]);w.writeheader();w.writerows(index)
 manifest=dict(source_archive=str(original),source_archive_sha256=original_sha,source_csv_archive=str(source),source_csv_archive_sha256=source_sha,output_csv=dest.name,output_sha256=digest(dest),generator_sha256=digest(Path(__file__)),protocol=dict(split='before first sample following timestamp interval strictly >10 s',minimum_segment_duration_s=300,duration='last minus first sample timestamp',time_origin='first sample of each segment',original_elapsed_column='source_elapsed_seconds',source_row_index='zero based within original activity',interpolation=False,resampling=False,missing_values='preserved; power_missing and hr_missing flag nonfinite or absent values',validation_split_group='activity_id; keep segments of the same activity together'),summary=dict(source_activities=131,represented_activities=130,segments=len(index),rows=row_count,retained_sample_percent=100*row_count/865127,missing_power=missing_p,missing_hr=missing_h,discarded_segments=len(discarded)),verification='Readback verified every original field, complete sample partition selection, segment durations, and remaining timestamp intervals <=10s',segments=index,discarded_segments=discarded)
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');assert digest(source)==source_sha and digest(original)==original_sha
 print(json.dumps(manifest['summary'],indent=2));print('OUTPUT',dest,'BYTES',dest.stat().st_size);print('READBACK VERIFIED',manifest['output_sha256'])
if __name__=='__main__':main()
