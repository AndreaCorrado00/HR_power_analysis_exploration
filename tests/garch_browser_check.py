"""Headless Edge smoke/metric checks for both HTML pages; no screenshots.

Run explicitly with Python. Checks the pages offline with file:// URLs.
"""
from pathlib import Path
import html
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT/'tmp/garch-browser-check'
EDGE = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')

COMMON = """
const failures=[];let checks=0;
function check(ok,label){checks++;if(!ok)failures.push(label);}
function close(a,b){return Math.abs(a-b)<1e-8*Math.max(1,Math.abs(b));}
try {
check(document.getElementById('error').hidden,'no page error');
"""
END = """
} catch(e){failures.push(e.stack);}
const result=document.createElement('pre');result.id='qa-result';result.textContent=JSON.stringify({checks,failures});document.body.appendChild(result);
"""
DIAGNOSTIC = """
for(const split of Object.keys(data.splits)){
 $('split').value=split;openSplit();
 for(const wid of Object.keys(data.splits[split].workouts)){
  $('workout').value=wid;openWorkout();
  for(const model of ['constant','garch']){
   $('variance').value=model;draw();
   const actual=metrics(model,[current.t[0],current.t.at(-1)]);
   const expected=current.metrics.find(r=>r.mode==='conditional'&&r.model===model);
   for(const k of ['n','nll','coverage80','width80_w','interval_score80_w'])check(close(actual[k],expected[k]),split+'/'+wid+'/'+model+'/'+k);
  }
  check(chart.getOption().series.length===8,'conditional series');
  check(acfChart.getOption().series[0].data.length===120,'ACF lag count');
 }
}
$('scope').value='window';chart.dispatchAction({type:'dataZoom',start:25,end:50});
check(metrics('garch',bounds()).n<current.metrics[1].n,'zoom limits evaluated samples');
"""
MAIN = """
for(const split of Object.keys(dataset.splits)){
 $('split').value=split;openSplit();
 for(const wid of Object.keys(dataset.splits[split].workouts)){
  $('workout').value=wid;openWorkout();
  check(!$('variance').options[1].disabled,'GARCH available');
  for(const variance of ['constant','garch'])for(const mode of ['mean','simulation'])for(const dynamic of [false,true])for(const ar of [false,true]){
   const opts={variance,mode,dynamic,ar},v=compose(current,opts);
   const source=variance==='garch'?garchDataset.splits[split].workouts[wid]:current;
   const j=Math.floor(current.t.length/2);
   const expected=current.target[j]+(dynamic?current.r[j]:0)+(ar?(mode==='mean'?current.arMean:source.arSample[j]):0);
   check(close(v.prediction[j],expected),'composition '+wid+JSON.stringify(opts));
   check(close(v.residual[j],current.real[j]-expected),'residual '+wid);
  }
 }
}
$('variance').value='garch';draw();
check(chart.getOption().series.length>5,'GARCH chart rendered');
chart.dispatchAction({type:'dataZoom',start:20,end:40});check(start===20&&end===40,'synchronized zoom');
"""


def run():
    TEMP.mkdir(parents=True,exist_ok=True)
    summaries = {}
    for name,script in [('garch',DIAGNOSTIC),('index',MAIN)]:
        source = (ROOT/f'power_response_estimation/{name}.html').read_text(encoding='utf-8')
        base_url = (ROOT/'power_response_estimation').as_uri()+'/'
        source = source.replace('<head>',f'<head><base href="{base_url}">',1)
        source = source.replace('</body>','<script>'+COMMON+script+END+'</script></body>')
        (TEMP/f'{name}.html').write_text(source,encoding='utf-8')
        result = subprocess.run([str(EDGE),'--headless','--disable-gpu','--no-first-run',
            '--no-default-browser-check','--disable-extensions',f'--user-data-dir={TEMP/name}',
            '--dump-dom','--virtual-time-budget=10000',(TEMP/f'{name}.html').as_uri()],
            capture_output=True,timeout=120)
        dom = result.stdout.decode('utf-8',errors='replace')
        found = re.search(r'<pre id="qa-result">(.*?)</pre>',dom,re.S)
        if not found:
            (TEMP/f'{name}-stderr.txt').write_bytes(result.stderr)
            raise RuntimeError(f'No browser result for {name}; see {TEMP}')
        report = json.loads(html.unescape(found.group(1)))
        summaries[name] = report
        if report['failures']:
            raise AssertionError(report)
    (TEMP/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':
    run()
