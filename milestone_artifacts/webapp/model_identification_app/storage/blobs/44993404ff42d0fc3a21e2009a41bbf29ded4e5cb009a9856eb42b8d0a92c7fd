<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {api,date} from '../api'
import type {Run,Population,PopulationConfig,PopulationPrediction,PopulationFitCorrelations} from '../types'
import Chart from '../components/Chart.vue'
const props=defineProps<{runs:Run[];selected:string}>(),emit=defineEmits<{select:[id:string];error:[message:string]}>()
const run=computed(()=>props.runs.find(r=>r.id===props.selected)||props.runs.at(-1))
const analysis=ref<(Population & PopulationFitCorrelations)|null>(null),loading=ref(false),busy=ref(false),exporting=ref(false),testId=ref('')
const defaults=():PopulationConfig=>({max_rse_pct:100,max_correlation:.98,exclude_near_bounds:false,draws:200,seed:42})
const config=ref(defaults())
const compatible=computed(()=>run.value?.config.initialization_mode==='estimated_equilibrium'&&run.value?.config.model_structure==='p1d_full')
const completed=computed(()=>['completed','completed_with_errors'].includes(run.value?.status||''))
const selectedTest=computed(()=>analysis.value?.test.find(t=>t.segment_id===testId.value)||analysis.value?.test[0])
const changed=computed(()=>analysis.value&&JSON.stringify(config.value)!==JSON.stringify(analysis.value.config))
const fmt=(v:number|null|undefined)=>v==null?'n.d.':Number(v.toPrecision(5)).toLocaleString('it-IT')
let version=0
watch(()=>run.value?.id,async id=>{
  const ticket=++version;analysis.value=null;config.value=defaults();testId.value=''
  if(!id)return
  loading.value=true
  try{const data=await api<Population|null>(`/runs/${id}/population`);if(ticket===version){analysis.value=data;if(data)config.value={...data.config}}}
  catch(e){if(ticket===version)emit('error',(e as Error).message)}finally{if(ticket===version)loading.value=false}
},{immediate:true})
async function estimate(){
  if(!run.value)return
  const id=run.value.id,ticket=version;busy.value=true
  try{const data=await api<Population>(`/runs/${id}/population`,'POST',config.value);if(ticket===version){analysis.value=data;config.value={...data.config}}}
  catch(e){emit('error',(e as Error).message)}finally{busy.value=false}
}
async function download(){
  if(!run.value)return
  const id=run.value.id;exporting.value=true
  try{const r=await fetch(`/api/runs/${id}/exports/pdf`,{method:'POST'});if(!r.ok)throw new Error((await r.json()).detail||'Export fallito');const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=`${id}_report.pdf`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){emit('error',(e as Error).message)}finally{exporting.value=false}
}
function histogram(key:string){
  const d=analysis.value!.distributions[key],all=d.all.values
  const min=Math.min(...all),max=Math.max(...all),bins=Math.min(15,Math.max(1,Math.ceil(Math.sqrt(all.length)))),width=(max-min||1)/bins
  const count=(v:number[])=>{const counts=Array(bins).fill(0);for(const x of v)counts[Math.min(bins-1,Math.max(0,Math.floor((x-min)/width)))]++;return counts}
  return {tooltip:{trigger:'axis'},legend:{data:['Tutte','Ammesse']},grid:{left:55,right:20,bottom:55},xAxis:{type:'category',name:key,data:Array.from({length:bins},(_,i)=>fmt(min+(i+.5)*width))},yAxis:{type:'value',name:'Segmenti'},series:[{name:'Tutte',type:'bar',data:count(all),itemStyle:{color:'#bcc9ce'}},{name:'Ammesse',type:'bar',data:count(d.retained.values),itemStyle:{color:'#268575'}}]}
}
function qq(key:string){const d=analysis.value!.distributions[key].retained;return {tooltip:{trigger:'item'},grid:{left:65,right:25,bottom:55},xAxis:{type:'value',name:'Quantile normale',nameLocation:'middle',nameGap:28},yAxis:{type:'value',scale:true,name:key},series:[{type:'scatter',symbolSize:7,data:d.qq.theoretical.map((x,i)=>[x,d.qq.observed[i]])},{type:'line',symbol:'none',data:d.qq.theoretical.map(x=>[x,(d.mean||0)+(d.sd||0)*x])}]}}
function trajectory(r:PopulationPrediction,residual=false){const s=r.series;return {tooltip:{trigger:'axis'},legend:{top:0},grid:{left:65,right:25,bottom:60,top:40},xAxis:{type:'value',name:'Tempo (s)'},yAxis:{type:'value',scale:true,name:residual?'Residuo (bpm)':'HR (bpm)'},dataZoom:[{type:'inside'},{type:'slider',height:16,bottom:10}],series:residual?[{name:'Osservata − prevista',type:'line',showSymbol:false,data:s.time.map((t,i)=>[t,s.residual[i]])}]:[['Osservata',s.observed,'#536a80'],['Prevista',s.predicted,'#268575'],['Limite 2.5%',s.lower,'#9ccab8'],['Limite 97.5%',s.upper,'#9ccab8']].map(([name,values,color])=>({name,type:'line',showSymbol:false,lineStyle:{color,width:name==='Prevista'?2:1},data:(values as (number|null)[]).map((v,i)=>[s.time[i],v])}))}}
</script>

<template>
  <section class="card compact-card"><label>Esperimento<select :value="run?.id||''" :disabled="busy" @change="emit('select',($event.target as HTMLSelectElement).value)"><option v-for="r in runs" :key="r.id" :value="r.id">{{r.dataset.name}} · {{date(r.created_at)}} · {{r.id.slice(0,6)}}</option></select></label></section>
  <section v-if="!run" class="card empty"><h2>Nessun esperimento</h2><p>Identifica prima i segmenti train con B stimato.</p></section>
  <template v-else>
    <section class="card"><h2>Distribuzione dei parametri dello stesso atleta</h2><p>θⱼ = θ_sub + νⱼ, νⱼ ~ N(0, Ω). REML sui fit train, considerando la loro covarianza di stima. Previsione test dalla sola potenza, HR(0) = B e x(0) = 0.</p>
      <p v-if="!compatible" class="message warning">Serve una run P1D con inizializzazione «B stimato». HR del test non viene usata come alternativa.</p>
      <p class="note">Imposta le soglie usando il train. Cambiarle dopo aver osservato il test rende esplorativa la valutazione ripetuta. Le stime originali restano conservate.</p>
      <form class="population-controls" @submit.prevent="estimate">
        <label>RSE massimo (%)<input v-model.number="config.max_rse_pct" aria-label="RSE massimo" type="number" min="1" max="10000" required :disabled="busy"/></label>
        <label>|Correlazione locale| massima<input v-model.number="config.max_correlation" aria-label="Correlazione massima" type="number" min="0.5" max="1" step="0.01" required :disabled="busy"/></label>
        <label>Traiettorie campionate<input v-model.number="config.draws" type="number" min="50" max="1000" required :disabled="busy"/></label>
        <label>Seed<input v-model.number="config.seed" type="number" min="0" max="4294967295" required :disabled="busy"/></label>
        <label><input v-model="config.exclude_near_bounds" type="checkbox" :disabled="busy"/> Escludi anche stime vicine ai bounds</label>
        <button class="primary" type="submit" :disabled="!compatible||!completed||busy||loading">{{busy?'Stima e previsione in corso…':'Stima popolazione e prevedi test'}}</button>
      </form>
      <p v-if="changed" class="message warning">Configurazione modificata: i risultati e il PDF si riferiscono ancora all’analisi salvata.</p>
    </section>
    <p v-if="loading" role="status">Caricamento analisi…</p>
    <template v-if="analysis">
      <section class="card"><div class="section-heading"><div><h2>{{analysis.retained_vectors}} / {{analysis.train_count}} vettori train ammessi</h2><p>Analisi {{analysis.id.slice(0,8)}} · {{date(analysis.created_at)}} · {{analysis.status}}</p></div><button class="secondary" :disabled="exporting||busy" @click="download">{{exporting?'Esportazione…':'Report PDF completo'}}</button></div>
        <p v-if="analysis.reason" class="message warning">{{analysis.reason}}</p><p v-for="w in analysis.warnings" :key="w" class="note warning">{{w}}</p>
        <p>Minimo richiesto: {{analysis.minimum_vectors??'n.d.'}} vettori completi. Le statistiche marginali possono includere più stime del modello congiunto.</p>
      </section>
      <section v-for="p in analysis.parameters.filter(p=>analysis!.distributions[p.key])" :key="p.key" class="card"><h2>{{p.key}} <small>({{p.unit}})</small></h2>
        <div class="table-wrap"><table><thead><tr><th>Campione</th><th>n</th><th>Media</th><th>Mediana</th><th>SD</th></tr></thead><tbody><tr v-for="(d,k) in analysis.distributions[p.key]" :key="k"><td>{{k==='all'?'Tutte le stime':'Stime ammesse'}}</td><td>{{d.n}}</td><td>{{fmt(d.mean)}}</td><td>{{fmt(d.median)}}</td><td>{{fmt(d.sd)}}</td></tr></tbody></table></div>
        <div class="population-plots"><Chart v-if="analysis.distributions[p.key].all.n" :option="histogram(p.key)"/><Chart v-if="analysis.distributions[p.key].retained.n" :option="qq(p.key)"/></div>
        <p class="note">Q–Q: quantili osservati e riferimento normale con media e SD campionarie. Deviazioni dalla retta segnalano scostamenti dalla gaussianità.</p>
      </section>
      <section class="card"><h2>Identificabilità e registro delle esclusioni</h2><p>Bounds, rango, incertezza, correlazioni locali e stabilità multistart. Una correlazione tra parametri dell’atleta non equivale a una correlazione degli errori del singolo fit.</p><div class="table-wrap population-scroll"><table><thead><tr><th>Segmento</th><th>Vettore ammesso</th><th>Esclusioni per parametro</th></tr></thead><tbody><tr v-for="s in analysis.screening" :key="s.segment_id"><td>{{s.segment_id}}</td><td>{{s.included?'Sì':'No'}}</td><td><div v-for="(reasons,k) in s.parameters" :key="k"><span v-if="reasons.length">{{k}}: {{reasons.join(', ')}}</span></div><span v-if="s.included">Nessuna esclusione</span></td></tr></tbody></table></div></section>
      <section v-for="(entry,label) in analysis.fit_correlations" :key="label" class="card"><h2>Correlazioni tra parametri dei fit · {{label==='all'?'tutti':'ammessi'}}</h2><p>{{entry.n}} vettori completi. Correlazione descrittiva delle stime: comprende anche l’incertezza dei fit.</p><div v-if="entry.matrix" class="table-wrap"><table><thead><tr><th>Parametro</th><th v-for="p in analysis.parameters" :key="p.key">{{p.key}}</th></tr></thead><tbody><tr v-for="(row,i) in entry.matrix" :key="i"><th>{{analysis.parameters[i].key}}</th><td v-for="(v,j) in row" :key="j">{{fmt(v)}}</td></tr></tbody></table></div><p v-else>Servono almeno due vettori completi.</p></section>
      <template v-if="analysis.model">
        <section class="card"><h2>Modello dei parametri dell’atleta</h2><div class="table-wrap"><table><thead><tr><th>Parametro</th><th>Media</th><th>SD tra segmenti</th><th>CI95 della media</th></tr></thead><tbody><tr v-for="(k,i) in analysis.model.keys" :key="k"><td>{{k}}{{analysis.model.fixed[i]?' (fisso)':''}}</td><td>{{fmt(analysis.model.mean[i])}}</td><td>{{fmt(analysis.model.sd[i])}}</td><td>{{analysis.model.mean_ci95[i].map(fmt).join(' – ')}}</td></tr></tbody></table></div><p class="note">CI locali condizionati alle covarianze stimate; non includono l’incertezza di Ω.</p></section>
        <section v-for="matrix in (['covariance','correlation','observed_correlation'] as const)" :key="matrix" class="card"><h2>{{({covariance:'Ω · covarianza tra segmenti',correlation:'Correlazione degli effetti casuali',observed_correlation:'Correlazione osservata tra fit completi ammessi'})[matrix]}}</h2><div class="table-wrap"><table><thead><tr><th>Parametro</th><th v-for="k in analysis.model.keys" :key="k">{{k}}</th></tr></thead><tbody><tr v-for="(row,i) in analysis.model[matrix]" :key="i"><th>{{analysis.model.keys[i]}}</th><td v-for="(v,j) in row" :key="j">{{fmt(v)}}</td></tr></tbody></table></div></section>
        <section class="card"><h2>Previsione HR sul test</h2><p>Nessuna ristima sul test. HR iniziale = B_sub. Fascia 95% della variabilità dei parametri, condizionata ai bounds: non include rumore residuo o incertezza della media.</p>
          <p v-if="!analysis.test.length">Nessun segmento test disponibile.</p>
          <div v-else class="table-wrap"><table><thead><tr><th>Segmento</th><th>MAE bpm</th><th>RMSE bpm</th><th>Bias bpm</th><th>RMSE B costante</th></tr></thead><tbody><tr v-for="r in analysis.test" :key="r.segment_id"><td><button class="secondary" @click="testId=r.segment_id">{{r.filename}}</button></td><td>{{fmt(r.metrics?.MAE)}}</td><td>{{fmt(r.metrics?.RMSE)}}</td><td>{{fmt(r.metrics?.bias)}}</td><td>{{fmt(r.metrics?.constant_B_RMSE)}}</td></tr></tbody></table></div>
        </section>
        <section v-if="selectedTest" class="card"><h2>{{selectedTest.filename}}</h2><p v-if="selectedTest.status!=='predicted'" class="message warning">{{selectedTest.error}}</p><template v-else><p>P₀: {{fmt(selectedTest.P0)}} W · B iniziale: {{fmt(selectedTest.initial_HR)}} bpm · HR mancanti: {{selectedTest.missing_hr}} · Estrazioni nel dominio: {{fmt(100*selectedTest.gaussian_domain_acceptance)}}%</p><p v-if="!selectedTest.band_available" class="message warning">Campioni ammissibili insufficienti: fascia non disponibile.</p><Chart :option="trajectory(selectedTest)" :height="360"/><Chart :option="trajectory(selectedTest,true)" :height="240"/><p>SD residui: {{fmt(selectedTest.metrics?.residual_sd)}} bpm · Copertura empirica della fascia: {{fmt(selectedTest.metrics?.band_coverage==null?null:100*selectedTest.metrics.band_coverage)}}%</p></template></section>
      </template>
    </template>
  </template>
</template>

<style scoped>
.table-wrap{overflow:auto}.population-controls input[type=checkbox]{width:auto}
.population-controls{display:flex;flex-wrap:wrap;gap:18px;align-items:end;margin-top:20px}.population-controls label{flex:1 1 170px}.population-plots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:20px}.population-scroll{max-height:440px;overflow:auto}.population-scroll td{overflow-wrap:anywhere;max-width:440px}@media(max-width:1000px){.population-plots{grid-template-columns:1fr}}
</style>
