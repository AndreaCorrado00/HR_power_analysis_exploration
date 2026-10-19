<script setup lang="ts">
import {computed} from 'vue'
import VChart from 'vue-echarts'
import {use} from 'echarts/core'
import {CanvasRenderer} from 'echarts/renderers'
import {LineChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,MarkAreaComponent} from 'echarts/components'
import {formatDuration} from '../utils'
import type {ProcessPoint} from '../processingApi'

use([CanvasRenderer,LineChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,MarkAreaComponent])
const p=defineProps<{points:ProcessPoint[]; step:number; powerRelative:boolean; hrMode:string}>()
const option=computed(()=>{
  const power=p.powerRelative?['power_w_kg','power_ma_w_kg','W/kg']:['power_w','power_ma_w','W']
  const hr=p.hrMode==='max'?['hr_pct_max','hr_ma_pct_max','% FCmax']:
    p.hrMode==='threshold'?['hr_pct_threshold','hr_ma_pct_threshold','% FC soglia']:
    ['heart_rate_bpm','heart_rate_ma_bpm','bpm']
  const gaps=p.points.slice(1).flatMap((point,i)=>point.elapsed_seconds-p.points[i].elapsed_seconds>1.5*p.step?
    [[{xAxis:p.points[i].elapsed_seconds},{xAxis:point.elapsed_seconds}]]:[])
  function data(key:string) {
    const result:unknown[]=[]
    p.points.forEach((point,i)=>{
      if(i && point.elapsed_seconds-p.points[i-1].elapsed_seconds>1.5*p.step)
        result.push([(point.elapsed_seconds+p.points[i-1].elapsed_seconds)/2,null])
      result.push([point.elapsed_seconds,point[key]])
    })
    return result
  }
  return {animation:false,legend:{top:0},grid:{left:65,right:65,top:55,bottom:75},
    tooltip:{trigger:'axis'},xAxis:{type:'value',name:'Tempo',axisLabel:{formatter:formatDuration}},
    yAxis:[{type:'value',name:power[2],scale:true},{type:'value',name:hr[2],scale:true}],
    dataZoom:[{type:'inside'},{type:'slider',bottom:10}],
    series:[
      {name:'Potenza originale',key:power[0],axis:0,color:'#93b4e4',width:1},
      {name:'Potenza media',key:power[1],axis:0,color:'#174f9b',width:2},
      {name:'HR originale',key:hr[0],axis:1,color:'#eeb3ae',width:1},
      {name:'HR media',key:hr[1],axis:1,color:'#b32d28',width:2}
    ].map((s,i)=>({name:s.name,type:'line',yAxisIndex:s.axis,showSymbol:false,connectNulls:false,
      lineStyle:{color:s.color,width:s.width},itemStyle:{color:s.color},data:data(s.key),
      ...(i===0?{markArea:{silent:true,itemStyle:{color:'#a9473620'},data:gaps}}:{})}))}
})
</script>
<template><VChart class="processing-chart" :option="option" autoresize/></template>
<style scoped>.processing-chart{height:420px;width:100%}</style>
