import type {PopulationPrediction} from './types'

export interface Review {verdict:'unreviewed'|'positive'|'negative';labels:string[];notes:string;updated_at?:string}
export interface Scale {min:number|null;max:number|null;absolute:boolean}
export interface ReviewContext {version:number;equation:string;warnings:string[];labels:Record<string,string>;verdicts:Record<string,string>;legend:string;scales:Record<string,Scale>;colors:{best:string;worst:string;neutral:string}}
export function elapsed(value:number){const s=Math.round(Math.abs(value));return (value<0?'-':'')+[Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(v=>String(v).padStart(2,'0')).join(':')}
export function metricColor(value:number|null|undefined,scale:Scale|undefined,colors:ReviewContext['colors']){
  if(value==null||!Number.isFinite(value)||!scale||scale.min==null||scale.max==null||scale.min===scale.max)return colors.neutral
  const ratio=Math.max(0,Math.min(1,((scale.absolute?Math.abs(value):value)-scale.min)/(scale.max-scale.min)))
  return '#'+[1,3,5].map(i=>Math.round(parseInt(colors.best.slice(i,i+2),16)*(1-ratio)+parseInt(colors.worst.slice(i,i+2),16)*ratio).toString(16).padStart(2,'0')).join('')
}
export function trajectory(r:PopulationPrediction,residual=false){
  const s=r.series
  const line=(name:string,values:(number|null)[],color:string,axis=0)=>({name,type:'line',showSymbol:false,xAxisIndex:axis,yAxisIndex:axis,itemStyle:{color},lineStyle:{color,width:name==='Prevista'?2:1},data:s.time.map((t,i)=>[t,values[i]])})
  const xAxis=(gridIndex:number)=>({type:'value',gridIndex,name:'Tempo (hh:mm:ss)',nameLocation:'middle',nameGap:27,axisLabel:{formatter:elapsed},axisPointer:{label:{formatter:(p:{value:number})=>elapsed(p.value)}}})
  const series=residual?[line('Osservata − prevista',s.residual,'#536a80')]:[
    line('Osservata',s.observed,'#536a80'),line('Prevista',s.predicted,'#268575'),
    ...(r.band_available===false?[]:[line('Limite 2.5%',s.lower,'#9ccab8'),line('Limite 97.5%',s.upper,'#9ccab8')]),
    {...line('Potenza',s.power,'#a07a3f',1),step:'end'}]
  return {tooltip:{trigger:'axis',formatter:(items:{axisValue:number;seriesName:string;value:[number,number|null];marker:string}[])=>
    items.length?elapsed(Number(items[0].axisValue))+'<br/>'+items.map(p=>p.marker+p.seriesName+': '+(p.value[1]==null?'n.d.':p.value[1].toLocaleString('it-IT',{maximumFractionDigits:2}))).join('<br/>'):''},legend:{top:0},axisPointer:{link:[{xAxisIndex:'all'}]},
    grid:residual?[{left:70,right:30,bottom:75,top:35}]:[{left:70,right:30,top:45,height:'45%'},{left:70,right:30,top:'66%',bottom:75}],
    xAxis:residual?[xAxis(0)]:[xAxis(0),xAxis(1)],
    yAxis:residual?[{type:'value',scale:true,name:'Residuo (bpm)'}]:[{type:'value',scale:true,name:'HR (bpm)'},{type:'value',gridIndex:1,name:'Potenza (W)'}],
    dataZoom:[{type:'inside',xAxisIndex:residual?[0]:[0,1]},{type:'slider',xAxisIndex:residual?[0]:[0,1],height:16,bottom:8,labelFormatter:elapsed}],series}
}
