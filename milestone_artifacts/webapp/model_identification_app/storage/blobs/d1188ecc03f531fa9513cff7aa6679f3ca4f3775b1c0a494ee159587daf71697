<script setup lang="ts">
import {computed} from 'vue'
import type {Fit} from '../types'
import {fmt} from '../api'
import {qualityLabels,residualLabels,identificationGuide} from '../models/diagnostics'
import {boxSummary} from '../models/charts'
import Chart from './Chart.vue'
const props=defineProps<{fits:Fit[];hasTau:boolean}>()
const stats=(key:string)=>{const v=props.fits.map(f=>f.metrics?.[key]).filter((v):v is number=>typeof v==='number'&&Number.isFinite(v));return {n:v.length,median:boxSummary(v)?.box[2],mean:v.length?v.reduce((a,b)=>a+b,0)/v.length:undefined}}
const rho=computed(()=>boxSummary(props.fits.map(f=>f.rho).filter((v):v is number=>typeof v==='number')))
const rhoOption=computed(()=>({animation:false,tooltip:{trigger:'item'},grid:{left:60,right:20,top:20,bottom:35},xAxis:{type:'category',data:[`ρ · n=${rho.value?.n||0}`]},yAxis:{type:'value',scale:true},series:[{type:'boxplot',data:rho.value?[rho.value.box]:[]},{type:'scatter',data:rho.value?.outliers.map(v=>[0,v])||[]}]}))
</script>
<template>
  <section class="card"><h2>Qualità della traiettoria</h2><p class="note">Aggregati sui {{fits.length}} fit validi, senza pesatura per durata. n = valori disponibili; non è una valutazione fuori campione.</p>
    <div class="fit-metrics"><div v-for="(label,key) in qualityLabels" :key="key"><small>{{label}} · mediana</small><strong>{{fmt(stats(key).median,3)}}</strong><small>media {{fmt(stats(key).mean,3)}} · n={{stats(key).n}}</small></div></div>
    <details><summary>Residui · riepilogo</summary><div class="fit-metrics"><div v-for="(label,key) in residualLabels" :key="key"><small>{{label}} · mediana</small><strong>{{fmt(stats(key).median,3)}}</strong><small>media {{fmt(stats(key).mean,3)}} · n={{stats(key).n}}</small></div></div></details>
  </section>
  <section class="card"><h2>Identificabilità</h2><ul class="note"><li v-for="line in identificationGuide" :key="line">{{line}}</li></ul>
    <p class="note">Accordo di tutti gli start: {{fits.filter(f=>f.all_starts_agree).length}} / {{fits.length}}. Rango pieno: {{fits.filter(f=>f.uncertainty.rank===(f.uncertainty.p??Object.keys(f.parameters).length)).length}} / {{fits.length}}.</p>
    <details v-if="hasTau"><summary>Distribuzione di ρ · {{rho?.n||0}} valori disponibili</summary><Chart v-if="rho" :option="rhoOption" :height="230"/><p v-else class="note">ρ non disponibile nei risultati di questa run.</p></details><p v-else class="note">ρ non applicabile alla struttura gamma, L.</p>
  </section>
</template>
