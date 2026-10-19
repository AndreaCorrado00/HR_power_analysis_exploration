<script setup lang="ts">
import {computed,reactive,ref,watch} from 'vue'
import SignalChart from './components/SignalChart.vue'
import DatasetBrowser from './components/DatasetBrowser.vue'
import NotificationToasts from './components/NotificationToasts.vue'
import ProcessingPage from './components/ProcessingPage.vue'
import ReconstructionPage from './components/ReconstructionPage.vue'
import ReconstructionChart from './components/ReconstructionChart.vue'
import {exportReconstruction,type ReconstructionItem} from './reconstruction'
import type {LoadedRequest} from './loadedSource'
import {notify} from './notifications'
import {exportZip,loadDataset,preview,series} from './api'
import type{Activity,ExportSegment,Inventory,Norm,Point}from'./types'
import{formatDuration,initialSegments,mergeSegments,normalizationError,undoMerge,type LapSegment}from'./utils'

const path=ref(''),maxHours=ref<number|null>(null),inventory=ref<Inventory|null>(null),loading=ref(false)
const browser=ref(false)
const page=ref('extraction')
const reconstructed=ref<ReconstructionItem[]>([]),exportBusy=ref(false),extractedSaved=ref<string[]>([])
const totalQueued=computed(()=>cart.value.length+reconstructed.value.length)
const extractionKey=(s:ExportSegment)=>JSON.stringify([s.activityId,s.firstLap,s.lastLap,norm])
function dirtyReconstruction(datasetId:string,sourceId:string){for(const item of reconstructed.value)if(item.datasetId===datasetId&&item.part.sourceId===sourceId){item.stale=true;item.exported=false}}
function queueReconstruction(items:ReconstructionItem[]){if(!items.length)return;const first=items[0];reconstructed.value=reconstructed.value.filter(x=>x.datasetId!==first.datasetId||x.part.sourceId!==first.part.sourceId).concat(items);notify(`${items.length} segmenti di ricostruzione in pre-esportazione`)}
const cache=reactive<Record<string,Point[]>>({}),selected=ref<Activity|null>(null),detail=ref<Point[]>([])
const partitions=ref<LapSegment[]>([]),chosen=ref<number[]>([]),cart=ref<ExportSegment[]>([]),review=ref(false),destination=ref('')
const processingPage=ref<InstanceType<typeof ProcessingPage>|null>(null),reconstructionPage=ref<InstanceType<typeof ReconstructionPage>|null>(null)
const loadedSelection=computed<LoadedRequest|null>(()=>inventory.value?.datasetId&&cart.value.length?{
  datasetId:inventory.value.datasetId,segments:cart.value.map(({activityId,firstLap,lastLap})=>({activityId,firstLap,lastLap}))}:null)
const loadedActivities=computed(()=>inventory.value?[...inventory.value.extractable,...inventory.value.excluded].filter(a=>a.recordCount>0):[])
async function sendSelection(target:'processing'|'reconstruction',whole=false){
  if(!inventory.value?.datasetId||!selected.value)return
  const activityId=selected.value.activityId
  const segments=whole?[{activityId}]:chosen.value.map(i=>({activityId,firstLap:partitions.value[i].laps[0],lastLap:partitions.value[i].laps.at(-1)!}))
  if(!segments.length)return
  const request={datasetId:inventory.value.datasetId,segments}
  page.value=target;selected.value=null
  await (target==='processing'?processingPage.value:reconstructionPage.value)?.useLoaded(request)
}
const selectedLaps=computed(()=>chosen.value.flatMap(i=>partitions.value[i]?.laps??[]))
const queuedLaps=computed(()=>selected.value?.laps.filter(l=>cart.value.some(s=>s.activityId===selected.value!.activityId&&l.index>=s.firstLap&&l.index<=s.lastLap)).map(l=>l.index)??[])
const norm=reactive<Norm>({weightKg:null,hrMaxBpm:null,hrThresholdBpm:null,normalizePower:false,normalizeHrMax:false,normalizeHrThreshold:false})
const normError=computed(()=>normalizationError(norm.normalizePower,String(norm.weightKg??''),'Peso')||normalizationError(norm.normalizeHrMax,String(norm.hrMaxBpm??''),'FC massima')||normalizationError(norm.normalizeHrThreshold,String(norm.hrThresholdBpm??''),'FC di soglia'))
watch(normError,value=>{if(value)notify(value,'error')})
function validNormalization(){if(normError.value){notify(normError.value,'error');return false}return true}

async function load(folder='',selectedFiles:string[]|null=null){loading.value=true;try{const next=await loadDataset(path.value,maxHours.value?maxHours.value*3600:null,folder,selectedFiles);for(const key of Object.keys(cache))delete cache[key];cart.value=[];extractedSaved.value=[];selected.value=null;review.value=false;inventory.value=next;for(const a of [...next.extractable,...next.excluded].filter(a=>a.recordCount>0))series(a.activityId).then(x=>cache[a.activityId]=x).catch(e=>notify((e as Error).message,'error'))}catch(e){notify((e as Error).message,'error')}finally{loading.value=false}}
function importSelection(s:{path:string;folder:string;selectedFiles:string[]|null}){path.value=s.path;browser.value=false;load(s.folder,s.selectedFiles)}
async function open(a:Activity){try{const points=cache[a.activityId]||await series(a.activityId);selected.value=a;detail.value=points;partitions.value=initialSegments(a.laps);chosen.value=[]}catch(e){notify((e as Error).message,'error')}}
function toggle(i:number){chosen.value=chosen.value.includes(i)?chosen.value.filter(x=>x!==i):[...chosen.value,i].sort((a,b)=>a-b)}
function merge(){try{const first=Math.min(...chosen.value);partitions.value=mergeSegments(partitions.value,chosen.value);chosen.value=[first]}catch(e){notify((e as Error).message,'error')}}
function split(i:number){partitions.value=undoMerge(partitions.value,i);chosen.value=[]}
async function addSelected(){if(!selected.value||!validNormalization())return;try{let added=0;for(const i of chosen.value){const group=partitions.value[i],firstLap=group.laps[0],lastLap=group.laps.at(-1)!;const key=`${selected.value.activityId}:${firstLap}-${lastLap}`;if(cart.value.some(x=>`${x.activityId}:${x.firstLap}-${x.lastLap}`===key))continue;const points=await preview(selected.value.activityId,firstLap,lastLap,norm);cart.value.push({activityId:selected.value.activityId,firstLap,lastLap,points,durationSeconds:points.at(-1)?.elapsedSeconds||0,sampleCount:points.length});added++}chosen.value=[];notify(added?`${added} segmenti aggiunti all'esportazione`:'I segmenti selezionati sono già in esportazione')}catch(e){notify((e as Error).message,'error')}}
function removeSegment(i:number){cart.value.splice(i,1)}
async function openReview(){if(cart.value.length&&!validNormalization())return;try{for(const item of cart.value){item.points=await preview(item.activityId,item.firstLap,item.lastLap,norm);item.durationSeconds=item.points.at(-1)?.elapsedSeconds||0;item.sampleCount=item.points.length}review.value=true}catch(e){notify((e as Error).message,'error')}}
async function doExport(){
  if(!totalQueued.value||reconstructed.value.some(x=>x.stale)||exportBusy.value||(cart.value.length&&!validNormalization()))return
  exportBusy.value=true
  const rec=[...reconstructed.value],keys=cart.value.map(extractionKey)
  try{
    const extraction=cart.value.length?{segments:cart.value.map(({activityId,firstLap,lastLap})=>({activityId,firstLap,lastLap})),normalization:{...norm}}:null
    const r=rec.length?await exportReconstruction(rec,extraction):await exportZip(cart.value,norm,destination.value)
    if(r.headers.get('content-type')?.includes('zip')){const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download=rec.length?'dataset_segments_reconstructed.zip':'dataset_segments.zip';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);notify('ZIP esportato e download avviato')}
    else notify(`Esportato in ${(await r.json()).writtenPath}`)
    for(const item of rec)item.exported=true
    extractedSaved.value=keys
  }catch(e){notify((e as Error).message,'error')}finally{exportBusy.value=false}
}

</script>

<template><main class="shell"><header><div><h1>Dataset exploration</h1><p>Potenza, frequenza cardiaca e segmenti lap</p></div><button class="cart" @click="openReview">Pre-esportazione · {{totalQueued}}</button></header>
<nav class="actions" aria-label="Pagine dataset" style="margin:0 0 1rem"><button :class="{secondary:page!=='extraction'}" :aria-pressed="page==='extraction'" @click="page='extraction'">Estrazione dataset</button><button :class="{secondary:page!=='processing'}" :aria-pressed="page==='processing'" @click="page='processing'">Elaborazione dataset</button><button :class="{secondary:page!=='reconstruction'}" :aria-pressed="page==='reconstruction'" @click="page='reconstruction'">Ricostruzione allenamenti</button></nav>
<ProcessingPage ref="processingPage" v-show="page==='processing'" :loaded-selection="loadedSelection"/>
<ReconstructionPage ref="reconstructionPage" v-show="page==='reconstruction'" :loaded-selection="loadedSelection" :loaded-dataset-id="inventory?.datasetId" :loaded-activities="loadedActivities" @queue="queueReconstruction" @dirty="dirtyReconstruction" @review="openReview"/>
<NotificationToasts/>
<div v-show="page==='extraction'">
<section class="controls"><label for="dataset-path">Percorso dataset<input id="dataset-path" v-model="path"></label><label>Durata massima (ore)<input v-model.number="maxHours" type="number" min="0" step="0.5" placeholder="Tutte"></label><button @click="browser=true" :disabled="loading">Sfoglia cartelle / ZIP</button><button @click="load()" :disabled="loading">{{loading?'Caricamento…':'Carica dataset'}}</button></section>
<DatasetBrowser v-if="browser" :initial-path="path" @close="browser=false" @choose="importSelection"/>
<section class="normal global"><strong>Normalizzazione</strong><label><input type="checkbox" v-model="norm.normalizePower"> W/kg</label><input v-model.number="norm.weightKg" type="number" placeholder="Peso kg"><label><input type="checkbox" v-model="norm.normalizeHrMax"> % FCmax</label><input v-model.number="norm.hrMaxBpm" type="number" placeholder="FC max bpm"><label><input type="checkbox" v-model="norm.normalizeHrThreshold"> % FC soglia</label><input v-model.number="norm.hrThresholdBpm" type="number" placeholder="FC soglia bpm"></section>
<template v-if="inventory"><section><h2>Attività estraibili <span>{{inventory.extractable.length}}</span></h2><div class="grid"><article v-for="a in inventory.extractable" :key="a.activityId" class="card" @click="open(a)"><div class="cardhead"><strong>{{a.activityId}}</strong><span>{{formatDuration(a.durationSeconds)}} · {{a.laps.length}} lap</span></div><SignalChart v-if="cache[a.activityId]" :points="cache[a.activityId]" :duration="a.durationSeconds"/><p v-else>Caricamento serie…</p></article></div></section>
<section><h2>Esclusi dall'estrazione <span>{{inventory.excluded.length}}</span></h2><div class="grid"><article v-for="a in inventory.excluded" :key="a.activityId" class="card excluded" @click="open(a)"><div class="cardhead"><strong>{{a.activityId}}</strong><span>{{formatDuration(a.durationSeconds)}}</span></div><SignalChart v-if="cache[a.activityId]" :points="cache[a.activityId]" :duration="a.durationSeconds"/><p class="badge">{{a.exclusionReason}}</p></article></div></section></template>

<div v-if="selected" class="overlay" @click.self="selected=null"><section class="detail"><button class="close" @click="selected=null">Chiudi</button><h2>{{selected.activityId}}</h2><SignalChart :points="detail" :laps="selected.laps" :selected-laps="selectedLaps" :queued-laps="queuedLaps" :duration="selected.durationSeconds" detail/>
<div class="actions"><button :disabled="!inventory?.datasetId||!selected.recordCount" @click="sendSelection('reconstruction',true)">Ricostruisci attività completa</button><button :disabled="!inventory?.datasetId||!chosen.length" @click="sendSelection('processing')">Elabora selezionati</button><button :disabled="!inventory?.datasetId||!chosen.length" @click="sendSelection('reconstruction')">Ricostruisci selezionati</button></div>
<p v-if="selected.extractable" class="selection-legend"><span style="color:#92400e">■ Arancione: lap selezionati</span> · <span style="color:#166534">■ Verde: già aggiunti all'esportazione</span></p>
<template v-if="selected.extractable"><h3>Costruisci i segmenti</h3><p>Seleziona segmenti adiacenti per unirli. Seleziona i segmenti finali da aggiungere all'esportazione.</p><div class="segments"><div v-for="(g,i) in partitions" :key="g.laps.join('-')" class="segment" :class="{active:chosen.includes(i)}"><button @click="toggle(i)">Lap {{g.laps[0]}}{{g.laps.length>1?`–${g.laps.at(-1)}`:''}}</button><button v-if="g.laps.length>1" class="secondary" @click="split(i)">Annulla unione</button></div></div><div class="actions"><button @click="merge" :disabled="chosen.length<2">Unisci selezionati</button><button @click="addSelected" :disabled="!chosen.length">Aggiungi selezionati all'esportazione</button></div></template><p v-else class="badge">{{selected.exclusionReason}}</p></section></div>

</div>
<div v-if="review" class="overlay review" @click.self="review=false"><section class="detail"><button class="close" @click="review=false">Chiudi</button><h2>Pre-esportazione <span>{{totalQueued}}</span></h2><p v-if="!totalQueued">Nessun segmento selezionato.</p><div class="review-grid"><article v-for="(s,i) in cart" :key="`${s.activityId}:${s.firstLap}-${s.lastLap}`" class="review-card"><div class="cardhead"><strong>{{s.activityId}} · lap {{s.firstLap}}{{s.lastLap>s.firstLap?`–${s.lastLap}`:''}}</strong><button class="danger" @click="removeSegment(i)">Rimuovi</button></div><p><strong>Estrazione dataset</strong> - {{extractedSaved.includes(extractionKey(s))?'Esportato':'In coda'}}</p><p>{{formatDuration(s.durationSeconds)}} · {{s.sampleCount}} campioni</p><SignalChart :points="s.points" :duration="s.durationSeconds"/></article><article v-for="(s,i) in reconstructed" :key="s.key" class="review-card"><div class="cardhead"><strong>{{s.activityId}} - {{s.part.sourceId}}</strong><button class="danger" :disabled="exportBusy" @click="reconstructed.splice(i,1)">Rimuovi</button></div><p><strong>Ricostruzione allenamenti</strong> - {{s.stale?'Bozza modificata: aggiorna dalla pagina di ricostruzione':s.exported?'Esportato':'In coda'}}</p><p>{{s.part.start}}-{{s.part.end}} s - {{s.points.length}} campioni</p><ReconstructionChart :points="s.points" :blocks="s.part.blocks" :start="s.part.start" :end="s.part.end" readonly/></article></div><div class="exportbar"><span v-if="cart.length">Normalizzazioni estrazione: {{norm.normalizePower?'W/kg ':''}}{{norm.normalizeHrMax?'%FCmax ':''}}{{norm.normalizeHrThreshold?'%FC soglia':'nessuna'}}</span><input v-if="!reconstructed.length" v-model="destination" placeholder="Destinazione ZIP (opzionale)"><button @click="doExport" :disabled="!totalQueued||exportBusy||reconstructed.some(x=>x.stale)">{{exportBusy?'Esportazione...':`Esporta ${totalQueued} segmenti`}}</button></div></section></div>
</main></template>
