<script setup lang="ts">
import {computed,ref,useId} from 'vue'
import type {ProcessPoint} from '../processingApi'
import {copy,moveBoundary,moveBlock,viewport,type Block,type Repeat} from '../reconstruction'
const props=withDefaults(defineProps<{points:ProcessPoint[];blocks:Block[];constraints?:Repeat[];selected?:number[];start:number;end:number;duration?:number;readonly?:boolean;cuts?:number[];mode?:'edit'|'add'|'cut'|'split'|'box'}>(),{constraints:()=>[],selected:()=>[],cuts:()=>[],mode:'edit'})
const emit=defineEmits<{change:[Block[]];select:[number,boolean];selection:[number[]];cursor:[number];error:[string];insert:[Block];viewport:[{start:number;end:number}]}>()
const svg=ref<SVGSVGElement|null>(null),draft=ref<Block[]|null>(null)
const clipId=useId()
const drag=ref<{i:number;edge:'start'|'end'|'power'|'body';base:Block[];max:number;moved:boolean;time:number;x:number;y:number}|null>(null)
const gesture=ref<{x:number;time:number;power:number;start:number;end:number;mode:string;moved:boolean}|null>(null)
const added=ref<Block|null>(null),hint=ref('')
const box=ref<{start:number;end:number}|null>(null)
let suppressClick=false
const shown=computed(()=>draft.value??props.blocks)
const scale=computed(()=>{let max=100;for(const p of props.points)if(p.elapsed_seconds>=props.start&&p.elapsed_seconds<=props.end)max=Math.max(max,p.power_w??0);for(const b of shown.value)max=Math.max(max,b.power);return Math.ceil(max*1.2/50)*50})
const ymax=computed(()=>drag.value?.max??scale.value)
const x=(t:number)=>55+(t-props.start)/Math.max(.1,props.end-props.start)*920
const y=(p:number)=>305-p/ymax.value*275
const visible=computed(()=>shown.value.map((b,i)=>({b,i})).filter(({b})=>b.end>props.start&&b.start<props.end))
const step=computed(()=>{
  const diffs=props.points.slice(1).map((p,i)=>p.elapsed_seconds-props.points[i].elapsed_seconds).sort((a,b)=>a-b)
  return diffs[Math.floor(diffs.length/2)]??1
})
function path(column:'power_w'|'power_ma_w') {
  let d='',previous:number|null=null
  for(const p of props.points){if(p.elapsed_seconds<props.start||p.elapsed_seconds>props.end)continue;const v=p[column];if(v===null||!Number.isFinite(v)){previous=null;continue}d+=`${previous===null||p.elapsed_seconds-previous>1.5*step.value?'M':'L'}${x(p.elapsed_seconds).toFixed(2)},${y(v).toFixed(2)} `;previous=p.elapsed_seconds}
  return d
}
const rawPath=computed(()=>path('power_w')),meanPath=computed(()=>path('power_ma_w'))
function coords(e:PointerEvent) {const r=svg.value!.getBoundingClientRect();return {time:props.start+((e.clientX-r.left)/r.width*1000-55)/920*(props.end-props.start),power:(305-(e.clientY-r.top)/r.height*350)/275*ymax.value}}
function begin(e:PointerEvent,i:number,edge:'start'|'end'|'power'|'body') {
  if(props.readonly||props.mode!=='edit'||e.button>0)return
  hint.value='';suppressClick=false
  e.preventDefault();e.stopPropagation();drag.value={i,edge,base:copy(props.blocks),max:scale.value,moved:false,time:coords(e).time,x:e.clientX,y:e.clientY};draft.value=copy(props.blocks)
  svg.value!.setPointerCapture?.(e.pointerId)
}
function move(e:PointerEvent) {
  if(gesture.value){
    const g=gesture.value,at=coords(e);g.moved ||= Math.abs(e.clientX-g.x)>3
    if(g.mode==='add'){
      const t=Math.max(0,Math.min(props.duration??props.end,Math.round(at.time*10)/10))
      added.value={start:Math.min(g.time,t),end:Math.max(g.time,t),power:g.power}
    }else if(g.mode==='box'){
      const t=Math.max(props.start,Math.min(props.end,at.time));box.value={start:Math.min(g.time,t),end:Math.max(g.time,t)}
    }else if(g.mode==='edit'){
      const delta=(g.x-e.clientX)/svg.value!.getBoundingClientRect().width*1000/920*(g.end-g.start)
      emit('viewport',viewport(g.start+delta,g.end+delta,props.duration??props.end))
    }
    return
  }
  if(!drag.value)return
  const at=coords(e);drag.value.moved ||= Math.hypot(e.clientX-drag.value.x,e.clientY-drag.value.y)>3
  if(!drag.value.moved)return
  try {
    if(drag.value.edge==='power'){const next=copy(drag.value.base);next[drag.value.i].power=Math.max(0,Math.round(at.power));draft.value=next}
    else if(drag.value.edge==='body')draft.value=moveBlock(drag.value.base,drag.value.i,Math.round((at.time-drag.value.time)*10)/10,props.duration??props.end,props.cuts)
    else {const t=Math.round(at.time*10)/10;if(t<0||t>(props.duration??props.end))return;draft.value=moveBoundary(drag.value.base,drag.value.i,drag.value.edge,t,[],props.cuts,props.duration??props.end)}
    hint.value=''
  }catch(e){hint.value=(e as Error).message}
}
function finish(e:PointerEvent) {
  if(drag.value){
    const next=draft.value;suppressClick=true
    if(drag.value.moved&&next)emit('change',next)
    else emit('select',drag.value.i,e.shiftKey)
    drag.value=null;draft.value=null
  }
  if(gesture.value){
    const g=gesture.value;suppressClick=g.moved||g.mode!=='edit'
    if(g.mode==='add'&&g.moved&&added.value&&added.value.end>added.value.start)emit('insert',added.value)
    if(g.mode==='box'&&g.moved&&box.value)emit('selection',props.blocks.map((b,i)=>({b,i})).filter(({b})=>b.start<box.value!.end&&b.end>box.value!.start).map(({i})=>i))
    if((g.mode==='cut'||g.mode==='split')&&!g.moved)emit('cursor',g.time)
    gesture.value=null;added.value=null;box.value=null
  }
  svg.value?.releasePointerCapture?.(e.pointerId)
}
function cancel(){drag.value=null;draft.value=null;gesture.value=null;added.value=null;box.value=null;hint.value=''}
function background(e:PointerEvent){
  if(props.readonly||e.button>0)return
  suppressClick=false
  if(props.mode==='edit'&&(e.target as Element).closest('[data-block]'))return
  e.preventDefault();suppressClick=false;hint.value=''
  const at=coords(e),time=Math.max(props.start,Math.min(props.end,Math.round(at.time*10)/10))
  gesture.value={x:e.clientX,time,power:Math.max(0,Math.round(at.power)),start:props.start,end:props.end,mode:props.mode,moved:false}
  if(props.mode==='add')added.value={start:time,end:time,power:gesture.value.power}
  if(props.mode==='box')box.value={start:time,end:time}
  svg.value?.setPointerCapture?.(e.pointerId)
}
function wheel(e:WheelEvent){
  if(props.readonly||drag.value||gesture.value)return
  e.preventDefault()
  const width=props.end-props.start,delta=(e.deltaY||e.deltaX)*(e.deltaMode===1?16:e.deltaMode===2?350:1)
  if(e.ctrlKey||e.metaKey){
    const anchor=Math.max(props.start,Math.min(props.end,coords(e as unknown as PointerEvent).time))
    const nextWidth=Math.min(props.duration??props.end,Math.max(Math.min(1,props.duration??props.end),width*Math.exp(Math.max(-1,Math.min(1,delta*.002)))))
    const start=anchor-(anchor-props.start)/width*nextWidth
    emit('viewport',viewport(start,start+nextWidth,props.duration??props.end))
  }else emit('viewport',viewport(props.start+delta*width/1000,props.end+delta*width/1000,props.duration??props.end))
}
function consumeClick(e:MouseEvent){if(suppressClick){suppressClick=false;e.stopPropagation()}}
function choose(i:number,e:MouseEvent){if(props.readonly||props.mode!=='edit')return;emit('select',i,e.shiftKey)}
const editing=computed(()=>drag.value&&draft.value?draft.value[drag.value.i]:added.value)
function locate(e:MouseEvent){if(!props.readonly)emit('cursor',Math.max(props.start,Math.min(props.end,Math.round(coords(e as PointerEvent).time*10)/10)))}
</script>
<template>
  <div class="reconstruction-plot">
    <svg ref="svg" viewBox="0 0 1000 350" preserveAspectRatio="none" role="img" aria-label="Potenza misurata, media mobile e intervalli ricostruiti" :class="{drawing:mode!=='edit'}" @click.capture="consumeClick" @wheel="wheel" @pointerdown="background" @pointermove="move" @pointerup="finish" @pointercancel="cancel" @dblclick="locate">
      <defs><clipPath :id="clipId"><rect x="55" y="20" width="920" height="285"/></clipPath></defs>
      <g v-for="fraction in [0,.25,.5,.75,1]" :key="fraction"><line x1="55" x2="975" :y1="y(fraction*ymax)" :y2="y(fraction*ymax)" stroke="#e2e8f0"/><text x="48" :y="y(fraction*ymax)+4" text-anchor="end">{{Math.round(fraction*ymax)}} W</text></g>
      <g :clip-path="`url(#${clipId})`">
        <path :d="rawPath" fill="none" stroke="#94a3b8" stroke-width="1.2"/>
        <path :d="meanPath" fill="none" stroke="#2563eb" stroke-width="1.8"/>
        <g v-for="{b,i} in visible" :key="i" :data-block="i">
          <rect :x="x(b.start)" :y="y(b.power)" :width="Math.max(1,x(b.end)-x(b.start))" :height="Math.max(1,305-y(b.power))" :fill="selected.includes(i)?'#f59e0b':'#10b981'" fill-opacity=".16" @pointerdown="begin($event,i,'body')" @click="choose(i,$event)"/>
          <line :x1="x(b.start)" :x2="x(b.end)" :y1="y(b.power)" :y2="y(b.power)" stroke="#047857" stroke-width="3"/>
          <line v-if="!readonly&&mode==='edit'" :x1="x(b.start)" :x2="x(b.end)" :y1="y(b.power)" :y2="y(b.power)" stroke="transparent" stroke-width="14" class="height-handle" :data-power-handle="i" @pointerdown="begin($event,i,'power')" @click="choose(i,$event)"><title>Trascina per modificare i watt</title></line>
          <line v-for="edge in (['start','end'] as const)" :key="edge" :x1="x(b[edge])" :x2="x(b[edge])" :y1="y(b.power)" y2="305" stroke="#059669" :stroke-width="readonly?1:5" stroke-opacity=".6" :class="{'time-handle':!readonly&&mode==='edit'}" @pointerdown="begin($event,i,edge)"><title>Confine temporale · {{b[edge]}} s</title></line>
          <text v-if="x(b.end)-x(b.start)>55" :x="(x(b.start)+x(b.end))/2" :y="Math.max(18,y(b.power)-10)" text-anchor="middle">{{b.power}} W</text>
        </g>
        <line v-for="cut in cuts" :key="cut" :x1="x(cut)" :x2="x(cut)" y1="20" y2="305" stroke="#dc2626" stroke-width="2" stroke-dasharray="5 4"/>
        <rect v-if="added" :x="x(added.start)" :y="y(added.power)" :width="Math.max(1,x(added.end)-x(added.start))" :height="Math.max(1,305-y(added.power))" fill="#f59e0b" fill-opacity=".3" stroke="#d97706" pointer-events="none"/>
        <rect v-if="box" :x="x(box.start)" y="20" :width="Math.max(1,x(box.end)-x(box.start))" height="285" fill="#2563eb" fill-opacity=".15" stroke="#2563eb" stroke-dasharray="4 3" pointer-events="none"/>
      </g>
      <g v-if="editing" pointer-events="none"><rect x="380" y="2" width="300" height="24" rx="5" fill="#0f172a"/><text x="530" y="18" text-anchor="middle" style="fill:white">{{editing.power}} W · {{(editing.end-editing.start).toFixed(1)}} s · {{editing.start.toFixed(1)}}–{{editing.end.toFixed(1)}} s</text></g>
      <text v-for="f in [0,.25,.5,.75,1]" :key="f" :x="55+920*f" y="330" text-anchor="middle">{{Math.round(start+(end-start)*f)}} s</text>
    </svg>
    <p v-if="hint" role="status">{{hint}}</p>
    <p class="legend"><span>━ Misurata</span><span class="mean">━ Media 5 s</span><span class="target">━ Obiettivo ricostruito</span><span v-if="!readonly">Rotellina: scorri · Ctrl + rotellina: zoom · Trascina lo sfondo: sposta · Maiusc + clic: seleziona sequenza</span></p>
  </div>
</template>
<style scoped>
svg{width:100%;height:350px;touch-action:none;user-select:none;background:white;border-radius:8px;cursor:grab}svg.drawing{cursor:crosshair}text{font-size:11px;fill:#475569;pointer-events:none}.height-handle{cursor:ns-resize}.time-handle{cursor:ew-resize}.legend{display:flex;gap:1rem;flex-wrap:wrap;font-size:.8rem;color:#64748b}.mean{color:#2563eb}.target{color:#047857}
</style>
