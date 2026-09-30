<script setup lang="ts">
import {computed,onMounted,onUnmounted,ref} from 'vue'
import {api} from './api'
import type {Dataset,Model,Run} from './types'
import DatasetPage from './pages/DatasetPage.vue'
import IdentificationPage from './pages/IdentificationPage.vue'
import AnalysisPage from './pages/AnalysisPage.vue'
import ComparisonPage from './pages/ComparisonPage.vue'
import PopulationPage from './pages/PopulationPage.vue'
const pages=[{id:'datasets',label:'Dataset',hint:'Importa e suddividi',icon:'01'},{id:'identification',label:'Identificazione',hint:'Configura gli esperimenti',icon:'02'},{id:'analysis',label:'Analisi',hint:'Esplora i fit',icon:'03'},{id:'comparison',label:'Confronto',hint:'Confronta le distribuzioni',icon:'04'}]
const page=ref('datasets'),datasets=ref<Dataset[]>([]),runs=ref<Run[]>([]),models=ref<Model[]>([])
pages.push({id:'population',label:'Parametri atleta',hint:'Popolazione e previsione test',icon:'05'})
const selectedDataset=ref(localStorage.getItem('hrpower.dataset')||''), selectedRun=ref('')
const error=ref(''),notice=ref(''),busy=ref(false),storage=ref('')
const current= computed(()=>pages.find(p=>p.id===page.value)||pages[0])
const active= computed(()=>datasets.value.find(d=>d.id===selectedDataset.value))
let timer:ReturnType<typeof setInterval>
function route(){const [p,id]=location.hash.slice(1).split('/');page.value=pages.some(x=>x.id===p)?p:'datasets';if(id)selectedRun.value=id}
function navigate(p:string,id=''){location.hash=p+(id?'/'+id:'');page.value=p;if(id)selectedRun.value=id}
function select(id:string){selectedDataset.value=id;localStorage.setItem('hrpower.dataset',id)}
async function refresh(){[datasets.value,runs.value]=await Promise.all([api<Dataset[]>('/datasets'),api<Run[]>('/runs')]);if(!active.value&&datasets.value.length)select(datasets.value[0].id)}
async function act(action:()=>Promise<unknown>,message='Impostazioni salvate') {busy.value=true;error.value='';try{await action();await refresh();notice.value=message}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
onMounted(async()=>{route();window.addEventListener('hashchange',route);await act(async()=>{models.value=await api('/models');storage.value=(await api<{storage:string}>('/health')).storage},'');timer=setInterval(async()=>{if(busy.value)return;try{runs.value=await api('/runs')}catch{}},2500)})
onUnmounted(()=>{clearInterval(timer);window.removeEventListener('hashchange',route)})
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="#datasets"><span class="brand-symbol">∿</span><span>HR <b>/</b> POWER<small>RESEARCH WORKSPACE</small></span></a>
      <div class="nav-caption">ESPERIMENTI</div>
      <nav><a v-for="p in pages" :key="p.id" :href="'#'+p.id" :class="{active:page===p.id}"><span class="nav-icon">{{p.icon}}</span><span>{{p.label}}<small>{{p.hint}}</small></span><span v-if="p.id==='identification'" class="nav-count">{{runs.length}}</span></a></nav>
      <div class="sidebar-bottom"><span class="live-dot"></span> Ambiente locale<small>Singolo atleta · ciclismo<br>Potenza → frequenza cardiaca</small><span class="version">PROTOCOLLO P1D / v1.0</span></div>
    </aside>
    <main>
      <header class="topbar"><div><span class="muted">Workspace</span><span class="divider">/</span>{{current.label}}</div><span class="pill"><span class="live-dot"></span> Fit train · previsione test</span></header>
      <div class="page-header"><div><div class="eyebrow">IDENTIFICAZIONE DI SISTEMI</div><h1>{{current.label}}</h1><p>{{({datasets:'Dai segmenti selezionati a un esperimento riproducibile.',identification:'Una stima indipendente per ogni segmento del training set.',analysis:'Osserva la risposta, i residui e la precisione delle stime.',comparison:'Due esperimenti, le loro distribuzioni di parametri.',population:'Dai parametri del training alla previsione HR su dati non osservati.'} as Record<string,string>)[page]}}</p></div><div class="context"><small>DATASET ATTIVO</small><strong>{{active?.name||'Nessun dataset'}}</strong></div></div>
      <div v-if="error" class="message error" role="alert">{{error}}<button @click="error=''" aria-label="Chiudi errore">×</button></div>
      <div v-if="notice" class="message success" role="status">{{notice}}<button @click="notice=''" aria-label="Chiudi messaggio">×</button></div>
      <div v-if="busy" class="working" role="status">Operazione in corso…</div>
      <DatasetPage v-if="page==='datasets'" :datasets="datasets" :selected="selectedDataset" :busy="busy" :act="act" @select="select" @next="navigate('identification')"/>
      <IdentificationPage v-if="page==='identification'" :datasets="datasets" :selected="selectedDataset" :models="models" :runs="runs" :busy="busy" :act="act" @select="select" @open="id=>navigate('analysis',id)"/>
      <AnalysisPage v-if="page==='analysis'" :runs="runs" :selected="selectedRun" @select="id=>navigate('analysis',id)" @error="error=$event"/>
      <ComparisonPage v-if="page==='comparison'" :runs="runs" @error="error=$event"/>
      <PopulationPage v-if="page==='population'" :runs="runs" :selected="selectedRun" @select="id=>navigate('population',id)" @error="error=$event"/>
      <footer><span>Identificazione sul train · previsione test nella pagina Parametri atleta</span><details><summary>Persistenza locale</summary><code>{{storage}}</code></details></footer>
    </main>
  </div>
</template>
