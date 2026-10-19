"""Offline checks for the frozen constant-variance baseline page."""
from pathlib import Path
import html
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run():
    module=ROOT/'power_response_estimation';temp=ROOT/'tmp/power-response-browser';temp.mkdir(parents=True,exist_ok=True)
    source=(module/'index.html').read_text(encoding='utf-8').replace('<head>','<head><base href="'+module.as_uri()+'/">')
    script='''
    const failures=[];let checks=0;function check(ok,label){checks++;if(!ok)failures.push(label);}
    function close(a,b){return Math.abs(a-b)<1e-8*Math.max(1,Math.abs(b));}
    try{
      check(!document.getElementById('variance'),'experimental selector removed');
      check(!Array.from(document.scripts).some(s=>/garch|variance_results|scaled_ar|lap_ar/.test(s.src)),'no experiment scripts');
      $('split').value='validation';openSplit();
      for(const wid of Object.keys(dataset.splits.validation.workouts)){
        $('workout').value=wid;openWorkout();
        for(const mode of ['mean','simulation'])for(const dynamic of [false,true])for(const ar of [false,true]){
          const v=compose(current,{mode,dynamic,ar}),j=Math.floor(current.t.length/2);
          const expected=ar&&mode==='mean'?(dynamic?current.clippedMean[j]:current.clippedMeanNoDynamics[j]):Math.max(0,current.target[j]+(dynamic?current.r[j]:0)+(ar?current.arSample[j]:0));
          check(v.prediction.every(p=>p>=0),'nonnegative output');
          const metric=dataset.splits.validation.metrics.find(m=>m.workout_id===wid&&m.mode===mode&&m.dynamic===dynamic&&m.ar===ar);
          const measured=stats(v.residual,[current.t[0],current.t.at(-1)]);
          check(close(measured.rmse,metric.rmse_w)&&close(measured.bias,metric.bias_w),'Python JS metrics');
          check(close(v.prediction[j],expected),'composition');check(close(v.residual[j],current.real[j]-expected),'residual');
        }
      }
      check(chart.getOption().series.length>5,'chart');
      chart.dispatchAction({type:'dataZoom',start:20,end:40});check(start===20&&end===40,'zoom');
    }catch(e){failures.push(e.stack);}
    const result=document.createElement('pre');result.id='qa-result';result.textContent=JSON.stringify({checks,failures});document.body.appendChild(result);
    '''
    page=temp/'index.html';page.write_text(source.replace('</body>','<script>'+script+'</script></body>'),encoding='utf-8')
    result=subprocess.run(['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','--headless','--disable-gpu','--no-first-run',
        f'--user-data-dir={temp/"profile"}','--dump-dom','--virtual-time-budget=10000',page.as_uri()],capture_output=True,timeout=90)
    found=re.search(r'<pre id="qa-result">(.*?)</pre>',result.stdout.decode('utf-8',errors='replace'),re.S)
    assert found, 'No browser result: '+result.stderr.decode('utf-8',errors='replace')[-2000:]
    report=json.loads(html.unescape(found.group(1)));print(report);assert not report['failures']


if __name__=='__main__':run()
