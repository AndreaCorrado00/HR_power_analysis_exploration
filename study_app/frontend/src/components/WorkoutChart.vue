<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {use} from 'echarts/core'
import {CanvasRenderer} from 'echarts/renderers'
import {LineChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent} from 'echarts/components'
import VChart from 'vue-echarts'
import {chartOption,clock} from '../charts'
import {fmt} from '../api'
use([CanvasRenderer,LineChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent])
const props=defineProps<{series:any;bands?:boolean;title?:string}>()
const pBand=ref(false),hBand=ref(false),window=ref([0,100])
const option=computed(()=>chartOption(props.series,pBand.value,hBand.value))
watch(()=>props.series,()=>window.value=[0,100])
function zoom(e:any){const v=e.batch?.[0]||e;window.value=[v.start??0,v.end??100]}
const visible=computed(()=>{
 const s=props.series,t=s.elapsed||s.elapsed_seconds||s.time||[];if(!t.length)return null
 const lo=t[0]+(t[t.length-1]-t[0])*window.value[0]/100,hi=t[0]+(t[t.length-1]-t[0])*window.value[1]/100
 const observed=s.hr||s.heart_rate_bpm,pred=s.hr_chain||s.hr_real_power
 if(!observed||!pred)return {lo,hi,n:null,mae:null,rmse:null}
 const errors=t.flatMap((v:number,i:number)=>v>=lo&&v<=hi&&observed[i]!=null&&pred[i]!=null?[observed[i]-pred[i]]:[])
 return {lo,hi,n:errors.length,mae:errors.length?errors.reduce((a:number,b:number)=>a+Math.abs(b),0)/errors.length:null,rmse:errors.length?Math.sqrt(errors.reduce((a:number,b:number)=>a+b*b,0)/errors.length):null}
})
</script>
<template><section class="chart-card"><div class="section-heading"><h3>{{title||'Traiettorie'}}</h3><div v-if="bands" class="toggles"><label><input type="checkbox" v-model="pBand"> Fascia P</label><label><input type="checkbox" v-model="hBand"> Fascia HR</label></div></div><VChart :option="option" autoresize style="height:390px;width:100%" :update-options="{notMerge:true}" @datazoom="zoom" @restore="window=[0,100]"/><p class="caption" v-if="visible">Finestra visibile {{clock(visible.lo)}}–{{clock(visible.hi)}}<span v-if="visible.n!==null"> · {{visible.n}} coppie HR · MAE {{fmt(visible.mae)}} · RMSE {{fmt(visible.rmse)}} bpm</span>. Rotella per zoom, trascina per scorrere.</p><p class="caption" v-if="bands">Fasce puntuali 95% di variabilità parziale: AR potenza e parametri HR. Esclusi rumore residuo HR e incertezza di A, HR0 e coefficienti potenza.</p></section></template>
