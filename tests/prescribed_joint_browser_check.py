"""Exercise the offline viewer in Edge; run after validation and test publication."""
from pathlib import Path
import html
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run():
    folder=ROOT/'experiments/prescribed_joint'
    temp=ROOT/'tmp/joint-browser-check'
    temp.mkdir(parents=True,exist_ok=True)
    source=(folder/'index.html').read_text(encoding='utf-8')
    source=source.replace('<head>','<head><base href="'+folder.as_uri()+'/">')
    script='''
    const failures=[];let checks=0;
    function check(ok,label){checks++;if(!ok)failures.push(label);}
    try {
      check(!$('error').textContent,'page has no startup error');
      check(Object.keys(data.splits).length===2,'validation and test present');
      for(const split of Object.keys(data.splits)){
        $('split').value=split;openSplit();
        check($('workout').options.length===9,'nine workouts '+split);
        for(const wid of data.split[split]){
          $('workout').value=wid;openWorkout();
          check(chart.getOption().series.length===13,'all graph series '+wid);
          check(!$('cards').textContent.includes('NaN'),'finite cards '+wid);
          check($('workoutMetrics').querySelectorAll('tbody tr').length===9,'metric rows '+wid);
          const segments=current.segments.filter(s=>s.workout_id===wid);
          check(segments.length>0,'HR coverage '+wid);
          check($('segment').options.length===segments.length+1,'segment selector '+wid);
          $('segment').value=segments[0].id;render();
          check(chart.getOption().series[4].data.length===segments[0].series.time.length,'segment plot length '+wid);
          $('window').value='tail';render();
          const expected=current.metrics.find(r=>r.workout_id===wid&&r.model==='chain'&&r.window==='tail');
          check($('cards').querySelector('b').textContent===fmt(expected.RMSE),'tail metric '+wid);
          $('window').value='all';
        }
      }
      $('split').value='validation';openSplit();
      chart.dispatchAction({type:'dataZoom',start:20,end:70});
      check(chart.getOption().dataZoom[0].start===20,'zoom synchronization');
      chart.dispatchAction({type:'dataZoom',start:0,end:100});
    }catch(e){failures.push(e.stack);}
    const report=document.createElement('pre');report.id='qa-result';
    report.textContent=JSON.stringify({checks,failures});document.body.appendChild(report);
    '''
    page=temp/'index.html'
    page.write_text(source.replace('</body>','<script>'+script+'</script></body>'),encoding='utf-8')
    result=subprocess.run(['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        '--headless','--disable-gpu','--no-first-run',f'--user-data-dir={temp/"profile"}',
        '--dump-dom','--virtual-time-budget=15000','--window-size=1440,1500',
        f'--screenshot={temp/"viewer.png"}',page.as_uri()],capture_output=True,timeout=90)
    found=re.search(r'<pre id="qa-result">(.*?)</pre>',result.stdout.decode('utf-8',errors='replace'),re.S)
    assert found,'No browser result: '+result.stderr.decode('utf-8',errors='replace')[-2000:]
    report=json.loads(html.unescape(found.group(1)))
    (temp/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report)
    assert not report['failures']


if __name__=='__main__':run()
