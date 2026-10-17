"""Headless offline HTML checks for lap random intercept experiment; no images."""
from pathlib import Path
import subprocess
import re
import html
import json

ROOT=Path(__file__).resolve().parents[1]


def run():
    p=ROOT/'power_response_estimation';temp=ROOT/'tmp/lap-ar-browser';temp.mkdir(parents=True,exist_ok=True)
    source=(p/'lap_ar.html').read_text(encoding='utf-8').replace('<head>','<head><base href="'+p.as_uri()+'/">')
    js='''
    let checks=0;const failures=[];function check(ok,label){checks++;if(!ok)failures.push(label);}
    try {
      check(Object.keys(data.splits).sort().join(',')==='train,validation','splits');
      for(const split of ['train','validation']) {
        $('split').value=split;openSplit();
        check($('workout').options.length===(split==='train'?36:12),'workout count');
        for(const [wid,w] of Object.entries(data.splits[split]))for(const [name,m] of Object.entries(w.models)) {
          check(Object.values(m).every(a=>a.length===w.t.length),'array lengths');
          check(m.low.every((x,i)=>Number.isFinite(x)&&x<=m.high[i]),'quantiles');
          check(m.negative.every(x=>x>=0&&x<=1),'negative probabilities');
          check(m.sample.every((x,i)=>Math.abs(x-w.mean[i]-m.offset[i]-m.noise[i])<.0021),'composition');
          const seen=new Map();let same=true;
          w.lap.forEach((lap,i)=>{if(seen.has(lap)&&seen.get(lap)!==m.offset[i])same=false;seen.set(lap,m.offset[i]);});
          check(same,'one offset per lap including fragments');
        }
        for(const model of ['lap_zero','lap_random']) {
          $('model').value=model;draw();
          check(chart.getOption().series.length===6,'main series');
          check(components.getOption().series.length===2,'components');
          check($('summary').querySelectorAll('tr').length===9,'summary rows');
          check($('laps').querySelectorAll('tr').length===7,'lap summary rows');
        }
      }
    } catch(e){failures.push(e.stack);}
    const el=document.createElement('pre');el.id='qa-result';el.textContent=JSON.stringify({checks,failures});document.body.appendChild(el);
    '''
    f=temp/'check.html';f.write_text(source.replace('</body>','<script>'+js+'</script></body>'),encoding='utf-8')
    result=subprocess.run(['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','--headless','--disable-gpu','--no-first-run',
        f'--user-data-dir={temp/"profile"}','--dump-dom','--virtual-time-budget=10000',f.as_uri()],capture_output=True,timeout=90)
    found=re.search(r'<pre id="qa-result">(.*?)</pre>',result.stdout.decode('utf-8',errors='replace'),re.S)
    assert found,'No browser result'
    report=json.loads(html.unescape(found.group(1)));print(report);assert not report['failures']


if __name__=='__main__':run()
