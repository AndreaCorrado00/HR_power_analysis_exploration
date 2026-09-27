<script setup lang="ts">
import {use} from 'echarts/core'
import {CanvasRenderer} from 'echarts/renderers'
import {LineChart,BoxplotChart,ScatterChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent,MarkLineComponent} from 'echarts/components'
import VChart from 'vue-echarts'
use([CanvasRenderer,LineChart,BoxplotChart,ScatterChart,GridComponent,TooltipComponent,LegendComponent,DataZoomComponent,ToolboxComponent,MarkLineComponent])
defineProps<{option:any;height?:number}>()
</script>
<template><VChart :option="option" :style="{height:(height||300)+'px',width:'100%'}" autoresize :update-options="{notMerge:true}" /></template>
