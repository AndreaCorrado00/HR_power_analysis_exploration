<script setup lang="ts">
import {computed,reactive,ref} from 'vue'
import {importSegments,processSegments,exportProcessed,type ProcessingDataset,type ProcessedSegment} from '../processingApi'
import type {Norm} from '../types'
import {formatDuration,normalizationError} from '../utils'
import ProcessingChart from './ProcessingChart.vue'

const dataset=ref<ProcessingDataset|null>(null),selected=ref<string[]>([]),windowSeconds=ref(3)
const filename=ref(''),busy=ref(false),error=ref(''),message=ref('')
const processed=ref<ProcessedSegment[]>([]),previewSignature=ref(''),activeId=ref('')
const powerRelative=ref(false),hrMode=ref('raw')
const norm=reactive<Norm>({weightKg:null,hrMaxBpm:null,hrThresholdBpm:null,
  normalizePower:false,normalizeHrMax:false,normalizeHrThreshold:false})
const reference=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?value:null
const options=computed(()=>({datasetId:dataset.value?.datasetId??'',selected:[...selected.value],
  windowSeconds:windowSeconds.value,normalization:{...norm,weightKg:reference(norm.weightKg),
    hrMaxBpm:reference(norm.hrMaxBpm),hrThresholdBpm:reference(norm.hrThresholdBpm)}}))
const signature=computed(()=>JSON.stringify(options.value))
const fresh=computed(()=>!!processed.value.length && signature.value===previewSignature.value)
const normError=computed(()=>normalizationError(norm.normalizePower,String(norm.weightKg??''),'Peso')||
  normalizationError(norm.normalizeHrMax,String(norm.hrMaxBpm??''),'FC massima')||
  normalizationError(norm.normalizeHrThreshold,String(norm.hrThresholdBpm??''),'FC di soglia'))
const active=computed(()=>processed.value.find(s=>s.id===activeId.value))
const activeSummary=computed(()=>dataset.value?.segments.find(s=>s.id===activeId.value))

async function upload(event:Event) {
  const input=event.target as HTMLInputElement, file=input.files?.[0]
  if(!file)return
  busy.value=true;error.value='';message.value=''
  try {
    const imported=await importSegments(file)
    dataset.value=imported;filename.value=file.name;selected.value=[];processed.value=[];previewSignature.value=''
    activeId.value='';message.value=`Importati ${imported.segments.length} segmenti.`
  } catch(e){error.value=(e as Error).message}
  finally{busy.value=false;input.value=''}
}
async function elaborate() {
  if(!selected.value.length||normError.value)return
  busy.value=true;error.value='';message.value=''
  const snapshot=signature.value
  try {
    const result=await processSegments(JSON.parse(snapshot))
    if(snapshot!==signature.value)return
    processed.value=result.segments;previewSignature.value=snapshot
    activeId.value=result.segments[0]?.id??'';powerRelative.value=false;hrMode.value='raw'
    message.value=`Elaborati ${result.segments.length} segmenti con finestra ${windowSeconds.value} s.`
  }catch(e){error.value=(e as Error).message;previewSignature.value=''}
  finally{busy.value=false}
}
async function download() {
  if(!fresh.value)return
  busy.value=true;error.value=''
  try {
    const blob=await exportProcessed(options.value),url=URL.createObjectURL(blob)
    const a=document.createElement('a');a.href=url;a.download='dataset_segments_processed.zip';a.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
    message.value='ZIP elaborato scaricato.'
  }catch(e){error.value=(e as Error).message}
  finally{busy.value=false}
}
</script>

<template>
<section class="processing-page" aria-labelledby="processing-title">
  <h2 id="processing-title">Elaborazione dataset</h2>
  <p>Importa i segmenti esportati, applica una media mobile coerente e scarica un nuovo dataset con gli originali conservati.</p>
  <label class="upload">Dataset dei segmenti (.zip)
    <input type="file" accept=".zip,application/zip" :disabled="busy" @change="upload">
  </label>
  <p v-if="busy" role="status">Elaborazione in corso…</p>
  <p v-if="error" class="error" role="alert">{{error}}</p>
  <p v-if="message" role="status">{{message}}</p>
  <template v-if="dataset">
    <p><strong>{{filename}}</strong> · {{dataset.segments.length}} segmenti</p>
    <fieldset :disabled="busy">
      <legend>Selezione dei segmenti</legend>
      <div class="actions"><button @click="selected=dataset.segments.map(s=>s.id)">Seleziona tutti</button>
        <button class="secondary" @click="selected=[]">Deseleziona tutti</button>
        <strong>{{selected.length}} / {{dataset.segments.length}} selezionati</strong></div>
      <div class="segment-table"><table>
        <thead><tr><th>Seleziona</th><th>Segmento / attività</th><th>Durata</th><th>Campioni</th><th>Qualità</th></tr></thead>
        <tbody><tr v-for="s in dataset.segments" :key="s.id">
          <td><input v-model="selected" type="checkbox" :value="s.id" :aria-label="`Seleziona ${s.id}`"></td>
          <td><strong>{{s.id}}</strong><small>{{s.activityId}} · lap {{s.firstLap}}–{{s.lastLap}}</small></td>
          <td>{{formatDuration(s.durationSeconds)}}</td><td>{{s.sampleCount}}</td>
          <td>{{s.gapCount}} gap · {{s.missing.power_w}} mancanti P · {{s.missing.heart_rate_bpm}} mancanti HR</td>
        </tr></tbody>
      </table></div>
    </fieldset>
    <fieldset :disabled="busy">
      <legend>Parametri globali · tutti i segmenti selezionati</legend>
      <label for="processing-window">Finestra media mobile</label>
      <select id="processing-window" v-model.number="windowSeconds"><option :value="3">3 s</option><option :value="5">5 s</option><option :value="10">10 s</option></select>
      <p>Media centrata su potenza e HR, interrotta ai gap e troncata ai bordi. Nessuna interpolazione. I valori mancanti si propagano nella rispettiva media.</p>
      <div class="normal">
        <label><input v-model="norm.normalizePower" type="checkbox"> W/kg</label>
        <label>Peso (kg)<input v-model.number="norm.weightKg" type="number" min="0.01" step="any" placeholder="kg" :disabled="!norm.normalizePower"></label>
        <label><input v-model="norm.normalizeHrMax" type="checkbox"> % FCmax</label>
        <label>FC massima (bpm)<input v-model.number="norm.hrMaxBpm" type="number" min="1" step="any" placeholder="bpm" :disabled="!norm.normalizeHrMax"></label>
        <label><input v-model="norm.normalizeHrThreshold" type="checkbox"> % FC soglia</label>
        <label>FC soglia (bpm)<input v-model.number="norm.hrThresholdBpm" type="number" min="1" step="any" placeholder="bpm" :disabled="!norm.normalizeHrThreshold"></label>
      </div>
      <p>Riferimenti fissi per l’intero dataset selezionato. Le normalizzazioni generano colonne distinte per originali e medie.</p>
      <p v-if="normError" class="error" role="alert">{{normError}}</p>
    </fieldset>
    <div class="actions">
      <button :disabled="busy||!selected.length||!!normError" @click="elaborate">Elabora e aggiorna anteprima</button>
      <button :disabled="busy||!fresh||!!normError" @click="download">Esporta ZIP</button>
    </div>
    <p v-if="!fresh">Aggiorna l’anteprima prima di esportare.</p>
    <section v-if="fresh" class="preview">
      <h3>Anteprima · originali e media mobile</h3>
      <label>Segmento <select v-model="activeId"><option v-for="s in processed" :key="s.id" :value="s.id">{{s.id}}</option></select></label>
      <div class="actions">
        <label v-if="norm.normalizePower"><input v-model="powerRelative" type="checkbox"> Mostra W/kg</label>
        <label>Unità HR <select v-model="hrMode"><option value="raw">bpm</option><option v-if="norm.normalizeHrMax" value="max">% FCmax</option><option v-if="norm.normalizeHrThreshold" value="threshold">% FC soglia</option></select></label>
      </div>
      <template v-if="active && activeSummary">
        <p>Finestra {{windowSeconds}} s · {{activeSummary.gapCount}} gap · {{active.points.filter(p=>p.ma_incomplete).length}} finestre incomplete ai bordi/gap.</p>
        <ProcessingChart :points="active.points" :step="activeSummary.medianStepSeconds" :power-relative="powerRelative" :hr-mode="hrMode"/>
      </template>
      <p>Elaborazione offline: la media centrata utilizza anche campioni successivi. Conservare gli originali come riferimento per la valutazione predittiva.</p>
    </section>
  </template>
</section>
</template>

<style scoped>
.processing-page{max-width:1250px;margin:0 auto}.upload,fieldset,.preview{display:block;background:white;border:1px solid #d6deea;border-radius:9px;padding:1rem;margin:1rem 0}
fieldset{min-width:0}legend{font-weight:600}input[type=file]{display:block;margin-top:.6rem}select{font:inherit;padding:.5rem;border:1px solid #aeb9c9;border-radius:5px;max-width:100%}
.normal input[type=number]{width:120px;display:block;margin-top:.3rem}.segment-table{max-height:340px;overflow:auto;margin-top:1rem}table{width:100%;border-collapse:collapse;text-align:left;font-size:.9rem}th{position:sticky;top:0;background:#e8eff6}th,td{padding:.65rem;border-bottom:1px solid #d6deea}small{display:block;color:#5d6878;overflow-wrap:anywhere}input[type=checkbox]{width:18px;height:18px}p{line-height:1.5}
</style>
