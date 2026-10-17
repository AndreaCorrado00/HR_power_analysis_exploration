"""Offline Edge smoke checks, no new images."""
from pathlib import Path
import html
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TEMP=ROOT/'tmp/variance-browser-check'
EDGE=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')


def run():
    TEMP.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'power_response_estimation/variance.html').read_text(encoding='utf-8')
    source=source.replace('<head>','<head><base href="'+(ROOT/'power_response_estimation').as_uri()+'/">')
    script='''
    let checks=0;const failures=[];
    function check(v,s){checks++;if(!v)failures.push(s);}
    try {
      check(Object.keys(data.splits).sort().join(',')==='train,validation','splits');
      for(const split of ['train','validation']) {
        $('split').value=split;openSplit();
        check($('workout').options.length===(split==='train'?36:12),'workouts');
        for(const [id,w] of Object.entries(data.splits[split])) {
          for(const [name,m] of Object.entries(w.models)) {
            check(m.h.length===w.t.length&&m.low.length===w.t.length,'lengths');
            check(m.h.every(x=>x>0&&Number.isFinite(x)),'finite variance');
            check(m.low.every((x,i)=>x<=m.high[i]),'quantile ordering');
            check(m.acf.length===120,'acf length');
          }
        }
        for(const model of ['constant','garch','targeted','context'])for(const mode of ['free','conditional']) {
          $('model').value=model;$('mode').value=mode;draw();
          check(chart.getOption().series.length===(mode==='free'?6:5),'series');
          check($('summary').querySelectorAll('tr').length===9,'summary rows');
        }
      }
    } catch(e){failures.push(e.stack);}
    const el=document.createElement('pre');el.id='qa-result';el.textContent=JSON.stringify({checks,failures});document.body.appendChild(el);
    '''
    source=source.replace('</body>','<script>'+script+'</script></body>')
    path=TEMP/'variance.html';path.write_text(source,encoding='utf-8')
    result=subprocess.run([str(EDGE),'--headless','--disable-gpu','--no-first-run','--disable-extensions',
        f'--user-data-dir={TEMP/"profile"}','--dump-dom','--virtual-time-budget=10000',path.as_uri()],capture_output=True,timeout=120)
    found=re.search(r'<pre id="qa-result">(.*?)</pre>',result.stdout.decode('utf-8',errors='replace'),re.S)
    if not found:
        raise RuntimeError(result.stderr.decode('utf-8',errors='replace')[-2000:])
    report=json.loads(html.unescape(found.group(1)));print(report)
    assert not report['failures']


if __name__=='__main__':
    run()
