'use strict';
const $=id=>document.getElementById(id),data=window.POWER_GARCH_RESULTS,base=window.POWER_RESPONSE_RESULTS;
const chart=echarts.init($('chart')),acfChart=echarts.init($('acf'));
const q90=1.2815515655446004;
const fmt=(x,n=3)=>x==null||!Number.isFinite(x)?'—':x.toLocaleString('it-IT',{maximumFractionDigits:n,minimumFractionDigits:n});
const clock=x=>{const t=Math.round(x);return [Math.floor(t/3600),Math.floor(t/60)%60,t%60].map(v=>String(v).padStart(2,'0')).join(':');};
let current,start=0,end=100;
const constant=base?.model?.decomposition?.ar?.sigma2;
function bounds(){const t=current.t,span=t.at(-1)-t[0];return [t[0]+span*start/100,t[0]+span*end/100];}
function metrics(model,range){
 let n=0,nll=0,coverage=0,width=0,score=0;
 for(let i=0;i<current.t.length;i++){
  if(current.epsilon[i]==null||current.t[i]<range[0]-1e-8||current.t[i]>range[1]+1e-8)continue;
  const e=current.epsilon[i],h=model==='garch'?current.h[i]:constant,half=q90*Math.sqrt(h);
  n++;nll+=.5*(Math.log(2*Math.PI*h)+e*e/h);coverage+=Math.abs(e)<=half?1:0;width+=2*half;score+=2*half+10*Math.max(Math.abs(e)-half,0);
 }
 return {n,nll:n?nll/n:null,coverage80:n?coverage/n:null,width80_w:n?width/n:null,interval_score80_w:n?score/n:null};
}
function updateMetrics(){
 const range=$('scope').value==='window'?bounds():[current.t[0],current.t.at(-1)],selected=$('variance').value;
 const s=metrics(selected,range);
 $('nll').textContent=fmt(s.nll);$('coverage').textContent=s.n?fmt(100*s.coverage80,1)+'%':'—';$('width').textContent=fmt(s.width80_w,1)+' W';$('score').textContent=fmt(s.interval_score80_w,1)+' W';
 $('window').textContent=bounds().map(clock).join(' → ');$('sample-info').textContent=s.n+' innovazioni valutate · Gaussiane condizionate · media AR identica fra i modelli.';
 $('comparison').innerHTML='<tr><th>Varianza</th><th>NLL</th><th>Copertura</th><th>Ampiezza W</th><th>Score W</th></tr>'+['constant','garch'].map(m=>{const v=metrics(m,range);return '<tr class="'+(m===selected?'active':'')+'"><td>'+(m==='garch'?'GARCH':'Costante')+'</td><td>'+fmt(v.nll)+'</td><td>'+fmt(v.coverage80==null?null:100*v.coverage80,1)+'%</td><td>'+fmt(v.width80_w,1)+'</td><td>'+fmt(v.interval_score80_w,1)+'</td></tr>';}).join('');
}
function points(v){const result=[];for(let i=0;i<current.t.length;i++){if(i&&current.segment[i]!==current.segment[i-1])result.push([(current.t[i]+current.t[i-1])/2,null]);result.push([current.t[i],v[i]]);}return result;}
function line(name,v,axis,color,width=1){return {name,type:'line',xAxisIndex:axis,yAxisIndex:axis,data:points(v),showSymbol:false,connectNulls:false,animation:false,lineStyle:{color,width},itemStyle:{color},emphasis:{disabled:true}};}
function draw(){
 const garch=$('variance').value==='garch',h=current.h.map(v=>v==null?null:(garch?v:constant));
 const low=current.conditionalMean.map((v,i)=>v==null?null:v-q90*Math.sqrt(h[i]));
 const width=h.map(v=>v==null?null:2*q90*Math.sqrt(v));
 const z=current.epsilon.map((v,i)=>v==null?null:v/Math.sqrt(h[i]));
 const axes=[0,1,2],titles=['Potenza e banda a un passo [W]','Varianza prevista delle innovazioni [W²]','Innovazioni standardizzate [adimensionali]'];
 const series=[{...line('P10',low,0,'#087e8b'),stack:'band',stackStrategy:'all',lineStyle:{opacity:0},silent:true},
  {...line('P10–P90',width,0,'#087e8b'),stack:'band',stackStrategy:'all',lineStyle:{opacity:0},areaStyle:{color:'#087e8b',opacity:.13},silent:true},
  line('Reale',current.real,0,'#8b9aa2',.8),line('Media AR a un passo',current.conditionalMean,0,'#087e8b',1.2),
  line('Target',current.target,0,'#b58226'),line('h GARCH',current.h,1,'#087e8b',1.3),
  line('Varianza costante',current.h.map(v=>v==null?null:constant),1,'#8060a4'),line('Standardizzate',z,2,'#bd5444')];
 chart.setOption({animation:false,legend:{top:0,data:['Reale','Media AR a un passo','Target','h GARCH','Varianza costante','Standardizzate']},
  title:titles.map((text,i)=>({text,left:14,top:40+i*265,textStyle:{fontSize:12}})),
  grid:axes.map(i=>({left:80,right:28,top:65+i*265,height:205})),
  xAxis:axes.map(i=>({type:'value',gridIndex:i,min:current.t[0],max:current.t.at(-1),axisLabel:{formatter:clock}})),
  yAxis:axes.map(i=>({type:'value',gridIndex:i,scale:true,splitLine:{lineStyle:{color:'#edf2f3'}}})),
  tooltip:{trigger:'axis',confine:true},axisPointer:{link:[{xAxisIndex:axes}]},
  dataZoom:[{type:'inside',xAxisIndex:axes,filterMode:'none',start,end},{type:'slider',xAxisIndex:axes,filterMode:'none',start,end,bottom:12,height:25}],series},true);
 updateMetrics();
}
function openWorkout(){
 current=data.splits[$('split').value].workouts[$('workout').value];start=0;end=100;
 $('previous').disabled=$('workout').selectedIndex===0;$('next').disabled=$('workout').selectedIndex===$('workout').options.length-1;
 draw();
 acfChart.setOption({animation:false,legend:{data:['Costante','GARCH']},grid:{left:65,right:25,top:35,bottom:45},tooltip:{trigger:'axis'},
  xAxis:{type:'value',name:'Lag [s]',min:1,max:120},yAxis:{type:'value',name:'ACF z²',scale:true},
  series:['constant','garch'].map((model,j)=>({name:j?'GARCH':'Costante',type:'line',showSymbol:false,data:current.acf[model].map((v,i)=>[i+1,v]),lineStyle:{color:j?'#087e8b':'#8060a4'}}))},true);
 $('arch').innerHTML='<tr><th>Varianza</th><th>Lag [s]</th><th>N</th><th>ARCH-LM</th><th>p-value</th></tr>'+current.arch.map(r=>'<tr><td>'+r.model+'</td><td>'+r.lag_s+'</td><td>'+r.nobs+'</td><td>'+fmt(r.lm,2)+'</td><td>'+(r.p_value===0?'&lt;1e-300':r.p_value.toExponential(2))+'</td></tr>').join('');
}
function openSplit(){$('workout').replaceChildren();for(const w of Object.keys(data.splits[$('split').value].workouts))$('workout').add(new Option(w,w));openWorkout();}
chart.on('datazoom',()=>{const v=chart.getOption().dataZoom[0];start=v.start;end=v.end;updateMetrics();});
$('split').addEventListener('change',openSplit);$('workout').addEventListener('change',openWorkout);$('variance').addEventListener('change',draw);$('scope').addEventListener('change',updateMetrics);
$('previous').addEventListener('click',()=>{$('workout').selectedIndex--;openWorkout();});$('next').addEventListener('click',()=>{$('workout').selectedIndex++;openWorkout();});$('reset').addEventListener('click',()=>chart.dispatchAction({type:'dataZoom',start:0,end:100}));
new ResizeObserver(()=>{chart.resize();acfChart.resize();}).observe($('chart'));
try{
 if(!data||data.baselineModelHash!==base?.model_hash)throw new Error('Risultati GARCH assenti o non coerenti con il modello AR. Eseguire fit-garch/test-garch.');
 const model=data.model,m=model.model,p=m.alpha+m.beta,fourth=p*p+2*m.alpha*m.alpha;
 $('model-info').textContent=model.training_workouts+' workout di training · AR congelato · Gaussian QML · seed '+model.config.seed;
 $('params').textContent='ω = '+fmt(m.omega)+' W² · α = '+fmt(m.alpha,6)+' · β = '+fmt(m.beta,6)+' · α+β = '+fmt(p,6)+'. Varianza incondizionata = '+fmt(m.unconditional_variance_w2,1)+' W².';
 $('warning').textContent=(p>.98?'Persistenza elevata: sensibile all’inizializzazione e alla variabilità tra sessioni. ':'')+(fourth>=1?'Il modello gaussiano stimato non ha quarto momento incondizionato finito. ':'')+'IC dei parametri non disponibili in questo fit; non interpretarli come caratteristiche individuali stabili.';
 $('summary').innerHTML='<tr><th>Split</th><th>Modalità</th><th>Varianza</th><th>Workout</th><th>NLL</th><th>Copertura</th><th>Ampiezza W</th><th>Score W</th></tr>'+data.summary.map(r=>'<tr><td>'+r.split+'</td><td>'+(r.mode==='conditional'?'A un passo':'Libera')+'</td><td>'+r.model+'</td><td>'+r.workouts+'</td><td>'+fmt(r.nll)+'</td><td>'+fmt(100*r.coverage80,1)+'%</td><td>'+fmt(r.width80_w,1)+'</td><td>'+fmt(r.interval_score80_w,1)+'</td></tr>').join('');
 for(const s of Object.keys(data.splits))$('split').add(new Option(s,s));openSplit();
}catch(e){$('error').hidden=false;$('error').textContent=e.message;}
