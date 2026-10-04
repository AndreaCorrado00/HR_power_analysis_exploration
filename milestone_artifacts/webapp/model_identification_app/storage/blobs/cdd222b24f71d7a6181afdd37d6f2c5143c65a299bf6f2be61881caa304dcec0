<script setup lang="ts">
import {computed,ref} from 'vue'
import type {Fit} from '../types'
import {fmt} from '../api'
import Chart from '../components/Chart.vue'
const props=defineProps<{fit:Fit}>()
const detail=ref(false)
const warnings:Record<string,string>={rank_deficient:'Parametri non identificabili: Jacobiano a rango ridotto',ill_conditioned:'Jacobiano mal condizionato',at_bounds:'Uno o più parametri vicini ai bounds',optimizer_not_converged:'Ottimizzatore non convergente',constant_power:'Potenza costante: manca eccitazione',autocorrelated_residuals:'Residui fortemente autocorrelati',recording_gaps:'Gap di registrazione: input mantenuto costante nel gap',irregular_sampling:'Campionamento irregolare',equivalent_predictions_different_parameters:'Predizioni equivalenti con parametri differenti',multistart_disagreement:'Le inizializzazioni non convergono tutte agli stessi parametri'}
const option=computed(()=>{
  const s=props.fit.series;if(!s)return {}
  const points=(v:number[])=>s.time.map((t,i)=>[t,v[i]])
  return {animation:false,color:['#536a80','#218576','#d49a50'],legend:{top:0,data:['HR osservata','HR prevista','Potenza']},tooltip:{trigger:'axis',confine:true},toolbox:{right:12,feature:{saveAsImage:{title:'Salva grafico'}}},axisPointer:{link:[{xAxisIndex:'all'}]},grid:[{left:60,right:62,top:48,height:'45%'},{left:60,right:62,top:'66%',height:'20%'}],xAxis:[{type:'value',name:'',gridIndex:0,axisLabel:{show:false},min:'dataMin',max:'dataMax'},{type:'value',name:'Tempo (s)',nameLocation:'middle',nameGap:25,gridIndex:1,min:'dataMin',max:'dataMax'}],yAxis:[{type:'value',name:'HR (bpm)',scale:true,gridIndex:0,splitLine:{lineStyle:{color:'#eef1ef'}}},{type:'value',name:'Potenza (W)',gridIndex:0,splitLine:{show:false}},{type:'value',name:'Residuo (bpm)',gridIndex:1,splitLine:{lineStyle:{color:'#eef1ef'}}}],dataZoom:[{type:'inside',xAxisIndex:[0,1]},{type:'slider',xAxisIndex:[0,1],bottom:0,height:18}],series:[{name:'HR osservata',type:'line',showSymbol:false,data:points(s.observed),lineStyle:{width:1.5}},{name:'HR prevista',type:'line',showSymbol:false,data:points(s.predicted),lineStyle:{width:2.5}},{name:'Potenza',type:'line',showSymbol:false,yAxisIndex:1,data:points(s.power),lineStyle:{width:1,opacity:.5},areaStyle:{opacity:.05}},{name:'Residuo',type:'line',showSymbol:false,xAxisIndex:1,yAxisIndex:2,data:points(s.residual),lineStyle:{color:'#218576',width:1.5},markLine:{silent:true,symbol:'none',label:{show:false},data:[{yAxis:0}],lineStyle:{color:'#869b95',type:'dashed'}}}]}
})
</script>
<template>
  <div v-if="fit.status==='fitted'">
    <div class="fit-metrics"><div v-for="(label,key) in {RMSE:'RMSE · bpm',residual_mean:'Bias · bpm',residual_sd:'SD residui · bpm',residual_autocorrelation_lag1:'ACF lag 1'}" :key="key"><small>{{label}}</small><strong>{{fmt(fit.metrics[key],3)}}</strong></div></div>
    <Chart v-if="fit.series" :option="option" :height="460"/>
    <div class="table-scroll"><table><thead><tr><th>Parametro</th><th>Stima</th><th>SE</th><th>CI 95%</th><th>RSE %</th></tr></thead><tbody><tr v-for="(p,key) in fit.parameters" :key="key"><td><b>{{key}}</b> <small>{{key==='K'?'bpm/W':'s'}}</small><span v-if="p.at_bound" class="tag warn">bound</span></td><td>{{fmt(p.estimate,5)}}</td><td>{{fmt(p.se,5)}}</td><td>{{p.ci95?`${fmt(p.ci95[0],5)} — ${fmt(p.ci95[1],5)}`:'n.d.'}}</td><td>{{fmt(p.rse_pct,2)}}</td></tr></tbody></table></div>
    <div class="fit-flags"><span v-for="w in fit.warnings" :key="w" class="tag warn">{{warnings[w]||w}}</span><span v-if="!fit.warnings.length" class="tag">Nessuna segnalazione automatica</span></div>
    <button class="text-button" @click="detail=!detail">{{detail?'Nascondi':'Mostra'}} diagnostica dell’ottimizzatore</button><div v-if="detail" class="diagnostics"><p>Status {{fit.optimizer.status}} · {{fit.optimizer.message}}</p><p>Rango Jacobiano {{fit.uncertainty.rank}} / 3 · condizionamento {{fmt(fit.uncertainty.jacobian_condition)}} · accordo multistart {{fit.all_starts_agree?'sì':'no'}}</p><pre>{{JSON.stringify(fit.starts,null,2)}}</pre></div>
  </div><p v-else class="message error">Fit non eseguito: {{fit.error}}</p>
</template>
