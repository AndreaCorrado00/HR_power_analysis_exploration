'use strict';
const $ = id => document.getElementById(id);
const dataset = window.POWER_RESPONSE_RESULTS;
const garchDataset = window.POWER_GARCH_RESULTS;
const chart = echarts.init($('chart'), null, {renderer:'canvas'});
const colors = {real:'#8b9aa2', target:'#b58226', model:'#087e8b', dynamic:'#bd5444', ar:'#8060a4'};
let current, start=0, end=100, values;
const format = (x,d=2) => x==null ? '—' : Number(x).toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d});
function clock(seconds){const t=Math.max(0,Math.round(seconds));return [Math.floor(t/3600),Math.floor(t/60)%60,t%60].map(v=>String(v).padStart(2,'0')).join(':');}
function options(){return {dynamic:$('dynamic').checked,ar:$('ar').checked,mode:$('mode').value,variance:$('variance').value};}
function stochastic(data,opts){return opts.variance==='garch'?garchDataset.splits[$('split').value].workouts[$('workout').value]:data;}
function compose(data,opts){
 const prediction=[],residual=[],response=[],noise=[];
 const source=stochastic(data,opts);
 for(let i=0;i<data.t.length;i++){
  const r=opts.dynamic?data.r[i]:0,a=opts.ar?(opts.mode==='mean'?data.arMean:source.arSample[i]):0;
  response.push(r);noise.push(a);prediction.push(data.target[i]+r+a);residual.push(data.real[i]-prediction[i]);
 }
 return {prediction,residual,response,noise};
}
function bounds(){const first=current.t[0],span=current.t.at(-1)-first;return [first+span*start/100,first+span*end/100];}
function stats(errors,range){
 let count=0,sum=0,absolute=0,square=0;
 for(let i=0;i<errors.length;i++){if(current.t[i]<range[0]-1e-8||current.t[i]>range[1]+1e-8)continue;const e=errors[i];count++;sum+=e;absolute+=Math.abs(e);square+=e*e;}
 return {n:count,rmse:count?Math.sqrt(square/count):null,mae:count?absolute/count:null,bias:count?sum/count:null};
}
function metricRange(){return $('scope').value==='workout'?[current.t[0],current.t.at(-1)]:bounds();}
function updateMetrics(){
 const opts=options(),range=metricRange(),s=stats(values.residual,range),mean=stats(compose(current,{...opts,mode:'mean'}).residual,range);
 $('rmse').textContent=format(s.rmse)+' W';$('mae').textContent=format(s.mae)+' W';$('bias').textContent=format(s.bias)+' W';$('mean-rmse').textContent=format(mean.rmse)+' W';$('samples').textContent=format(s.n,0);
 $('window-label').textContent=bounds().map(clock).join(' → ');
 $('metric-note').textContent=(opts.mode==='simulation'&&opts.ar?'Errore della prima realizzazione casuale: non misura la capacità di prevedere i singoli picchi.':'Errore della previsione media, senza feedback osservato.')+' Residuo aggiornato = potenza reale − curva attiva.';
 let html='<tr><th>Dinamica / AR</th><th>RMSE W</th><th>MAE W</th><th>Bias W</th></tr>';
 for(const dynamic of [false,true])for(const ar of [false,true]){const q=stats(compose(current,{dynamic,ar,mode:opts.mode,variance:opts.variance}).residual,range);html+='<tr class="'+(dynamic===opts.dynamic&&ar===opts.ar?'active':'')+'"><td>'+(dynamic?'ON':'OFF')+' / '+(ar?'ON':'OFF')+'</td><td>'+format(q.rmse)+'</td><td>'+format(q.mae)+'</td><td>'+format(q.bias)+'</td></tr>';}
 $('ablations').innerHTML=html;
}
function points(series){
 const result=[];for(let i=0;i<current.t.length;i++){if(i&&current.segment[i]!==current.segment[i-1])result.push([(current.t[i-1]+current.t[i])/2,null]);result.push([current.t[i],series[i]]);}return result;
}
function line(name,series,axis,color,width=1.2,step=false){return {name,type:'line',xAxisIndex:axis,yAxisIndex:axis,data:points(series),showSymbol:false,connectNulls:false,step:step?'end':false,animation:false,clip:true,lineStyle:{color,width},itemStyle:{color},emphasis:{disabled:true}};}
function geometry(){
 const top=64,gap=55,bottom=90,height=(chart.getHeight()-top-bottom-3*gap)/4;
 return {grid:[0,1,2,3].map(i=>({left:70,right:30,top:top+i*(height+gap),height})),title:['Potenza [W]','Residuo aggiornato: reale − curva attiva [W]','Contributi attivi [W]','Ingresso ΔP prescritta [W]'].map((text,i)=>({text,left:16,top:top-24+i*(height+gap),textStyle:{fontSize:12,fontWeight:600,color:'#345463'}}))};
}
function draw(){
 const opts=options();values=compose(current,opts);
 const raw=current.real.map((v,i)=>v-current.target[i]);
 const series=[];
 const source=stochastic(current,opts);
 if(opts.ar){const low=current.target.map((v,i)=>v+values.response[i]+source.low[i]),width=source.high.map((v,i)=>v-source.low[i]);
  series.push({...line('Banda P10',low,0,colors.ar),stack:'interval',stackStrategy:'all',lineStyle:{opacity:0},silent:true},
   {...line('Banda P10–P90',width,0,colors.ar),stack:'interval',stackStrategy:'all',lineStyle:{opacity:0},areaStyle:{opacity:.09,color:colors.ar},silent:true});}
 series.push(line('Reale',current.real,0,colors.real,.9),line('Prescritta',current.target,0,colors.target,1.4,true),line('Modello attivo',values.prediction,0,colors.model,1.3),
  line('Residuo originale',raw,1,colors.real,.8),line('Residuo aggiornato',values.residual,1,colors.model,1.2),
  line('Risposta dinamica',values.response,2,colors.dynamic,1.4),line('Contributo AR',values.noise,2,colors.ar,1),line('ΔP prescritta',current.u,3,colors.target,1.2));
 const axes=[0,1,2,3];
 chart.setOption({animation:false,...geometry(),legend:{top:0,selectedMode:false,data:['Reale','Prescritta','Modello attivo','Residuo originale','Residuo aggiornato','Risposta dinamica','Contributo AR'],textStyle:{fontSize:11}},
  xAxis:axes.map(i=>({type:'value',gridIndex:i,min:current.t[0],max:current.t.at(-1),axisLabel:{formatter:clock,fontSize:10},splitLine:{lineStyle:{color:'#edf2f3'}}})),
  yAxis:axes.map(i=>({type:'value',gridIndex:i,scale:true,axisLabel:{fontSize:10},splitLine:{lineStyle:{color:'#e8eeee'}}})),
  axisPointer:{link:[{xAxisIndex:axes}]},
  tooltip:{trigger:'axis',confine:true,transitionDuration:0,formatter(params){
   const point=params.find(p=>p.value?.[1]!=null);if(!point)return '';const t=point.value[0];let l=0,r=current.t.length;while(l<r){const mid=(l+r)>>1;if(current.t[mid]<t)l=mid+1;else r=mid;}let i=Math.min(l,current.t.length-1);if(i&&Math.abs(current.t[i-1]-t)<Math.abs(current.t[i]-t))i--;if(Math.abs(current.t[i]-t)>.51)return '';
   const text=clock(current.t[i])+' · reale '+format(current.real[i])+' W · modello '+format(values.prediction[i])+' W · residuo '+format(values.residual[i])+' W';$('readout').textContent=text;
   return '<b>'+clock(current.t[i])+'</b><br>Reale: '+format(current.real[i])+' W<br>Target: '+format(current.target[i])+' W<br>r attivo: '+format(values.response[i])+' W<br>AR attivo: '+format(values.noise[i])+' W<br>Modello: '+format(values.prediction[i])+' W<br>Residuo: '+format(values.residual[i])+' W';}},
  dataZoom:[{id:'inside',type:'inside',xAxisIndex:axes,filterMode:'none',start,end,zoomOnMouseWheel:true,moveOnMouseMove:true,moveOnMouseWheel:false,preventDefaultMouseMove:true},
   {id:'slider',type:'slider',xAxisIndex:axes,filterMode:'none',start,end,bottom:14,height:25,left:70,right:30,showDataShadow:false,labelFormatter:clock}],series},true);
 updateMetrics();
}
function openWorkout(){
 current=dataset.splits[$('split').value].workouts[$('workout').value];start=0;end=100;
 $('previous').disabled=$('workout').selectedIndex===0;$('next').disabled=$('workout').selectedIndex===$('workout').options.length-1;
 $('readout').textContent='';draw();
}
function openSplit(){
 const available=garchDataset?.baselineModelHash===dataset.model_hash&&garchDataset?.splits[$('split').value];
 $('variance').options[1].disabled=!available;if(!available)$('variance').value='constant';
 $('workout').replaceChildren();for(const wid of Object.keys(dataset.splits[$('split').value].workouts))$('workout').add(new Option(wid,wid));
 $('notice').textContent='Target ricostruiti dalla potenza: risultati condizionati al dataset. '+($('split').value==='test'?'TEST già esaminato: confronto descrittivo.':'VALIDATION usato per scegliere l’ordine.')+' Coefficienti congelati dal training.';openWorkout();
}
function moveWindow(a,b){const width=Math.min(100,b-a);a=Math.max(0,Math.min(100-width,a));b=a+width;chart.dispatchAction({type:'dataZoom',start:a,end:b});}
chart.on('datazoom',()=>{const z=chart.getOption().dataZoom[0];start=z.start;end=z.end;updateMetrics();});
for(const id of ['dynamic','ar','mode','variance'])$(id).addEventListener('change',draw);
$('scope').addEventListener('change',updateMetrics);$('workout').addEventListener('change',openWorkout);$('split').addEventListener('change',openSplit);
$('previous').addEventListener('click',()=>{$('workout').selectedIndex--;openWorkout();});$('next').addEventListener('click',()=>{$('workout').selectedIndex++;openWorkout();});
$('reset').addEventListener('click',()=>moveWindow(0,100));
$('zoom-in').addEventListener('click',()=>{const mid=(start+end)/2,width=Math.max(.01,(end-start)/2);moveWindow(mid-width/2,mid+width/2);});
$('zoom-out').addEventListener('click',()=>{const mid=(start+end)/2,width=Math.min(100,(end-start)*2);moveWindow(mid-width/2,mid+width/2);});
$('pan-left').addEventListener('click',()=>moveWindow(start-(end-start)/2,end-(end-start)/2));$('pan-right').addEventListener('click',()=>moveWindow(start+(end-start)/2,end+(end-start)/2));
new ResizeObserver(()=>{chart.resize();if(current)chart.setOption(geometry());}).observe($('chart'));
try{
 if(!dataset||!Object.keys(dataset.splits).length)throw new Error('Nessuna valutazione disponibile. Eseguire prima fit o test.');
 for(const name of Object.keys(dataset.splits))$('split').add(new Option(name,name));
 const m=dataset.model,s=m.statistics,ar=m.decomposition.ar;
 $('model-summary').textContent='Dinamica n='+m.selected_order+' · AR('+ar.p+') · '+m.training_workouts+' workout di training · '+m.loss.toUpperCase()+' · seed '+m.decomposition.seed;
 $('fit-info').textContent='Raggio poli '+format(s.spectral_radius,5)+' · rango '+s.jacobian_rank+'/'+s.parameter_count+' · condizionamento '+Number(s.jacobian_condition).toExponential(2);
 $('selection').innerHTML='<tr><th>Ordine</th><th>RMSE validation W</th><th>Delta W</th></tr>'+m.selection.comparisons.map(row=>'<tr class="'+(row.order===m.selected_order?'active':'')+'"><td>'+row.order+'</td><td>'+format(row.mean_rmse_w,3)+'</td><td>'+format(row.delta_from_best_w,3)+'</td></tr>').join('');
 $('parameters').innerHTML='<tr><th>Parametro</th><th>Stima</th><th>IC 95% locale</th></tr>'+s.parameters.map(p=>'<tr><td>'+p.name+'</td><td>'+format(p.estimate,5)+'</td><td>'+(p.ci95?p.ci95.map(v=>format(v,5)).join(' … '):'n.d.')+'</td></tr>').join('');
 $('ar-info').textContent='AR: c='+format(ar.intercept,5)+' W · φ=['+ar.coefficients.map(v=>format(v,5)).join('; ')+'] · varianza innovazioni '+format(ar.sigma2)+' W² · stabile '+ar.stable;
 openSplit();
}catch(error){$('error').hidden=false;$('error').textContent=error.message;}
