<script setup lang="ts">
import {computed,markRaw,onBeforeUnmount,reactive,ref} from 'vue'
import type {ProcessingDataset} from '../processingApi'
import {identifyRepeats,copy,cutRanges,deleteBlocks,insertBlock,viewport,importReconstruction,mergeBlocks,moveBoundary,proposeReconstruction,splitBlock,
  type Block,type Proposal,type ReconstructionItem,type ReconstructionState} from '../reconstruction'
import ReconstructionChart from './ReconstructionChart.vue'
import {importLoaded,type LoadedRequest} from '../loadedSource'
import type {Activity} from '../types'
const props=defineProps<{loadedSelection?:LoadedRequest|null;loadedDatasetId?:string;loadedActivities?:Activity[]}>()
const loadedActivity=ref('')
interface Draft extends ReconstructionState {proposal:Proposal;cuts:number[];manual:boolean;undo:string[]}
const emit=defineEmits<{queue:[ReconstructionItem[]];review:[];dirty:[string,string]}>()
const dataset=ref<ProcessingDataset|null>(null),filename=ref(''),source=ref(''),busy=ref(false),error=ref(''),message=ref('')
const drafts=reactive<Record<string,Draft>>({}),selection=ref<number[]>([]),cutTime=ref(0)
const viewStart=ref(0),viewEnd=ref(1),on=ref(30),off=ref(15),powerOn=ref(300),powerOff=ref(100),repeatFlag=ref(false)
const sessions=reactive<Record<string,{dataset:ProcessingDataset;label:string;source:string;drafts:Record<string,Draft>}>>({})
const mode=ref<'edit'|'add'|'cut'|'split'|'box'>('edit'),precise=ref(false)
const active=computed(()=>drafts[source.value]),summary=computed(()=>dataset.value?.segments.find(s=>s.id===source.value))
let request=0
onBeforeUnmount(()=>{request++})
function fail(e:unknown){error.value=(e as Error).message}
function snapshot(d:Draft){return JSON.stringify({blocks:d.blocks,constraints:d.constraints,cuts:d.cuts,manual:d.manual,sensitivity:d.sensitivity,automaticBlocks:d.automaticBlocks})}
function remember(){const d=active.value;if(d){d.undo.push(snapshot(d));if(d.undo.length>50)d.undo.shift();emit('dirty',dataset.value!.datasetId,source.value)}}
function mutate(fn:()=>void){error.value='';try{fn();message.value='Modifica in bozza: aggiorna la pre-esportazione per includerla.'}catch(e){fail(e)}}
function edit(blocks:Block[]){remember();active.value.blocks=blocks;active.value.constraints=[];active.value.manual=true}
function undo(){const d=active.value,last=d?.undo.pop();if(last){Object.assign(d,JSON.parse(last));emit('dirty',dataset.value!.datasetId,source.value);selection.value=[];message.value='Modifica annullata. Aggiorna la pre-esportazione se necessario.'}}
function saveSession(){if(dataset.value)sessions[dataset.value.datasetId]={dataset:dataset.value,label:filename.value,source:source.value,drafts:{...drafts}}}
function setDataset(next:ProcessingDataset,label:string){saveSession();dataset.value=next;filename.value=label;source.value='';for(const key in drafts)delete drafts[key];selection.value=[];mode.value='edit';precise.value=false;repeatFlag.value=false;saveSession();message.value='Caricamento aperto. Le altre bozze e la pre-esportazione sono conservate.'}
async function restoreSession(id:string){if(busy.value||id===dataset.value?.datasetId||!sessions[id])return;saveSession();const s=sessions[id];dataset.value=s.dataset;filename.value=s.label;source.value=s.source;for(const key in drafts)delete drafts[key];Object.assign(drafts,s.drafts);repeatFlag.value=false;await open()}
async function useLoaded(value:LoadedRequest){
  if(busy.value){error.value='Attendi la fine dell’operazione corrente.';return}
  const snapshot=copy(value)
  await acceptLoaded(snapshot)
}
async function acceptLoaded(value:LoadedRequest){
  busy.value=true;error.value='';request++
  let success=false
  try{const next=await importLoaded('reconstruction',value);setDataset(next,'Dal dataset caricato in Estrazione');success=true}
  catch(e){fail(e)}finally{busy.value=false}
  if(success){source.value=dataset.value!.segments[0]?.id??'';await open()}
}
function openLoadedActivity(){if(props.loadedDatasetId&&props.loadedActivities?.some(a=>a.activityId===loadedActivity.value))return useLoaded({datasetId:props.loadedDatasetId,segments:[{activityId:loadedActivity.value}]})}
defineExpose({useLoaded})
async function upload(event:Event){const input=event.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file)return;await importFile(file)}
async function importFile(file:File){busy.value=true;error.value='';request++
  try{const next=await importReconstruction(file);setDataset(next,file.name)}
  catch(e){fail(e)}finally{busy.value=false}}
async function open(){request++;selection.value=[];error.value='';mode.value='edit';precise.value=false
  if(!source.value)return
  if(active.value){viewStart.value=0;viewEnd.value=active.value.proposal.end;return}
  if(!dataset.value)return
  const id=++request,sourceId=source.value;busy.value=true
  try{
    const proposal=await proposeReconstruction(dataset.value.datasetId,sourceId,50)
    if(id!==request)return
    // Signals are immutable: avoid thousands of reactive sample objects.
    proposal.points=markRaw(proposal.points)
    const saved=proposal.saved
    drafts[sourceId]={proposal,blocks:copy(saved?.blocks??proposal.blocks),automaticBlocks:copy(saved?.automaticBlocks??proposal.blocks),
      constraints:[],sensitivity:saved?.sensitivity??50,cuts:[],manual:!!saved,undo:[]}
    viewStart.value=0;viewEnd.value=proposal.end;cutTime.value=Math.round(proposal.end/2)
    message.value=saved?'Ricostruzione salvata ripristinata.':proposal.blocks.length?'Intervalli dai lap pronti: correggili direttamente sul grafico.':'Nessun target disponibile dai lap. Premi Aggiungi e disegna un intervallo.'
  }catch(e){if(id===request)fail(e)}finally{if(id===request)busy.value=false}
}
function select(i:number,shift=false){if(shift&&selection.value.length){const anchor=selection.value[0];selection.value=Array.from({length:Math.abs(i-anchor)+1},(_,k)=>Math.min(i,anchor)+k)}else selection.value=selection.value.length===1&&selection.value[0]===i?[]:[i]}
function numeric(i:number,field:'start'|'end'|'power',event:Event){const input=event.target as HTMLInputElement,value=input.valueAsNumber
  mutate(()=>{if(!Number.isFinite(value)||value<0)throw Error('Inserisci un valore finito e non negativo.')
    if(field==='power'){const next=copy(active.value.blocks);next[i].power=value;edit(next)}
    else{if(value>active.value.proposal.end)throw Error('Il confine supera la sorgente.');edit(moveBoundary(active.value.blocks,i,field,value,[],active.value.cuts,active.value.proposal.end))}})
  input.value=String(active.value.blocks[i][field])
}
function startIdentify(){
  repeatFlag.value=!repeatFlag.value
  const powers=selection.value.map(i=>active.value.blocks[i]?.power).filter(Number.isFinite)
  if(powers.length){powerOn.value=Math.max(...powers);powerOff.value=Math.min(...powers)}
}
function prepareRepeat(){mutate(()=>{const d=active.value;edit(identifyRepeats(d.blocks,selection.value,on.value,off.value,powerOn.value,powerOff.value,d.proposal.end,d.cuts));repeatFlag.value=false})}
function selectBox(ids:number[]){selection.value=ids;mode.value='edit';repeatFlag.value=false}
function queue(){const d=active.value;if(!d||!dataset.value||!summary.value)return
  const parts=cutRanges(d.cuts,d.proposal.end)
  const items=parts.map(({start,end})=>{const points=d.proposal.points.filter(p=>p.elapsed_seconds>=start&&p.elapsed_seconds<end)
    if(!points.length)throw Error('Un taglio produce un segmento senza campioni.')
    return {key:`${dataset.value!.datasetId}:${source.value}:${start}:${end}`,datasetId:dataset.value!.datasetId,activityId:summary.value!.activityId,
      part:{sourceId:source.value,start,end,blocks:copy(d.blocks),automaticBlocks:copy(d.automaticBlocks),constraints:copy(d.constraints),sensitivity:d.sensitivity},points:copy(points),exported:false}})
  emit('queue',items);message.value=`${items.length} segmenti aggiornati nella pre-esportazione. Rimuovi lì le porzioni da escludere.`
}
function cut(){mutate(()=>{const d=active.value,t=cutTime.value;if(!Number.isFinite(t)||t<=0||t>=d.proposal.end||d.cuts.includes(t))throw Error('Scegli un tempo interno non già tagliato.')
  const ranges=cutRanges([...d.cuts,t],d.proposal.end)
  if(ranges.some(r=>!d.proposal.points.some(p=>p.elapsed_seconds>=r.start&&p.elapsed_seconds<r.end)))throw Error('Il taglio produce una porzione senza campioni.')
  remember();if(d.blocks.some(b=>b.start<t&&b.end>t))d.blocks=splitBlock(d.blocks,t,[]);d.constraints=[];d.cuts.push(t);selection.value=[];queue()})}
function setView(value:{start:number;end:number}){if(!active.value)return;const next=viewport(value.start,value.end,active.value.proposal.end);viewStart.value=next.start;viewEnd.value=next.end}
function pan(delta:number){setView({start:viewStart.value+delta,end:viewEnd.value+delta})}
function scroll(event:Event){const start=(event.target as HTMLInputElement).valueAsNumber;setView({start,end:start+viewEnd.value-viewStart.value})}
function zoom(factor=.5){const width=(viewEnd.value-viewStart.value)*factor,center=(viewStart.value+viewEnd.value)/2;setView({start:center-width/2,end:center+width/2})}
function tool(value:typeof mode.value){mode.value=mode.value===value?'edit':value}
function add(block:Block){mutate(()=>{if(active.value.cuts.some(t=>t>block.start&&t<block.end))throw Error('Il nuovo blocco attraversa un taglio.');edit(insertBlock(active.value.blocks,block,[],active.value.proposal.end));selection.value=[];mode.value='edit'})}
function cursor(t:number){cutTime.value=t;if(mode.value==='cut'){cut();mode.value='edit'}else if(mode.value==='split')mutate(()=>{edit(splitBlock(active.value.blocks,t,active.value.constraints));selection.value=[];mode.value='edit'})}
function remove(){mutate(()=>{edit(deleteBlocks(active.value.blocks,selection.value,[]));selection.value=[]})}
const chosen=computed(()=>selection.value.length===1?active.value?.blocks[selection.value[0]]:null)

const modeHelp=computed(()=>({edit:'Clic per selezionare. Trascina il corpo per spostare un blocco e adattare i vicini; trascina i bordi per correggere watt e durata.',box:'Trascina un rettangolo sulla porzione temporale: selezioni tutti i blocchi che interseca.',add:'Trascina da inizio a fine intervallo: l’altezza iniziale del puntatore imposta i watt. Le parti sovrapposte vengono sostituite.',cut:'Clicca dove separare l’attività in due segmenti da esportare.',split:'Clicca dentro un rettangolo per dividerlo in due intervalli.'}[mode.value]))
</script>
<template>
<section class="reconstruction-page" aria-labelledby="reconstruction-title">
  <h2 id="reconstruction-title">Ricostruzione allenamenti</h2>
  <section class="panel">
    <strong>Dataset caricato in Estrazione</strong>
    <p v-if="!loadedDatasetId">Carica una cartella o un archivio FIT in Estrazione, poi apri qui un’attività completa o i segmenti selezionati.</p>
    <template v-else>
      <label>Attività completa<select id="loaded-activity" v-model="loadedActivity" :disabled="busy"><option value="">Seleziona attività…</option><option v-for="a in loadedActivities" :key="a.activityId" :value="a.activityId">{{a.activityId}}</option></select></label>
      <div class="actions"><button :disabled="busy||!loadedActivities?.some(a=>a.activityId===loadedActivity)" @click="openLoadedActivity">Apri attività caricata</button>
      <button :disabled="busy||!loadedSelection" @click="loadedSelection&&useLoaded(loadedSelection)">Usa segmenti in pre-esportazione</button></div>
    </template>
  </section>
  <p>Ricostruisci una possibile prescrizione a blocchi rettangolari. I watt misurati e la frequenza cardiaca restano conservati.</p>
  <label class="panel">Importa dataset segmenti o riapri una ricostruzione (.zip)<input id="reconstruction-file" type="file" accept=".zip" :disabled="busy" @change="upload"></label>
  <p v-if="error" class="error" role="alert">{{error}}</p><p v-if="message" role="status">{{message}}</p><p v-if="busy" role="status">Apertura dell’attività…</p>
  <template v-if="dataset">
    <label v-if="Object.keys(sessions).length>1" class="panel">Caricamenti della sessione<select id="reconstruction-session" :value="dataset.datasetId" :disabled="busy" @change="restoreSession(($event.target as HTMLSelectElement).value)"><option v-for="(s,id) in sessions" :key="id" :value="id">{{s.label}} · {{s.dataset.segments[0]?.activityId}} · {{s.dataset.segments.length}} segmenti</option></select></label>
    <label class="panel">{{filename}} · Apri attività / segmento <select id="reconstruction-source" v-model="source" :disabled="busy" @change="open"><option value="">Seleziona…</option><option v-for="s in dataset.segments" :key="s.id" :value="s.id">{{s.activityId}} · {{s.id}}</option></select></label>
    <template v-if="active">
      <p class="quality">{{active.proposal.laps?.length??0}} lap di riferimento · {{active.blocks.length}} intervalli · {{active.proposal.gapCount}} gap · {{active.proposal.missingPower}} campioni di potenza mancanti o non validi.
        Media mobile 5 s come riferimento visivo.</p>
      <fieldset class="panel editor" :disabled="busy">
        <legend>Ricostruisci sul grafico</legend>
        <div class="actions toolbar">
          <button :aria-pressed="mode==='edit'" @click="mode='edit'">Seleziona / modifica</button>
          <button :aria-pressed="mode==='box'" @click="tool('box')">Selezione rettangolare</button>
          <button :aria-pressed="mode==='add'" @click="tool('add')">Aggiungi</button>
          <button :aria-pressed="mode==='split'" @click="tool('split')">Dividi rettangolo</button>
          <button :aria-pressed="mode==='cut'" @click="tool('cut')">Taglia</button>
          <button class="secondary" :disabled="!active.undo.length" @click="undo">Annulla ultima modifica</button>
        </div>
        <p class="tool-help" role="status">{{modeHelp}}</p>
        <div class="actions navigation">
          <button class="secondary" aria-label="Scorri a sinistra" :disabled="viewStart<=0" @click="pan(-(viewEnd-viewStart)/2)">←</button>
          <button class="secondary" aria-label="Scorri a destra" :disabled="viewEnd>=active.proposal.end" @click="pan((viewEnd-viewStart)/2)">→</button>
          <button class="secondary" @click="zoom()">Zoom +</button><button class="secondary" @click="zoom(2)">Zoom −</button>
          <button class="secondary" @click="viewStart=0;viewEnd=active.proposal.end">Mostra tutto</button>
          <span>{{viewStart.toFixed(1)}}–{{viewEnd.toFixed(1)}} s</span>
        </div>
        <ReconstructionChart :points="active.proposal.points" :blocks="active.blocks" :constraints="active.constraints" :selected="selection" :start="viewStart" :end="viewEnd" :cuts="active.cuts" :duration="active.proposal.end" :readonly="busy" :mode="mode" @select="select" @selection="selectBox" @change="blocks=>mutate(()=>edit(blocks))" @cursor="cursor" @insert="add" @viewport="setView" @error="error=$event"/>
        <input class="timeline-scroll" aria-label="Scorri attività" type="range" min="0" :max="Math.max(0,active.proposal.end-(viewEnd-viewStart))" step="any" :value="viewStart" :disabled="viewEnd-viewStart>=active.proposal.end" @input="scroll">
        <div v-if="selection.length" class="selection-panel">
          <div class="actions">
            <strong>{{selection.length}} {{selection.length===1?'blocco selezionato':'blocchi selezionati'}}</strong>
            <span v-if="chosen">{{chosen.power}} W · {{(chosen.end-chosen.start).toFixed(1)}} s</span>
            <button v-if="chosen" class="secondary" :aria-expanded="precise" @click="precise=!precise">Valori precisi</button>
            <button class="secondary" :disabled="selection.length<2" @click="mutate(()=>{edit(mergeBlocks(active.blocks,selection,[],active.cuts));selection=[]})">Unisci blocchi</button>
            <button class="secondary" @click="remove">Elimina blocchi</button>
            <button class="secondary" @click="selection=[]">Deseleziona</button>
          </div>
          <div v-if="chosen&&precise" class="actions precise">
            <label>Inizio (s)<input type="number" :value="chosen.start" step=".1" :aria-label="`Inizio blocco ${selection[0]+1}`" @change="numeric(selection[0],'start',$event)"></label>
            <label>Fine (s)<input type="number" :value="chosen.end" step=".1" :aria-label="`Fine blocco ${selection[0]+1}`" @change="numeric(selection[0],'end',$event)"></label>
            <label>Potenza (W)<input type="number" :value="chosen.power" min="0" step="1" :aria-label="`Potenza blocco ${selection[0]+1}`" @change="numeric(selection[0],'power',$event)"></label>
          </div>
          <div v-if="selection.length>=2" class="actions">
            <button class="secondary" :aria-expanded="repeatFlag" @click="startIdentify">Identifica ripetute</button>
            <template v-if="repeatFlag"><label>ON (s)<input aria-label="Durata ON" v-model.number="on" type="number" min=".1" step=".1"></label><label>OFF (s)<input aria-label="Durata OFF" v-model.number="off" type="number" min=".1" step=".1"></label><label>Potenza ON (W)<input aria-label="Potenza ON" v-model.number="powerOn" type="number" min="0" step="1"></label><label>Potenza OFF (W)<input aria-label="Potenza OFF" v-model.number="powerOff" type="number" min="0" step="1"></label><button @click="prepareRepeat">Applica ripetute</button></template>
          </div>
          <p v-if="repeatFlag&&selection.length>=2">Mantiene i {{selection.length}} blocchi selezionati. Il primo è {{active.blocks[selection[0]].power>=active.blocks[selection[1]].power?'ON':'OFF'}}, riconosciuto dai livelli attuali. L’inizio resta fisso e il vicino successivo si adatta. Dopo l’applicazione puoi modificare tutto liberamente.</p>
        </div>
        <p v-if="active.cuts.length">Tagli: <span v-for="t in [...active.cuts].sort((a,b)=>a-b)" :key="t">{{t}} s <button class="secondary" @click="mutate(()=>{remember();active.cuts=active.cuts.filter(x=>x!==t);queue()})">Rimuovi taglio</button> </span></p>
        <div class="actions"><button @click="mutate(queue)">Aggiorna pre-esportazione</button><button class="secondary" @click="emit('review')">Apri pre-esportazione</button></div>
      </fieldset>
    </template>
  </template>
</section>
</template>
<style scoped>
.reconstruction-page{max-width:1400px;margin:auto}.panel{display:block;background:#fff;border:1px solid #d6deea;border-radius:10px;padding:1rem;margin:1rem 0;min-width:0}.panel input[type=file],select{display:block;margin-top:.5rem;max-width:100%}select{padding:.6rem;font:inherit;width:100%}input[type=range]{width:100%;margin-top:1rem}input[type=number]{width:110px}input[type=checkbox]{width:18px;height:18px}label{line-height:1.8}.actions{align-items:end}.table-scroll{max-height:300px;overflow:auto;margin:1rem 0}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:.45rem;border-bottom:1px solid #e2e8f0}th{position:sticky;top:0;background:#f1f5f9}.chosen{background:#fffbeb}.warning{background:#fff7ed;padding:.8rem;border-radius:6px;margin:.5rem 0}p{line-height:1.5}
.toolbar button[aria-pressed=true]{background:#065f46;color:white;box-shadow:0 0 0 2px #a7f3d0}.tool-help{min-height:1.5em;color:#334155}.navigation{align-items:center}.selection-panel{padding:1rem;background:#f8fafc;border-radius:8px;margin:1rem 0}.precise{margin:.75rem 0}.quality{font-size:.9rem;color:#475569}.locks{display:flex;gap:.75rem;flex-wrap:wrap}.timeline-scroll{cursor:ew-resize}.actions{flex-wrap:wrap}
</style>
