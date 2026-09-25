<script setup lang="ts">
import {computed} from 'vue';import VChart from 'vue-echarts';import {use} from 'echarts/core';import {CanvasRenderer} from 'echarts/renderers';import {LineChart} from 'echarts/charts';import {GridComponent,TooltipComponent,DataZoomComponent,MarkAreaComponent} from 'echarts/components';import type {Point,Lap} from '../types';import {formatDuration} from '../utils';
use([CanvasRenderer,LineChart,GridComponent,TooltipComponent,DataZoomComponent,MarkAreaComponent]);
const p=withDefaults(defineProps<{points:Point[],laps?:Lap[],selectedLaps?:number[],queuedLaps?:number[],detail?:boolean,duration:number}>(),{laps:()=>[],selectedLaps:()=>[],queuedLaps:()=>[],detail:false});
const lapAreas=computed(()=>p.laps.map(l=>{
  const selected=p.selectedLaps.includes(l.index),queued=p.queuedLaps.includes(l.index)
  return [{name:`Lap ${l.index}`,xAxis:l.startElapsedSeconds,
    itemStyle:{color:selected?'rgba(245,158,11,.30)':queued?'rgba(22,163,74,.20)':'rgba(37,99,235,.035)',borderColor:selected?'#b45309':queued?'#15803d':'#cbd5e1',borderWidth:selected||queued?2:1},
    label:{show:selected||queued,position:'insideTop',color:selected?'#92400e':'#166534'}}, {xAxis:l.endElapsedSeconds}]
}))
const option=computed(()=>({animation:false,grid:{left:45,right:45,top:18,bottom:p.detail?62:28},tooltip:{trigger:'axis'},xAxis:{type:'value',min:0,max:p.duration,axisLabel:{formatter:formatDuration}},yAxis:[{type:'value',name:'W',scale:true},{type:'value',name:'bpm',scale:true}],dataZoom:p.detail?[{type:'inside'},{type:'slider',bottom:10}]:[],series:[{name:'Potenza',type:'line',showSymbol:false,sampling:'lttb',lineStyle:{width:1,color:'#2563eb'},data:p.points.map(x=>[x.elapsedSeconds,x.power]),markArea:{silent:true,data:lapAreas.value}},{name:'HR',type:'line',yAxisIndex:1,showSymbol:false,sampling:'lttb',lineStyle:{width:1.5,color:'#dc2626'},data:p.points.map(x=>[x.elapsedSeconds,x.heartRate])}]}))
</script><template><VChart class="chart" :option="option" autoresize /></template>
