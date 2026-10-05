<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {api,fmt} from '../api'
import type {Dataset} from '../types'
const props=defineProps<{datasets:Dataset[];selected:string;busy:boolean;act:(f:()=>Promise<unknown>,message?:string)=>Promise<void>}>()
const emit=defineEmits<{select:[id:string];next:[]}>()
const sources=ref<string[]>([]),paths=ref<string[]>([]),name=ref(''),files=ref<File[]>([])
const groups=ref<string[]>([]),labels=ref<string[]>([]),subsetName=ref(''),rename=ref('')
const percentages=ref([70,10,20]),seed=ref(60),unit=ref('segment')
const ds=computed(()=>props.datasets.find(d=>d.id===props.selected))
const activityCount=computed(()=>ds.value?.segments.filter(s=>s.kind==='activity').length||0)
const qualityRows=computed(()=>ds.value?.segments.filter(s=>s.kind==='activity'&&s.warnings.length)||[])
const availableGroups=computed(()=>[...new Set(ds.value?.segments.map(s=>s.group)||[])].sort())
const availableLabels=computed(()=>[...new Set(ds.value?.segments.map(s=>s.label)||[])].sort())
const filtered=computed(()=>ds.value?.segments.filter(s=>groups.value.includes(s.group)&&labels.value.includes(s.label))||[])
const filteredMean=computed(()=>filtered.value.reduce((n,s)=>n+s.duration_seconds,0)/(filtered.value.length||1))
watch(()=>ds.value?.id,()=>{groups.value=[...availableGroups.value];labels.value=[...availableLabels.value];rename.value=ds.value?.name||'';percentages.value=[...(ds.value?.split?.percentages||[70,10,20])];seed.value=ds.value?.split?.seed??60;unit.value=ds.value?.split?.unit||(activityCount.value?'activity':'segment');subsetName.value=''}, {immediate:true})
onMounted(()=>props.act(async()=>{sources.value=await api('/sources')},''))
function chooseFiles(e:Event){files.value=Array.from((e.target as HTMLInputElement).files||[])}
function importSource(upload=false){props.act(async()=>{let result:Dataset;if(upload){const data=new FormData();data.set('name',name.value||'Dataset importato');files.value.forEach(f=>data.append('files',f));result=await api('/datasets/upload','POST',data)}else result=await api('/datasets/import','POST',{paths:paths.value,name:name.value||'Dataset importato'});emit('select',result.id)},'Dataset importato e conservato su disco')}
function createSubset(){props.act(async()=>{const result=await api<Dataset>(`/datasets/${props.selected}/subset`,'POST',{name:subsetName.value||`${ds.value?.name} · ${groups.value.map(g=>'G'+g).join('+')} ${labels.value.join('+')}`,groups:groups.value,labels:labels.value});emit('select',result.id)},'Sottoinsieme creato; configura il suo split')}
</script>

<template>
  <div class="two-columns dataset-columns">
    <section class="card"><div class="card-heading"><span class="step">01</span><div><h2>Importa attività o segmenti</h2><p>CSV di segmenti, FIT di attività e archivi ZIP</p></div></div>
      <label>Nome del dataset<input v-model="name" placeholder="Es. UtD · segmenti brevi" maxlength="120"></label>
      <label>File nella cartella sorgente</label><div class="source-list"><label v-for="source in sources" :key="source" class="check"><input type="checkbox" :value="source" v-model="paths"><span>{{source}}</span></label><p v-if="!sources.length" class="muted">Nessuna sorgente trovata. Puoi caricare i file dal computer.</p></div>
      <button class="primary full" :disabled="busy||!paths.length" @click="importSource()">Importa dalla sorgente <span>↗</span></button>
      <div class="or"><span>oppure</span></div><label class="upload-area"><strong>Carica dal computer</strong><span>Più CSV, FIT, ZIP o manifest JSON · max 256 MiB</span><input type="file" multiple accept=".csv,.fit,.zip,.json" @change="chooseFiles"></label>
      <button v-if="files.length" class="secondary full" :disabled="busy" @click="importSource(true)">Importa {{files.length}} file selezionati</button>
      <p class="note">I dati vengono copiati senza filtraggi aggiuntivi. Le sorgenti restano inalterate. Gli ZIP con collegamenti ai FIT vanno importati dalla cartella sorgente; per il caricamento usare ZIP con i file reali.</p>
    </section>
    <section class="card"><div class="card-heading"><span class="step">02</span><div><h2>Seleziona il dataset</h2><p>{{datasets.length}} dataset disponibili al riavvio</p></div></div>
      <label>Dataset salvati<select :value="selected" @change="emit('select',($event.target as HTMLSelectElement).value)"><option value="" disabled>Scegli un dataset</option><option v-for="d in datasets" :value="d.id" :key="d.id">{{d.name}} · {{d.stats.count}} serie</option></select></label>
      <template v-if="ds">
        <div class="stats-grid"><div><small>SERIE</small><strong>{{ds.stats.count}}</strong></div><div><small>DURATA MEDIA ± SD</small><strong>{{fmt(ds.stats.duration_mean)}} <em>± {{fmt(ds.stats.duration_sd)}} s</em></strong></div></div>
        <div class="inline"><input v-model="rename" aria-label="Nuovo nome dataset" maxlength="120"><button class="secondary" :disabled="busy||!rename.trim()" @click="act(()=>api(`/datasets/${selected}`,'PATCH',{name:rename}),'Dataset rinominato')">Rinomina</button></div>
        <p v-if="activityCount" class="note">{{activityCount}} attività complete · {{ds.segments.length-activityCount}} segmenti. Ogni FIT conserva i campioni originali, senza interpolazione. Le attività non ricevono classificazioni G1/G2 o UtD/DtU.</p>
        <details v-if="qualityRows.length" class="note warning"><summary>{{qualityRows.length}} attività con anomalie nei dati</summary><p>I campioni mancanti sono conservati e impediscono il fitting della serie con i modelli attuali. I gap sono segnalati, senza ricampionamento.</p><ul><li v-for="s in qualityRows" :key="s.id">{{s.filename}} — potenza mancante: {{s.quality?.missing_power_samples||0}}, HR mancante: {{s.quality?.missing_hr_samples||0}}, gap: {{s.quality?.gap_count||0}}. {{s.warnings.join(', ')}}</li></ul></details>
        <hr><h3>Crea un sottoinsieme</h3><p class="muted">Combina gruppo di durata e tipo di transizione.</p>
        <label>Gruppi</label><div class="choices"><label v-for="g in availableGroups" :key="g"><input type="checkbox" :value="g" v-model="groups">{{g==='unknown'?'Non classificato':'G'+g}}</label></div>
        <label>Transizioni</label><div class="choices"><label v-for="l in availableLabels" :key="l"><input type="checkbox" :value="l" v-model="labels">{{l==='unknown'?'Non classificato':l}}</label></div>
        <div class="selection-summary">{{filtered.length}} segmenti selezionati <span>· media {{fmt(filteredMean)}} s</span></div>
        <div class="inline"><input v-model="subsetName" placeholder="Nome del sottoinsieme (facoltativo)" aria-label="Nome del sottoinsieme"><button class="secondary" :disabled="busy||!filtered.length" @click="createSubset">Crea dataset</button></div>
      </template><div v-else class="empty"><span>▤</span><h3>La tua base di esperimenti</h3><p>Importa un dataset per vedere durata, gruppi e split.</p></div>
    </section>
  </div>
  <section v-if="ds" class="card split-card"><div class="card-heading"><span class="step">03</span><div><h2>Suddivisione del dataset</h2><p>Lo split riguarda tutte le serie di <b>{{ds.name}}</b>. Per applicare i filtri, crea prima il sottoinsieme.</p></div></div>
    <div class="split-controls"><label v-for="(label,i) in ['Train %','Validation %','Test %']" :key="label">{{label}}<input type="number" min="0" max="100" step="1" v-model.number="percentages[i]"></label><label>Seed<input type="number" min="0" max="4294967295" v-model.number="seed"></label><label>Unità dello split<select v-model="unit" aria-label="Unità dello split"><option value="segment">Segmento intero</option><option value="activity">Attività (FIT)</option></select></label><button class="primary" :disabled="busy||Math.abs(percentages.reduce((a,b)=>a+b,0)-100)>.00001" @click="act(()=>api(`/datasets/${selected}/split`,'POST',{percentages,seed,unit}),'Split salvato; le run precedenti mantengono il proprio split')">Salva split</button></div>
    <p class="note">Mai campioni casuali. Per attività, le percentuali si applicano ai gruppi FIT; la quota effettiva dei segmenti può variare. Segmenti sovrapposti richiedono lo split per attività.</p>
    <template v-if="ds.split"><div class="split-bar"><div v-for="(part,i) in ['train','val','test']" :key="part" :class="part" :style="{flex:ds.split.assignments[part].length||.1}"></div></div><div class="split-legend"><span v-for="(part,i) in ['train','val','test']" :key="part"><i :class="part"></i>{{['Train','Validation','Test'][i]}} <b>{{ds.split.assignments[part].length}}</b> <small>({{fmt(ds.split.actual_percentages[i],1)}}%)</small></span><button class="text-button" @click="emit('next')">Vai all’identificazione →</button></div><p v-if="ds.split.warnings.length" class="note warning">Uno o più insiemi riservati sono vuoti: il numero di gruppi è limitato.</p></template>
  </section>
</template>
