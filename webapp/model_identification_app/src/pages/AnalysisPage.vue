<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {api,date,statusLabel} from '../api'
import type {Run,Fit} from '../types'
import {analysisRegistry} from '../models/registry'
import RunSummary from '../components/RunSummary.vue'
const props=defineProps<{runs:Run[];selected:string}>(),emit=defineEmits<{select:[id:string];error:[message:string]}>()
const results=ref<Fit[]>([]),details=ref<Fit[]>([]),page=ref(0),loading=ref(false),onlyWarnings=ref(false)
const run=computed(()=>props.runs.find(r=>r.id===props.selected)||props.runs.at(-1))
const adapter=computed(()=>run.value?analysisRegistry[run.value.model.id]:undefined)
const filtered=computed(()=>results.value.filter(f=>!onlyWarnings.value||f.status!=='fitted'||f.warnings?.length))
const maxPage=computed(()=>Math.max(0,Math.ceil(filtered.value.length/4)-1))
const fits=computed(()=>results.value.filter(f=>f.status==='fitted'))
const exporting=ref(false)
async function download(kind:'pdf'|'tables'){
  const current=run.value;if(!current)return
  exporting.value=true
  try{
    const response=await fetch(`/api/runs/${current.id}/exports/${kind}`,{method:'POST'})
    if(!response.ok){const e=await response.json();throw new Error(e.detail||'Export non riuscito')}
    const url=URL.createObjectURL(await response.blob()),a=document.createElement('a')
    a.href=url;a.download=`${current.id}_${kind==='pdf'?'report.pdf':'tables.zip'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
  }catch(e){emit('error',(e as Error).message)}finally{exporting.value=false}
}
let resultVersion=0,detailVersion=0
async function loadResults(){const version=++resultVersion;if(!run.value){results.value=[];details.value=[];return}try{const data=await api<Fit[]>(`/runs/${run.value.id}/results`);if(version===resultVersion)results.value=data}catch(e){emit('error',(e as Error).message)}}
async function loadDetails(){const version=++detailVersion;details.value=[];if(!run.value)return;loading.value=true;try{const data=await Promise.all(filtered.value.slice(page.value*4,page.value*4+4).map(f=>api<Fit>(`/runs/${run.value!.id}/segments/${f.segment_id}`)));if(version===detailVersion)details.value=data}catch(e){emit('error',(e as Error).message)}finally{if(version===detailVersion)loading.value=false}}
watch(()=>run.value?.id,()=>{page.value=0;results.value=[];loadResults()},{immediate:true})
watch(()=>run.value?.progress.done,loadResults)
watch([page,filtered],()=>{page.value=Math.min(page.value,maxPage.value);loadDetails()})
</script>
<template>
  <section class="card compact-card"><label>Esperimento<select :value="run?.id||''" @change="emit('select',($event.target as HTMLSelectElement).value)"><option value="" disabled>Scegli una run</option><option v-for="r in runs" :key="r.id" :value="r.id">{{r.dataset.name}} · {{r.model.id.toUpperCase()}} · {{date(r.created_at)}} · {{r.id.slice(0,6)}}</option></select></label></section>
  <div v-if="!run" class="card empty"><span>∿</span><h2>I fit compariranno qui</h2><p>Avvia un esperimento dalla pagina Identificazione.</p><a href="#identification" class="primary">Configura una run →</a></div>
  <template v-else>
    <section class="analysis-banner"><div><span class="badge" :class="run.status">{{statusLabel(run.status)}}</span><h2>{{run.dataset.name}}</h2><p>{{fits.length}} fit validi / {{run.progress.total}} segmenti train · {{run.columns.join(' → ')}} · {{run.config.model_structure||'P1D storico'}}</p></div><div class="inline"><a :href="`/api/runs/${run.id}/manifest`" class="secondary">Manifest ↓</a><button class="secondary" :disabled="exporting||['running','queued'].includes(run.status)" @click="download('tables')">Export CSV</button><button class="primary" :disabled="exporting||['running','queued'].includes(run.status)" @click="download('pdf')">{{exporting?'Esportazione…':'Export PDF'}}</button></div></section>
    <p v-if="run.error" class="message error">{{run.error}}</p><p v-if="run.code_changed_since_original" class="message warning">Questa riesecuzione usa una versione del codice differente dall’esperimento originale; entrambe sono tracciate nei manifest.</p>
    <template v-if="adapter"><RunSummary :fits="fits" :has-tau="run.model.parameters.some(p=>p.key==='tau')"/><section class="card"><div class="section-heading"><div><h2>Precisione e distribuzione dei parametri</h2><p>Stime dei fit validi, incluse quelle con segnalazioni. SE, CI95 e RSE nelle schede segmento.</p></div><span class="pill">{{fits.length}} segmenti</span></div><component :is="adapter.distribution" :parameters="run.model.parameters" :groups="[{name:'Train',fits}]"/><p class="note warning">CI locali approssimati, condizionati a P₀ e HR₀. Autocorrelazione, bounds e scarsa identificabilità possono rendere ottimistica la precisione stimata.</p></section>
      <div class="section-heading fit-heading"><div><h2>Fit dei segmenti</h2><p>HR osservata, previsione e residui · zoom temporale sincronizzato</p></div><label class="check"><input type="checkbox" v-model="onlyWarnings">Solo segnalazioni / errori</label></div>
      <div class="pagination"><span>{{filtered.length}} segmenti · pagina {{page+1}} di {{maxPage+1}}</span><div><button class="secondary" :disabled="page===0" @click="page--">← Precedente</button><button class="secondary" :disabled="page>=maxPage" @click="page++">Successiva →</button></div></div>
      <p v-if="loading" class="muted">Caricamento dei grafici…</p><p v-if="!filtered.length" class="card empty compact">Nessun risultato disponibile per questa selezione.</p>
      <article v-for="fit in details" :key="fit.segment_id" class="card fit-card"><div class="fit-title"><div><small>SEGMENTO TRAIN</small><h3>{{fit.filename.split('::').at(-1)}}</h3></div><span class="tag">{{fit.segment_id.slice(0,8)}}</span></div><component :is="adapter.fit" :fit="fit"/></article>
      <div v-if="filtered.length>4" class="pagination"><span>Pagina {{page+1}} di {{maxPage+1}}</span><div><button class="secondary" :disabled="page===0" @click="page--">← Precedente</button><button class="secondary" :disabled="page>=maxPage" @click="page++">Successiva →</button></div></div>
    </template><p v-else class="message warning">Nessun modulo di analisi registrato per questo modello. Il manifest resta disponibile.</p>
  </template>
</template>
