<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {api,date} from '../api'
import type {Run,Fit} from '../types'
import {analysisRegistry} from '../models/registry'
import {compatibleParameters} from '../models/charts'
const props=defineProps<{runs:Run[]}>(),emit=defineEmits<{error:[message:string]}>()
const ids=ref(['','']),results=ref<Fit[][]>([[],[]]),loading=ref(false)
const chosen=computed(()=>ids.value.map(id=>props.runs.find(r=>r.id===id)))
const params=computed(()=>chosen.value[0]&&chosen.value[1]?compatibleParameters(chosen.value[0].model.parameters,chosen.value[1].model.parameters):[])
const adapter=computed(()=>chosen.value[0]?analysisRegistry[chosen.value[0].model.id]:undefined)
const different=computed(()=>chosen.value[0]&&chosen.value[1]&&(chosen.value[0].dataset.id!==chosen.value[1].dataset.id||JSON.stringify(chosen.value[0].split.assignments)!==JSON.stringify(chosen.value[1].split.assignments)))
watch(()=>props.runs.length,()=>{if(!ids.value[0]&&props.runs.length)ids.value[0]=props.runs[0].id;if(!ids.value[1]&&props.runs.length>1)ids.value[1]=props.runs[1].id},{immediate:true})
let version=0
watch(()=>[...ids.value, ...chosen.value.map(r=>r?.progress.done)],async()=>{const current=++version;loading.value=true;results.value=[[],[]];try{const loaded=await Promise.all(ids.value.map(id=>id?api<Fit[]>(`/runs/${id}/results`):Promise.resolve([])));if(current===version)results.value=loaded}catch(e){emit('error',(e as Error).message)}finally{if(current===version)loading.value=false}},{immediate:true})
</script>
<template>
  <div class="two-columns"><section v-for="(label,i) in ['Esperimento A','Esperimento B']" :key="label" class="card comparison-card" :class="{second:i===1}"><div class="eyebrow">{{label}}</div><label>Run<select v-model="ids[i]"><option value="">Scegli una run</option><option v-for="r in runs" :key="r.id" :value="r.id">{{r.dataset.name}} · {{r.model.id.toUpperCase()}} · {{date(r.created_at)}} · {{r.id.slice(0,6)}}</option></select></label><template v-if="chosen[i]"><h2>{{chosen[i]!.dataset.name}}</h2><dl class="properties"><div><dt>Modello</dt><dd>{{chosen[i]!.model.id.toUpperCase()}} · {{chosen[i]!.model.version}}</dd></div><div><dt>Train</dt><dd>{{chosen[i]!.progress.total}} segmenti</dd></div><div><dt>Segnali</dt><dd>{{chosen[i]!.signal==='raw'?'Originali':'Medie mobili'}}</dd></div><div><dt>Seed split / fit</dt><dd>{{chosen[i]!.split.seed}} / {{chosen[i]!.config.seed}}</dd></div><div><dt>Fit con segnalazioni</dt><dd>{{results[i].filter(f=>f.status!=='fitted'||f.warnings?.length).length}}</dd></div></dl></template></section></div>
  <section class="card"><div class="section-heading"><div><h2>Parametri a confronto</h2><p>Confronto descrittivo delle distribuzioni, senza valutazione fuori campione.</p></div><span class="pill">Train only</span></div>
    <p v-if="different" class="message warning">Dataset o segmenti train differenti: le distribuzioni non isolano l’effetto del modello.</p><p v-if="ids[0]&&ids[0]===ids[1]" class="message warning">Hai selezionato lo stesso esperimento in entrambe le colonne.</p>
    <p v-if="loading" class="muted">Caricamento…</p><component v-else-if="params.length&&adapter" :is="adapter.comparison" :parameters="params" :groups="[{name:'A',fits:results[0]},{name:'B',fits:results[1]}]"/><div v-else class="empty"><span>⊞</span><h3>Seleziona due esperimenti</h3><p>Puoi confrontare due run P1D. I modelli futuri esporranno le proprie analisi; si confronteranno soltanto parametri compatibili per nome e unità.</p></div>
  </section>
</template>
