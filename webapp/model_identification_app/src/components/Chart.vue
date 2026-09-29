<script setup lang="ts">
import {use,connect,disconnect} from 'echarts/core'
import {onMounted,onBeforeUnmount} from 'vue'
import {CanvasRenderer} from 'echarts/renderers'
import {LineChart,BoxplotChart,ScatterChart,BarChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent,MarkLineComponent,MarkAreaComponent} from 'echarts/components'
import VChart from 'vue-echarts'
use([CanvasRenderer,LineChart,BoxplotChart,ScatterChart,BarChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent,MarkLineComponent,MarkAreaComponent])
const props=defineProps<{option:any;height?:number;group?:string}>()
onMounted(()=>{if(props.group)connect(props.group)})
onBeforeUnmount(()=>{if(props.group)disconnect(props.group)})
</script>
<template><VChart :option="option" :group="group" :style="{height:(height||300)+'px',width:'100%'}" autoresize :update-options="{notMerge:true}" /></template>
