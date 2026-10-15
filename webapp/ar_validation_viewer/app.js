'use strict';
const $ = id => document.getElementById(id);
const chart = echarts.init($('chart'), null, {renderer: 'canvas'});
let catalog, current, currentIndex = 0, loading = false;
let rows = [];
const colors = {real: '#88939c', simulated: '#147fa8', target: '#c28a2e'};
const numeric = (x, digits=2) => Number(x).toLocaleString('it-IT', {minimumFractionDigits:digits, maximumFractionDigits:digits});
function clock(seconds) {
  const t = Math.max(0, Math.round(seconds));
  return `${Math.floor(t/3600).toString().padStart(2,'0')}:${Math.floor(t/60)%60 < 10 ? '0' : ''}${Math.floor(t/60)%60}:${(t%60).toString().padStart(2,'0')}`;
}
function nearest(time) {
  let lo=0, hi=rows.length;
  while(lo<hi) {const mid=(lo+hi)>>1;if(rows[mid][0]<time)lo=mid+1;else hi=mid;}
  let index=Math.min(lo,rows.length-1);
  if(index>0 && Math.abs(rows[index-1][0]-time)<Math.abs(rows[index][0]-time))index--;
  return index>=0 && Math.abs(rows[index][0]-time)<=.51 ? rows[index] : null;
}
function showValues(row) {
  if(!row)return;
  $('value-time').textContent=clock(row[0]);
  for(const [id,ix] of [['real',1],['target',2],['simulated',3]])$('value-'+id).textContent=numeric(row[ix])+' W';
  $('value-residual').textContent=`${numeric(row[4])} / ${numeric(row[5])} W`;
  $('value-z').textContent=`${numeric(row[6],3)} / ${numeric(row[7],3)}`;
}
function geometry() {
  const top=34, bottom=74, gap=48, height=(chart.getHeight()-top-bottom-2*gap)/3;
  return {grid:[0,1,2].map(i=>({left:76,right:28,top:top+i*(height+gap),height})),
    title:['Potenza [W]','Residui rispetto alla prescrizione [W]','ACF residui - intero workout - mediana e P10-P90'].map((text,i)=>({text,left:20,top:8+i*(height+gap),textStyle:{fontSize:12,fontWeight:600,color:'#365467'}}))};
}
function makeSeries(name, column, axis, color, dashed=false) {
  const data=[];
  current.segments.forEach((s,i)=>{
    if(i)data.push([(current.segments[i-1].rows.at(-1)[0]+s.rows[0][0])/2,null]);
    for(const row of s.rows)data.push([row[0],row[column]]);
  });
  return {name,type:'line',xAxisIndex:axis,yAxisIndex:axis,data,showSymbol:false,connectNulls:false,step:dashed?'end':false,
    animation:false,clip:true,lineStyle:{width:axis===0?1.05:1,color,type:dashed?'dashed':'solid',opacity:color===colors.real ? .8 : 1},
    itemStyle:{color},emphasis:{disabled:true}};
}
function acfSeries(name, column, color) {
  return {name,type:'line',xAxisIndex:2,yAxisIndex:2,showSymbol:false,
    data:current.acf.rows.map(r=>[r[0],r[column]]),lineStyle:{color,width:1.5},itemStyle:{color}};
}
function render() {
  const {grid,title}=geometry();
  chart.setOption({animation:false,title,grid,
    xAxis:[0,1].map(i=>({type:'value',gridIndex:i,min:current.start_s,max:current.end_s,
      axisLabel:{formatter:clock,color:'#758592',fontSize:10},axisLine:{lineStyle:{color:'#d9e1e7'}},axisTick:{show:false},
      splitLine:{show:true,lineStyle:{color:'#eef2f5'}},axisPointer:{show:true,snap:true,label:{show:true,formatter:p=>clock(p.value)}}})).concat([{type:'value',gridIndex:2,min:0,max:current.acf.rows.at(-1)?.[0] || 60,name:'Ritardo [s]',nameLocation:'middle',nameGap:24,axisPointer:{show:true,snap:true},splitLine:{lineStyle:{color:'#eef2f5'}}}]),
    yAxis:[0,1,2].map(i=>({type:'value',gridIndex:i,scale:true,...(i===2?{min:-1,max:1}:{}),axisLabel:{color:'#758592',fontSize:10},splitLine:{lineStyle:{color:'#eef2f5'}},
      axisPointer:{show:false}})),
    axisPointer:{link:[{xAxisIndex:[0,1]}],lineStyle:{color:'#476d83',type:'dashed'}},
    tooltip:{trigger:'axis',confine:true,transitionDuration:0,axisPointer:{type:'line'},
      formatter(params){
        if(params.some(p=>p.axisIndex===2)) {
          const r=current.acf.rows.find(r=>r[0]===Number(params[0].axisValue));
          if(!r)return '';
          const f=x=>x==null?'non definita':numeric(x,3);
          return `<b>Ritardo ${r[0]} s</b><br>ACF reale: ${f(r[1])}<br>Mediana AR: ${f(r[3])}<br>P10-P90: ${f(r[2])} / ${f(r[4])}<br>${r[5]} coppie valide - ${current.acf.paths} simulazioni`;
        }
        const point=params.find(p=>Array.isArray(p.value)&&p.value[1]!=null);const row=point?nearest(point.value[0]):null;
        if(!row)return '';showValues(row);
        return `<b>${clock(row[0])}</b><br>Reale: ${numeric(row[1])} W<br>Prescritta: ${numeric(row[2])} W<br>Simulata: ${numeric(row[3])} W<br>e reale / simulato: ${numeric(row[4])} / ${numeric(row[5])} W<br>z reale / simulato: ${numeric(row[6],3)} / ${numeric(row[7],3)}`;}},
    dataZoom:[{id:'inside',type:'inside',xAxisIndex:[0,1],filterMode:'none',zoomOnMouseWheel:true,moveOnMouseMove:true,moveOnMouseWheel:false,preventDefaultMouseMove:true},
      {id:'slider',type:'slider',xAxisIndex:[0,1],filterMode:'none',bottom:14,height:22,left:76,right:28,showDataShadow:false,borderColor:'#d6e1e7',fillerColor:'rgba(20,127,168,.10)',labelFormatter:clock}],
    series:[makeSeries('Reale',1,0,colors.real),makeSeries('Prescritta',2,0,colors.target,true),makeSeries('Simulata',3,0,colors.simulated),
      makeSeries('e reale',4,1,colors.real),makeSeries('e simulato',5,1,colors.simulated),acfSeries('ACF reale',1,colors.real),acfSeries('ACF mediana AR',3,colors.simulated),
      {...acfSeries('P10',2,colors.simulated),stack:'band',stackStrategy:'all',lineStyle:{opacity:0},silent:true},
      {...acfSeries('P10-P90',4,colors.simulated),data:current.acf.rows.map(r=>[r[0],r[2]==null?null:r[4]-r[2]]),stack:'band',stackStrategy:'all',lineStyle:{opacity:0},areaStyle:{color:colors.simulated,opacity:.18},silent:true}]},true);
}
function buttons() {
  $('previous').disabled=loading||currentIndex===0;
  $('next').disabled=loading||currentIndex===catalog.workouts.length-1;
  $('reset').disabled=loading;
}
async function request(url) {const response=await fetch(url);if(!response.ok)throw new Error(`Dati non disponibili (${response.status}).`);return response.json();}
async function openWorkout(index) {
  if(loading||index<0||index>=catalog.workouts.length)return;
  loading=true;buttons();$('error').hidden=true;chart.showLoading({text:'Caricamento workout…',color:colors.simulated});
  try {
    const data=await request('/api/workouts/'+catalog.workouts[index].id);
    current=data;currentIndex=index;rows=data.segments.flatMap(s=>s.rows);
    const meta=catalog.workouts[index];
    $('workout-title').textContent=meta.date+' · '+meta.id;
    $('workout-info').textContent=`AR(${catalog.model.p}) · Validation · ${clock(data.end_s)} · ${numeric(data.samples,0)} campioni`;
    $('counter').textContent=`${index+1} / ${catalog.workouts.length}`;
    render();showValues(rows[0]);
  }catch(error){$('error').textContent=error.message;$('error').hidden=false;}
  finally{loading=false;chart.hideLoading();buttons();}
}
$('previous').addEventListener('click',()=>openWorkout(currentIndex-1));
$('next').addEventListener('click',()=>openWorkout(currentIndex+1));
$('reset').addEventListener('click',()=>chart.dispatchAction({type:'dataZoom',start:0,end:100}));
new ResizeObserver(()=>{chart.resize();if(current)chart.setOption(geometry());}).observe($('chart'));
(async()=>{try{catalog=await request('/api/workouts');const m=catalog.model;
  $('scaling').textContent=`Scala comune: z = (e − μ) / σe · μ = ${numeric(m.residual_mean_w,3)} W · σe = ${numeric(m.residual_sd_w,3)} W · stimati sul training, non sul workout visualizzato.`;
  await openWorkout(0);
}catch(error){$('error').textContent=error.message;$('error').hidden=false;$('workout-title').textContent='Dati non disponibili';}})();
