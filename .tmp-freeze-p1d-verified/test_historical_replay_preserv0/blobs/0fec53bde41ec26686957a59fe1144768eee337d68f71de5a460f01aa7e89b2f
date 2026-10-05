import type {Fit} from '../types'
export const qualityLabels={RMSE:'RMSE · bpm',MAE:'MAE · bpm',bias:'Bias · bpm',R2:'R²',amplitude_ratio:'Amplitude ratio'}
export const residualLabels={residual_mean:'Media · bpm',residual_sd:'SD · bpm',residual_autocorrelation_lag1:'ACF lag 1',residual_autocorrelation_lag5:'ACF lag 5'}
export const identificationGuide=[
  'B, quando stimato, è il livello di equilibrio matematico a P₀ (bpm). Può compensarsi con K e τ: controllare CI, bounds e correlazioni; non è un indicatore fisiologico.',
  'ρ = (T − L) / τ: tempo disponibile dopo il ritardo in unità di τ. Un valore piccolo indica una porzione breve del transitorio; non applica soglie o esclusioni.',
  'Correlazioni parametriche: valori vicini a −1 o +1 indicano compensazione locale tra stime. Non misurano la qualità della traiettoria.',
  'Rango Jacobiano: confrontalo con p, il numero di parametri liberi. Se rango < p, alcune direzioni non sono identificabili localmente.',
  'Multistart: SSE simili con parametri diversi indicano ambiguità. SE e CI95 sono approssimazioni locali, condizionate a P₀ e HR₀.'
]
const base={animation:false,toolbox:{right:5,feature:{saveAsImage:{title:'Salva grafico'}}},tooltip:{trigger:'axis',confine:true},grid:{left:65,right:65,top:45,bottom:55},xAxis:{type:'value',name:'Tempo (s)',nameLocation:'middle',nameGap:30},dataZoom:[{type:'inside'},{type:'slider',height:15,bottom:0}]}
export function trajectoryOption(fit:Fit){
  const s=fit.series;if(!s)return {series:[]}
  const pre=fit.pre_window?.included_in_objective?undefined:fit.pre_window
  const preT=pre?.time||[]
  const time=[...preT,...s.time]
  const observed=[...(pre?.observed||[]),...s.observed],power=[...(pre?.power||[]),...s.power]
  return {...base,color:['#536a80','#218576','#c78b40'],legend:{data:['HR osservata','HR prevista','Power']},yAxis:[{type:'value',scale:true,name:'HR (bpm)'},{type:'value',name:'Power (W)',splitLine:{show:false}}],series:[
    {name:'HR osservata',type:'line',showSymbol:false,data:time.map((t,i)=>[t,observed[i]]),markArea:preT.length?{silent:true,itemStyle:{color:'#dbe6df80'},data:[[{name:'Pre-window',xAxis:-10},{xAxis:0}]]}:undefined},
    {name:'HR prevista',type:'line',showSymbol:false,data:s.time.map((t,i)=>[t,s.predicted[i]])},
    {name:'Power',type:'line',step:'end',showSymbol:false,yAxisIndex:1,data:time.map((t,i)=>[t,power[i]]),lineStyle:{opacity:.55,width:1}}
  ]}
}
export function residualOption(fit:Fit){
  const s=fit.series
  return {...base,yAxis:{type:'value',name:'Residuo (bpm)',scale:true},series:[{name:'Residuo',type:'line',showSymbol:false,data:s?.time.map((t,i)=>[t,s.residual[i]])||[],lineStyle:{color:'#218576'},markLine:{symbol:'none',silent:true,data:[{yAxis:0}]}}]}
}
export function acfOption(fit:Fit){
  return {animation:false,tooltip:{trigger:'axis'},grid:{left:55,right:25,top:20,bottom:45},xAxis:{type:'category',name:'Lag (campioni)',nameLocation:'middle',nameGap:28,data:fit.residual_acf?.lags||[]},yAxis:{type:'value',min:-1,max:1},series:[{name:'ACF',type:'bar',data:fit.residual_acf?.values||[],itemStyle:{color:'#536a80'}}]}
}
