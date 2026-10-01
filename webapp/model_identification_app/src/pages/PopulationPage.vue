<script setup lang="ts">
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {api,date} from '../api'
import type {Run,Population,PopulationConfig,PopulationFitCorrelations} from '../types'
import Chart from '../components/Chart.vue'
import {metricColor,trajectory,type Review} from '../populationReview'
const props=defineProps<{runs:Run[];selected:string}>(),emit=defineEmits<{select:[id:string];error:[message:string]}>()
const run=computed(()=>props.runs.find(r=>r.id===props.selected)||props.runs.at(-1))
const analysis=ref<(Population & PopulationFitCorrelations)|null>(null),loading=ref(false),busy=ref(false),exporting=ref(false),testId=ref('')
const defaults=():PopulationConfig=>({prediction_mode:'observed_hr',max_rse_pct:100,max_correlation:.98,exclude_near_bounds:false,draws:200,seed:42})
const config=ref(defaults())
const compatible=computed(()=>run.value?.config.initialization_mode==='estimated_equilibrium'&&run.value?.config.model_structure==='p1d_full')
const completed=computed(()=>['completed','completed_with_errors'].includes(run.value?.status||''))
const selectedTest=computed(()=>analysis.value?.test.find(t=>t.segment_id===testId.value)||analysis.value?.test[0])
const changed=computed(()=>analysis.value&&JSON.stringify(config.value)!==JSON.stringify({...analysis.value.config,prediction_mode:analysis.value.config.prediction_mode||'legacy_power_only'}))
const fmt=(v:number|null|undefined)=>v==null?'n.d.':Number(v.toPrecision(5)).toLocaleString('it-IT')
let version=0
watch(()=>run.value?.id,async id=>{
  const ticket=++version;analysis.value=null;config.value=defaults();testId.value=''
  if(!id)return
  loading.value=true
  try{const data=await api<Population|null>(`/runs/${id}/population`);if(ticket===version){analysis.value=data;if(data)config.value={...data.config,prediction_mode:data.config.prediction_mode||'legacy_power_only'}}}
  catch(e){if(ticket===version)emit('error',(e as Error).message)}finally{if(ticket===version)loading.value=false}
},{immediate:true})
async function estimate(){
  if(!run.value)return
  const id=run.value.id,ticket=version;busy.value=true
  try{const data=await api<Population>(`/runs/${id}/population`,'POST',config.value);if(ticket===version){analysis.value=data;config.value={...data.config,prediction_mode:data.config.prediction_mode||'legacy_power_only'}}}
  catch(e){emit('error',(e as Error).message)}finally{busy.value=false}
}
const saving=ref(false),review=ref<Review>({verdict:'unreviewed',labels:[],notes:''}),savedReview=ref(''),saveMessage=ref('')
const reviewDirty=computed(()=>JSON.stringify(review.value)!==savedReview.value)
const reviewedCount=computed(()=>analysis.value?.test.filter(r=>analysis.value?.reviews?.[r.segment_id]?.verdict && analysis.value.reviews[r.segment_id].verdict!=='unreviewed').length||0)
const metricKeys=['MAE','RMSE','bias','constant_B_RMSE','residual_sd'] as const
const metricNames={MAE:'MAE',RMSE:'RMSE',bias:'Bias',constant_B_RMSE:'RMSE B costante',residual_sd:'SD residui'}
const draftKey=computed(()=>analysis.value&&selectedTest.value?`population-review:${run.value?.id}:${analysis.value.id}:${selectedTest.value.segment_id}`:'')
function preserveDraft(){
  if(!draftKey.value)return
  try{if(reviewDirty.value)sessionStorage.setItem(draftKey.value,JSON.stringify(review.value));else sessionStorage.removeItem(draftKey.value)}catch{ /* Backend saving remains available if browser storage is full. */ }
}
function resetReview(){
  const stored=analysis.value?.reviews?.[selectedTest.value?.segment_id||'']
  review.value={verdict:stored?.verdict||'unreviewed',labels:[...(stored?.labels||[])],notes:stored?.notes||''}
  savedReview.value=JSON.stringify(review.value);saveMessage.value=''
  preserveDraft()
}
watch([()=>analysis.value?.id,()=>selectedTest.value?.segment_id],()=>{
  let draft:string|null=null
  try{draft=draftKey.value?sessionStorage.getItem(draftKey.value):null}catch{}
  resetReview()
  if(draft){try{review.value=JSON.parse(draft);saveMessage.value='Bozza recuperata: da salvare nel backend'}catch{}}
},{immediate:true})
watch(review,preserveDraft,{deep:true})
watch(()=>review.value.verdict,value=>{if(value!=='negative')review.value.labels=[]})
function beforeUnload(e:BeforeUnloadEvent){if(reviewDirty.value){preserveDraft();e.preventDefault();e.returnValue=''}}
window.addEventListener('beforeunload',beforeUnload)
onBeforeUnmount(()=>{preserveDraft();window.removeEventListener('beforeunload',beforeUnload)})
function color(value:number|null|undefined,key:string){const c=analysis.value?.review_context;return c?metricColor(value,c.scales[key],c.colors):'#edf0f2'}
function verdict(id:string){const v=analysis.value?.reviews?.[id]?.verdict||'unreviewed';return analysis.value?.review_context?.verdicts[v]||'Non valutata'}
async function saveReview(){
  if(!run.value||!analysis.value||!selectedTest.value)return
  const id=run.value.id,a=analysis.value,sid=selectedTest.value.segment_id,ticket=version
  saving.value=true;saveMessage.value=''
  try{
    const stored=await api<Review>(`/runs/${id}/population/reviews/${encodeURIComponent(sid)}`,'PUT',{analysis_id:a.id,...review.value})
    if(ticket===version&&analysis.value?.id===a.id){a.reviews={...a.reviews,[sid]:stored};resetReview();saveMessage.value='Osservazione salvata'}
  }catch(e){emit('error',(e as Error).message)}finally{saving.value=false}
}
async function download(kind:'pdf'|'json'){
  if(!run.value||!analysis.value||reviewDirty.value)return
  const id=run.value.id,analysisId=analysis.value.id;exporting.value=true
  try{const r=await fetch(`/api/runs/${id}/population/exports/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({analysis_id:analysisId})});if(!r.ok)throw new Error((await r.json()).detail||'Export fallito');const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=`${analysisId}_population_review.${kind}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){emit('error',(e as Error).message)}finally{exporting.value=false}
}
function histogram(key:string){
  const d=analysis.value!.distributions[key],all=d.all.values
  const min=Math.min(...all),max=Math.max(...all),bins=Math.min(15,Math.max(1,Math.ceil(Math.sqrt(all.length)))),width=(max-min||1)/bins
  const count=(v:number[])=>{const counts=Array(bins).fill(0);for(const x of v)counts[Math.min(bins-1,Math.max(0,Math.floor((x-min)/width)))]++;return counts}
  return {tooltip:{trigger:'axis'},legend:{data:['Tutte','Ammesse']},grid:{left:55,right:20,bottom:55},xAxis:{type:'category',name:key,data:Array.from({length:bins},(_,i)=>fmt(min+(i+.5)*width))},yAxis:{type:'value',name:'Segmenti'},series:[{name:'Tutte',type:'bar',data:count(all),itemStyle:{color:'#bcc9ce'}},{name:'Ammesse',type:'bar',data:count(d.retained.values),itemStyle:{color:'#268575'}}]}
}
function qq(key:string){const d=analysis.value!.distributions[key].retained;return {tooltip:{trigger:'item'},grid:{left:65,right:25,bottom:55},xAxis:{type:'value',name:'Quantile normale',nameLocation:'middle',nameGap:28},yAxis:{type:'value',scale:true,name:key},series:[{type:'scatter',symbolSize:7,data:d.qq.theoretical.map((x,i)=>[x,d.qq.observed[i]])},{type:'line',symbol:'none',data:d.qq.theoretical.map(x=>[x,(d.mean||0)+(d.sd||0)*x])}]}}
</script>

<template>
  <section class="card compact-card"><label>Esperimento<select :value="run?.id||''" :disabled="busy||saving||reviewDirty" @change="emit('select',($event.target as HTMLSelectElement).value)"><option v-for="r in runs" :key="r.id" :value="r.id">{{r.dataset.name}} · {{date(r.created_at)}} · {{r.id.slice(0,6)}}</option></select></label></section>
  <section v-if="!run" class="card empty"><h2>Nessun esperimento</h2><p>Identifica prima i segmenti train con B stimato.</p></section>
  <template v-else>
    <section class="card"><h2>Distribuzione dei parametri dello stesso atleta</h2><p>θⱼ = θ_sub + νⱼ, νⱼ ~ N(0, Ω). REML sui fit train, considerando la loro covarianza di stima. Scegli prima della stima se mantenere B nella popolazione o calibrarlo sui primi 10 s del segmento.</p>
      <p v-if="!compatible" class="message warning">Serve una run P1D con inizializzazione «B stimato». HR del test non viene usata come alternativa.</p>
      <p class="note">Imposta le soglie usando il train. Cambiarle dopo aver osservato il test rende esplorativa la valutazione ripetuta. Le stime originali restano conservate.</p>
      <form class="population-controls" @submit.prevent="estimate">
        <label>Equilibrio e inizializzazione<select v-model="config.prediction_mode" aria-label="Protocollo predittivo" :disabled="busy||saving||reviewDirty"><option value="observed_hr">B di popolazione - HR(0) osservata</option><option value="local_B_10s">B locale - calibrazione di 10 s</option><option v-if="analysis &amp;&amp; (!analysis.config.prediction_mode || analysis.config.prediction_mode==='legacy_power_only')" value="legacy_power_only" disabled>Storico - sola potenza</option></select></label>
        <label>RSE massimo (%)<input v-model.number="config.max_rse_pct" aria-label="RSE massimo" type="number" min="1" max="10000" required :disabled="busy||saving||reviewDirty"/></label>
        <label>|Correlazione locale| massima<input v-model.number="config.max_correlation" aria-label="Correlazione massima" type="number" min="0.5" max="1" step="0.01" required :disabled="busy||saving||reviewDirty"/></label>
        <label>Traiettorie campionate<input v-model.number="config.draws" type="number" min="50" max="1000" required :disabled="busy||saving||reviewDirty"/></label>
        <label>Seed<input v-model.number="config.seed" type="number" min="0" max="4294967295" required :disabled="busy||saving||reviewDirty"/></label>
        <label><input v-model="config.exclude_near_bounds" type="checkbox" :disabled="busy||saving||reviewDirty"/> Escludi anche stime vicine ai bounds</label>
        <button class="primary" type="submit" :disabled="!compatible||!completed||busy||loading||saving||reviewDirty">{{busy?'Stima e previsione in corso…':'Stima popolazione e prevedi test'}}</button>
      </form>
      <p v-if="config.prediction_mode==='observed_hr'" class="note">K, L, tau e B di popolazione. x(0) = HR(0) - B_pop; nessuna ristima. Metriche da t >= 10 s per confronto con la calibrazione locale.</p>
      <p v-else-if="config.prediction_mode==='local_B_10s'" class="note">Solo K, L e tau di popolazione. B locale stimato con potenza e HR in [0, 10 s); x(0) = HR(0) - B_locale. Stato propagato senza reset, metriche da t >= 10 s. La finestra non assume equilibrio: B puo essere debolmente identificato.</p>
      <p v-if="changed" class="message warning">Configurazione modificata: i risultati e il PDF si riferiscono ancora all’analisi salvata.</p>
    </section>
    <p v-if="loading" role="status">Caricamento analisi…</p>
    <template v-if="analysis">
      <section class="card"><div class="section-heading"><div><h2>{{analysis.retained_vectors}} / {{analysis.train_count}} vettori train ammessi</h2><p>Analisi {{analysis.id.slice(0,8)}} · {{date(analysis.created_at)}} · {{analysis.status}}</p></div><div class="review-actions"><button v-for="kind in (['json','pdf'] as const)" :key="kind" class="secondary" :data-export="kind" :disabled="exporting||busy||saving||reviewDirty" @click="download(kind)">{{exporting?'Esportazione…':`Esporta analisi ${kind.toUpperCase()}`}}</button></div></div>
        <p v-for="warning in analysis.review_context?.warnings||[]" :key="warning" class="message warning">{{warning}}</p>
        <p v-if="reviewDirty" class="message warning">Osservazione non salvata: salva o annulla prima di cambiare selezione o esportare.</p>
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
        <section class="card"><h2>Previsione HR sul test</h2><p>Protocollo salvato: {{analysis.config.prediction_mode==='local_B_10s'?'B locale calibrato in [0, 10 s); metriche da 10 s':analysis.config.prediction_mode==='observed_hr'?'B di popolazione, HR(0) osservata; metriche da 10 s':'Storico: sola potenza, HR iniziale = B_pop'}}. Fascia 95% della variabilità dei parametri, condizionata ai bounds: non include rumore residuo, incertezza della media o errore della calibrazione HR/B. In modalita locale B viene ricalibrato per ogni traiettoria campionata.</p>
          <p v-if="!analysis.test.length">Nessun segmento test disponibile.</p>
          <template v-else>
            <p>{{reviewedCount}} / {{analysis.test.length}} predizioni valutate</p>
            <p class="note">{{analysis.review_context?.legend}}</p>
            <div class="color-legend"><span style="background:#c7ead2">Verde: migliore</span><span style="background:#f4b9b4">Rosso: peggiore</span><span style="background:#edf0f2">Grigio: n.d. / parità</span></div>
            <label>Attività / segmento test<select :value="selectedTest?.segment_id" aria-label="Attività test" :disabled="saving||reviewDirty" @change="testId=($event.target as HTMLSelectElement).value"><option v-for="r in analysis.test" :key="r.segment_id" :value="r.segment_id">{{r.activity_id||r.filename}} · {{r.filename}} · {{r.segment_id}} · {{verdict(r.segment_id)}}</option></select></label>
            <details class="test-overview"><summary>Riepilogo di tutte le predizioni</summary><div class="table-wrap"><table><thead><tr><th>Segmento</th><th>Valutazione</th><th v-for="k in metricKeys" :key="k">{{metricNames[k]}} bpm</th></tr></thead><tbody><tr v-for="r in analysis.test" :key="r.segment_id"><td><button class="secondary" :disabled="saving||reviewDirty" @click="testId=r.segment_id">{{r.filename}} · {{r.segment_id}}</button></td><td>{{verdict(r.segment_id)}}</td><td v-for="k in metricKeys" :key="k" :style="{backgroundColor:color(r.metrics?.[k],k)}">{{fmt(r.metrics?.[k])}}</td></tr></tbody></table></div></details>
          </template>
        </section>
        <section v-if="selectedTest" class="card">
          <details open :key="selectedTest.segment_id"><summary class="activity-title">{{selectedTest.filename}} · {{selectedTest.segment_id}}</summary>
          <p v-if="selectedTest.status!=='predicted'" class="message warning">{{selectedTest.error}}</p>
          <template v-else>
            <div class="metric-cards"><div v-for="k in metricKeys" :key="k" :style="{backgroundColor:color(selectedTest.metrics?.[k],k)}"><small>{{metricNames[k]}}</small><strong>{{fmt(selectedTest.metrics?.[k])}} bpm</strong></div></div>
            <p>P₀: {{fmt(selectedTest.P0)}} W · HR iniziale: {{fmt(selectedTest.initial_HR)}} bpm · HR mancanti: {{selectedTest.missing_hr}} · Estrazioni nel dominio: {{fmt(100*selectedTest.gaussian_domain_acceptance)}}%</p>
            <p v-if="selectedTest.equilibrium_B!=null">B: {{fmt(selectedTest.equilibrium_B)}} bpm · Valutazione da {{selectedTest.evaluation_start_s}} s. Il tratto precedente serve a inizializzazione/calibrazione.</p>
            <template v-if="selectedTest.calibration"><p>Calibrazione: {{selectedTest.calibration.samples}} campioni · SE condizionale B: {{fmt(selectedTest.calibration.B_se_conditional)}} bpm (approssimazione locale, condizionata a HR(0), K, L e tau).</p><p v-for="w in selectedTest.calibration.warnings" :key="w" class="message warning">{{w}}</p></template>
            <p v-if="!selectedTest.band_available" class="message warning">Campioni ammissibili insufficienti: fascia non disponibile.</p>
            <Chart :option="trajectory(selectedTest)" :height="490"/><Chart :option="trajectory(selectedTest,true)" :height="260"/>
            <p>Copertura empirica della fascia: {{fmt(selectedTest.metrics?.band_coverage==null?null:100*selectedTest.metrics.band_coverage)}}%</p>
            <fieldset :disabled="saving||busy"><legend>Osservazione della predizione</legend>
              <label>Valutazione<select v-model="review.verdict" aria-label="Valutazione predizione"><option value="unreviewed">Non valutata</option><option value="positive">Positiva</option><option value="negative">Negativa</option></select></label>
              <div v-if="review.verdict==='negative'" class="review-labels"><label v-for="(label,key) in analysis.review_context?.labels||{}" :key="key"><input v-model="review.labels" type="checkbox" :value="key"/>{{label}}</label></div>
              <label>Note descrittive<textarea v-model="review.notes" aria-label="Note osservazione" maxlength="10000" rows="3" placeholder="Descrivi cosa osservi nelle tracce"/></label>
              <div class="review-actions"><button class="primary" data-save-review :disabled="!reviewDirty" @click="saveReview">{{saving?'Salvataggio…':'Salva osservazione'}}</button><button class="secondary" :disabled="!reviewDirty" @click="resetReview">Annulla modifiche</button><span role="status">{{reviewDirty?'Modifiche non salvate':saveMessage}}</span></div>
            </fieldset>
          </template></details>
        </section>
      </template>
    </template>
  </template>
</template>

<style scoped>
.table-wrap{overflow:auto}.population-controls input[type=checkbox]{width:auto}
.population-controls{display:flex;flex-wrap:wrap;gap:18px;align-items:end;margin-top:20px}.population-controls label{flex:1 1 170px}.population-plots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:20px}.population-scroll{max-height:440px;overflow:auto}.population-scroll td{overflow-wrap:anywhere;max-width:440px}@media(max-width:1000px){.population-plots{grid-template-columns:1fr}}
.review-actions,.color-legend{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.color-legend{margin:16px 0}.color-legend span{padding:8px 12px;border-radius:6px}.metric-cards{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}.metric-cards>div{padding:12px 18px;border-radius:8px;min-width:135px}.metric-cards small,.metric-cards strong{display:block}.metric-cards strong{margin-top:5px}.activity-title{font-size:20px;font-weight:600;cursor:pointer}.test-overview{margin-top:18px}.test-overview summary{cursor:pointer;padding:10px 0}fieldset{border:1px solid #c9d5d0;border-radius:8px;padding:18px}textarea{display:block;width:100%;box-sizing:border-box;margin:8px 0 16px}.review-labels{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}.review-labels label{display:flex;align-items:center;gap:7px}.review-labels input{width:auto}
</style>
