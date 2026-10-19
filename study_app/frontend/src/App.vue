<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {api} from './api'
import AthletesPage from './pages/AthletesPage.vue'
import HistoryPage from './pages/HistoryPage.vue'
import ExperimentsPage from './pages/ExperimentsPage.vue'
import ModelsPage from './pages/ModelsPage.vue'
import PlannerPage from './pages/PlannerPage.vue'
import EvaluationPage from './pages/EvaluationPage.vue'
import CompareAthletesPage from './pages/CompareAthletesPage.vue'
const athletes=ref<any[]>([]),athlete=ref<any>(null),page=ref('atleti'),error=ref('')
const nav=[['storico','01','Storico attività'],['esperimenti','02','Identificazione'],['modelli','03','Modelli'],['allenamenti','04','Prepara allenamento'],['verifiche','05','Verifiche nel tempo']]
async function refresh(){try{athletes.value=await api('/athletes');if(athlete.value)athlete.value=athletes.value.find(a=>a.id===athlete.value.id)}catch(e:any){error.value=e.message}}
function select(a:any){athlete.value=a;page.value='storico'}
onMounted(refresh)
</script>
<template><div class="shell"><aside><a class="brand" href="#" @click.prevent="page='atleti'"><span class="brand-mark">↗</span><span>STUDIO<small>HR / POWER</small></span></a><div class="local"><i></i> Workspace locale</div><button class="nav-item" :class="{active:page==='atleti'}" @click="page='atleti'">Atleti <span>{{athletes.length}}</span></button><template v-if="athlete"><div class="athlete-switch"><small>ATLETA SELEZIONATO</small><select :value="athlete.id" @change="select(athletes.find(a=>a.id===($event.target as HTMLSelectElement).value))"><option v-for="a in athletes" :value="a.id">{{a.first_name}} {{a.last_name}}</option></select></div><button v-for="[key,num,label] in nav" class="nav-item" :class="{active:page===key}" @click="page=key"><small>{{num}}</small>{{label}}</button></template><button class="nav-item compare-nav" :class="{active:page==='confronto'}" @click="page='confronto'">⇄ Confronta atleti</button><footer>Uno studio, una traccia verificabile.<br>Modelli congelati · aggiornamenti espliciti</footer></aside><main><header class="topbar"><span>Ricerca applicata / Ciclismo</span><span class="pill">Solo locale</span></header><div class="error" v-if="error" role="alert">{{error}}</div><AthletesPage v-if="page==='atleti'" :athletes="athletes" @refresh="refresh" @select="select"/><CompareAthletesPage v-else-if="page==='confronto'" :athletes="athletes"/><template v-else-if="athlete"><HistoryPage v-if="page==='storico'" :key="athlete.id+'h'" :athlete="athlete" @refresh="refresh"/><ExperimentsPage v-if="page==='esperimenti'" :key="athlete.id+'e'" :athlete="athlete"/><ModelsPage v-if="page==='modelli'" :key="athlete.id+'m'" :athlete="athlete"/><PlannerPage v-if="page==='allenamenti'" :key="athlete.id+'p'" :athlete="athlete"/><EvaluationPage v-if="page==='verifiche'" :key="athlete.id+'v'" :athlete="athlete"/></template></main></div></template>
