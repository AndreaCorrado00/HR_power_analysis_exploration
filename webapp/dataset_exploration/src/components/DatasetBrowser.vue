<script setup lang="ts">
import {computed,onMounted, ref} from 'vue'
import {notify} from '../notifications'
const emit=defineEmits<{close:[]; choose:[selection:{path:string;folder:string;selectedFiles:string[]|null}]}>()
const props=defineProps<{initialPath:string}>()
interface Entry{name:string;path:string;kind:string}
interface Listing{path:string;folder:string;isZip:boolean;parent:string;entries:Entry[]}
const listing=ref<Listing|null>(null),location=ref(props.initialPath),chosen=ref<string[]>([]),busy=ref(false)
const fitFiles=computed(()=>listing.value?.entries.filter(e=>e.kind==='fit').map(e=>listing.value!.isZip?e.path:e.name)??[])
const allSelected=computed(()=>fitFiles.value.length>0&&chosen.value.length===fitFiles.value.length)
function toggleAll(event:Event){chosen.value=(event.target as HTMLInputElement).checked?[...fitFiles.value]:[]}
async function navigate(path:string,folder=''){
  busy.value=true
  try{
    const r=await fetch('/api/datasets/browse?'+new URLSearchParams({path,folder}));const data=await r.json()
    if(!r.ok)throw new Error(data.detail)
    listing.value=data;location.value=data.path;chosen.value=[]
  }catch(e){notify((e as Error).message,'error')}finally{busy.value=false}
}
function enter(entry:Entry){const s=listing.value!;navigate(s.isZip?s.path:entry.path,s.isZip?entry.path:'')}
function up(){const s=listing.value!;if(s.isZip&&s.folder)navigate(s.path,s.folder.split('/').slice(0,-1).join('/'));else navigate(s.parent)}
function choose(all:boolean){const s=listing.value!;emit('choose',{path:s.path,folder:s.folder,selectedFiles:all?null:chosen.value})}
onMounted(()=>navigate(props.initialPath))
</script>
<template>
  <div class="overlay" @click.self="emit('close')"><section class="detail" role="dialog" aria-modal="true" aria-label="Esplora dataset">
    <button class="close" @click="emit('close')">Chiudi</button><h2>Esplora dataset</h2>
    <form class="actions" @submit.prevent="navigate(location)"><label>Percorso cartella o ZIP <input v-model="location" aria-label="Percorso cartella o ZIP" style="width: min(650px,65vw)"></label><button :disabled="busy">Apri</button></form>
    <p v-if="busy">Caricamento...</p>
    <template v-if="listing"><p>{{listing.path}}{{listing.isZip?' / '+listing.folder:''}}</p><button @click="up" :disabled="busy">Cartella superiore</button>
      <p><label><input type="checkbox" aria-label="Seleziona tutti i FIT" :checked="allSelected" :indeterminate="chosen.length>0&&!allSelected" :disabled="busy||!fitFiles.length" @change="toggleAll"> Seleziona tutti i FIT nella cartella ({{fitFiles.length}})</label></p>
      <div style="display:grid;gap:.6rem;margin:1rem 0;max-height:50vh;overflow:auto">
        <div v-for="entry in listing.entries" :key="entry.path">
          <label v-if="entry.kind==='fit'"><input type="checkbox" v-model="chosen" :disabled="busy" :aria-label="entry.name" :value="listing.isZip?entry.path:entry.name"> {{entry.name}}</label>
          <button v-else class="secondary" @click="enter(entry)" :disabled="busy">{{entry.kind==='zip'?'ZIP':'Cartella'}}: {{entry.name}}</button>
        </div>
      </div>
      <p v-if="!listing.entries.length">Nessun FIT, ZIP o sottocartella.</p>
      <div class="actions"><button :disabled="busy||!chosen.length" @click="choose(false)">Importa selezionati ({{chosen.length}})</button><button :disabled="busy" @click="choose(true)">Importa cartella e sottocartelle</button></div>
    </template>
  </section></div>
</template>
