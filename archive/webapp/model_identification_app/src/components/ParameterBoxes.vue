<script setup lang="ts">
import {computed} from 'vue'
import Chart from './Chart.vue'
import {boxSummary} from '../models/charts'
import type {Fit} from '../types'
const props=defineProps<{parameters:{key:string;unit:string}[];groups:{name:string;fits:Fit[]}[]}>()
const boxes=computed(()=>props.parameters.map(p=>{
  const summaries=props.groups.map(g=>boxSummary(g.fits.filter(f=>f.status==='fitted').map(f=>f.parameters[p.key]?.estimate).filter((v):v is number=>v!==undefined)))
  return {key:p.key,unit:p.unit,counts:summaries.map(s=>s?.n||0),option:{animation:false,color:['#26776a','#df9a55'],tooltip:{trigger:'item',confine:true},grid:{top:20,left:60,right:20,bottom:50},xAxis:{type:'category',data:props.groups.map((g,i)=>`${g.name}\nn=${summaries[i]?.n||0}`),axisLabel:{width:150,overflow:'truncate'}},yAxis:{type:'value',scale:true,splitLine:{lineStyle:{color:'#ecf0ef'}}},series:[{type:'boxplot',data:summaries.map((s,i)=>({value:s?.box||[],itemStyle:{color:i?'#fbecd9':'#e1f1eb',borderColor:i?'#bf823d':'#26776a'}}))},{type:'scatter',symbolSize:6,data:summaries.flatMap((s,i)=>(s?.outliers||[]).map(v=>[i,v]))}]}}
}))
</script>
<template><div class="box-grid"><div v-for="box in boxes" :key="box.key" class="box-panel"><h3>{{box.key}} <small>{{box.unit}}</small></h3><Chart v-if="box.counts.some(n=>n>0)" :option="box.option" :height="250"/><p v-else class="empty compact">Nessuna stima disponibile</p></div></div><p class="note">Mediana, quartili e baffi fino a 1,5 × IQR. I punti esterni sono outlier; non vengono rimossi.</p></template>
