export function points(time:number[],values:(number|null)[]){
 const out:any[]=[]
 time.forEach((t,i)=>{if(i&&t-time[i-1]>1)out.push([(t+time[i-1])/2,null]);out.push([t,values[i]??null])})
 return out
}
export function clock(t:number){const s=Math.max(0,Math.round(t));return `${Math.floor(s/3600).toString().padStart(2,'0')}:${Math.floor(s/60)%60<10?'0':''}${Math.floor(s/60)%60}:${(s%60).toString().padStart(2,'0')}`}
export function chartOption(s:any,pBand=false,hBand=false){
 const t=s.elapsed||s.elapsed_seconds||s.time||[];const series:any[]=[]
 const fields=[['target','Prescrizione','#a18453',0],['power_target_w','Prescrizione ricostruita','#a18453',0],['power','P reale','#8a9b9e',0],['power_w','P reale','#8a9b9e',0],['power_mean','P prevista','#df8b46',0],['hr','HR osservata','#c65f64',1],['heart_rate_bpm','HR osservata','#c65f64',1],['hr_chain','HR prevista a priori','#186f70',1],['hr_real_power','HR diagnostica da P reale','#7165a6',1],['hr_target','HR da target diretto','#728934',1],['residual','Residuo HR','#186f70',1]]
 fields.forEach(([key,name,color,axis])=>{if(s[String(key)])series.push({name,type:'line',yAxisIndex:axis,showSymbol:false,connectNulls:false,lineStyle:{width:key==='hr_chain'?2.4:1.4,color},itemStyle:{color},data:points(t,s[String(key)]),animation:false})})
 for(const [base,enabled,axis,color,label] of [['power',pBand,0,'#df8b46','P'],['hr',hBand,1,'#186f70','HR']] as const){
  if(enabled&&s[`${base}_low`]&&s[`${base}_high`]){
   const lo=s[`${base}_low`],hi=s[`${base}_high`]
   series.push({name:`${label} · limite inferiore`,type:'line',yAxisIndex:axis,stack:base+'band',stackStrategy:'all',showSymbol:false,lineStyle:{width:1,color,opacity:.4},data:points(t,lo),animation:false})
   series.push({name:`${label} · fascia 95%`,type:'line',yAxisIndex:axis,stack:base+'band',stackStrategy:'all',showSymbol:false,lineStyle:{width:0},areaStyle:{color,opacity:.12},data:points(t,hi.map((v:any,i:number)=>v==null||lo[i]==null?null:v-lo[i])),animation:false})
  }
 }
 return {animation:false,tooltip:{trigger:'axis',valueFormatter:(v:any)=>typeof v==='number'?v.toFixed(1):v},legend:{type:'scroll',top:0},grid:{left:60,right:60,top:48,bottom:75},toolbox:{right:0,feature:{restore:{title:'Ripristina zoom'},saveAsImage:{title:'Salva immagine'}}},xAxis:{type:'value',name:'Tempo trascorso',axisLabel:{formatter:clock}},yAxis:[{type:'value',name:'Potenza · W'},{type:'value',name:'HR · bpm',scale:true}],dataZoom:[{type:'inside',filterMode:'none'},{type:'slider',bottom:12,filterMode:'none'}],series}
}
