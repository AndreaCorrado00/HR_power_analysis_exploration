const data=window.VARIANCE_RESULTS,$=id=>document.getElementById(id);
const chart=echarts.init($('chart')),varianceChart=echarts.init($('variance-chart')),acfChart=echarts.init($('acf'));
chart.group=varianceChart.group='time';echarts.connect('time');
function table(id,rows,cols){
 const t=document.createElement('table'),head=t.insertRow();
 for(const c of cols){const th=document.createElement('th');th.textContent=c;head.appendChild(th);}
 for(const r of rows){const tr=t.insertRow();for(const c of cols)tr.insertCell().textContent=typeof r[c]==='number'?r[c].toFixed(Number.isInteger(r[c])?0:3):r[c];}
 $(id).replaceChildren(t);
}
function openSplit(){
 $('workout').replaceChildren(...Object.keys(data.splits[$('split').value]).map(id=>new Option(id,id)));draw();
}
function draw(){
 const split=$('split').value,w=data.splits[split][$('workout').value],m=w.models[$('model').value],free=$('mode').value==='free';
 const center=free?w.mean:w.conditionalMean;
 const low=free?m.low:center.map((v,i)=>v===null?null:v-1.2815515655446004*Math.sqrt(m.h[i]));
 const high=free?m.high:center.map((v,i)=>v===null?null:v+1.2815515655446004*Math.sqrt(m.h[i]));
 function points(values){const out=[];w.t.forEach((t,i)=>{if(i&&t-w.t[i-1]!==1)out.push([t-.1,null]);out.push([t,values[i]]);});return out;}
 function line(name,values,color,dashed=false){return {name,type:'line',data:points(values),showSymbol:false,connectNulls:false,lineStyle:{width:1.2,type:dashed?'dashed':'solid'},itemStyle:{color}};}
 const opts={animation:false,tooltip:{trigger:'axis'},legend:{top:5},grid:{left:65,right:25,top:50,bottom:65},xAxis:{type:'value',name:'s'},yAxis:{type:'value',name:'W'},dataZoom:[{type:'inside'},{type:'slider'}]};
 chart.setOption({...opts,series:[line('Target',w.target,'#777'),line('Misurata',w.real,'#b7c1c7'),line('Media',center,'#087e8b'),line('P10',low,'#ba7832',true),line('P90',high,'#ba7832',true),...(free?[line('Una traiettoria',m.sample,'#a88aba')]:[])]},true);
 varianceChart.setOption({...opts,yAxis:{type:'value',name:'SD (W)'},series:[line('SD innovazioni',m.h.map(Math.sqrt),'#087e8b')]},true);
 acfChart.setOption({animation:false,tooltip:{trigger:'axis'},legend:{},grid:{left:65,right:25,bottom:40},xAxis:{type:'value',name:'lag (s)'},yAxis:{type:'value',name:'ACF z²'},series:Object.entries(w.models).map(([name,v])=>({name,type:'line',showSymbol:false,data:v.acf.map((x,i)=>[i+1,x])}))},true);
 table('summary',data.summary.filter(r=>r.split===split),['mode','model','coverage80','width80_w','interval_score80_w','nll']);drawGroups();
}
function drawGroups(){table('groups',data.groups.filter(r=>r.split===$('split').value&&r.dimension===$('dimension').value),['band','model','workouts','n','coverage80','width80_w','interval_score80_w','innovation_variance','predicted_innovation_variance']);}
$('split').onchange=openSplit;for(const id of ['workout','model','mode'])$(id).onchange=draw;$('dimension').onchange=drawGroups;
window.addEventListener('resize',()=>[chart,varianceChart,acfChart].forEach(c=>c.resize()));openSplit();
