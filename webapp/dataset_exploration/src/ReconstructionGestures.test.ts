import {mount,flushPromises} from '@vue/test-utils'
import {expect,it,vi} from 'vitest'
import ReconstructionChart from './components/ReconstructionChart.vue'
import {insertBlock,deleteBlocks,viewport,applyRepeat} from './reconstruction'

it('inserts an interval preserving outer portions and refuses locked overlaps',()=>{
  const original=[{start:0,end:30,power:200},{start:30,end:60,power:100}]
  expect(insertBlock(original,{start:10,end:40,power:300},[],60)).toEqual([
    {start:0,end:10,power:200},{start:10,end:40,power:300},{start:40,end:60,power:100}])
  expect(original[0].end).toBe(30)
  expect(()=>insertBlock(original,{start:10,end:40,power:300},[{start:0,end:60,on:30,off:30}],60)).toThrow(/vincolo/)
  expect(deleteBlocks(original,[0],[])).toEqual([original[1]])
  expect(()=>deleteBlocks(original,[0],[{start:0,end:60,on:30,off:30}])).toThrow(/vincolo/)
})

it('clamps panning at both ends while preserving the zoom width',()=>{
  expect(viewport(-10,20,100)).toEqual({start:0,end:30})
  expect(viewport(90,120,100)).toEqual({start:70,end:100})
  expect(viewport(10,200,100)).toEqual({start:0,end:100})
})

it('does not apply ON/OFF across a recording gap inside a lap',()=>{
  expect(()=>applyRepeat([{start:0,end:30,power:300},{start:30,end:60,power:100}],
    [0,1],30,15,60,[],[{start:10,end:20}])).toThrow(/gap/)
})

async function send(svg:any,type:string,options:any){
  svg.element.dispatchEvent(type==='wheel'?new WheelEvent(type,{bubbles:true,cancelable:true,...options}):new MouseEvent(type,{bubbles:true,...options}));await flushPromises()
}
function chart(mode='edit'){
  const w=mount(ReconstructionChart,{props:{points:[],blocks:[],start:20,end:60,duration:100,mode:mode as any}})
  vi.spyOn(w.get('svg').element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:1000,height:350} as DOMRect)
  return w
}

it('scrolls horizontally with wheel and zooms around pointer with ctrl wheel',async()=>{
  const w=chart(),svg=w.get('svg')
  await send(svg,'wheel',{deltaY:100,clientX:515,clientY:100})
  const pan=w.emitted('viewport')![0][0] as any
  expect(pan.start).toBeGreaterThan(20);expect(pan.end-pan.start).toBe(40)
  await send(svg,'wheel',{deltaY:-100,ctrlKey:true,clientX:515,clientY:100})
  const zoom=w.emitted('viewport')![1][0] as any
  expect(zoom.end-zoom.start).toBeLessThan(40)
  expect((zoom.start+zoom.end)/2).toBeCloseTo(40)
})

it('draws new intervals with the pointer and cuts with a single click',async()=>{
  const w=chart('add'),svg=w.get('svg')
  await send(svg,'pointerdown',{clientX:285,clientY:167.5})
  await send(svg,'pointermove',{clientX:745,clientY:167.5})
  await send(svg,'pointerup',{clientX:745,clientY:167.5})
  await flushPromises()
  expect(w.emitted('insert')![0][0]).toEqual({start:30,end:50,power:75})
  await w.setProps({mode:'cut'})
  await send(svg,'pointerdown',{clientX:515,clientY:150})
  await send(svg,'pointerup',{clientX:515,clientY:150})
  expect(w.emitted('cursor')![0][0]).toBe(40)
})

it('pans by dragging the background without editing blocks',async()=>{
  const w=chart(),svg=w.get('svg')
  await send(svg,'pointerdown',{clientX:515,clientY:100})
  await send(svg,'pointermove',{clientX:285,clientY:100})
  await send(svg,'pointerup',{clientX:285,clientY:100})
  expect(w.emitted('viewport')![0][0]).toEqual({start:30,end:70})
  expect(w.emitted('change')).toBeUndefined()
})

it('selects a clicked handle and consumes the SVG click after pointer capture before the next selection',async()=>{
  const w=mount(ReconstructionChart,{props:{points:[],blocks:[{start:0,end:30,power:200}],start:0,end:30}})
  const svg=w.get('svg'),handle=w.get('[data-power-handle="0"]')
  vi.spyOn(svg.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:1000,height:350} as DOMRect)
  await send(handle,'pointerdown',{clientX:300,clientY:85})
  await send(svg,'pointerup',{clientX:300,clientY:85,shiftKey:true})
  // Browser pointer capture retargets this click to the SVG.
  await svg.trigger('click')
  expect(w.emitted('select')![0]).toEqual([0,true])
  await send(handle,'pointerdown',{clientX:300,clientY:85})
  await send(svg,'pointermove',{clientX:300,clientY:140})
  await send(svg,'pointerup',{clientX:300,clientY:140})
  await svg.trigger('click')
  await w.get('[data-block="0"] rect').trigger('click')
  expect(w.emitted('select')).toHaveLength(2)
})

it('selects a run by dragging a selection rectangle',async()=>{
  const w=chart('box'),svg=w.get('svg')
  await w.setProps({blocks:[{start:20,end:30,power:300},{start:30,end:40,power:100},{start:40,end:60,power:300}]})
  await send(svg,'pointerdown',{clientX:56,clientY:50})
  await send(svg,'pointermove',{clientX:514,clientY:280})
  await send(svg,'pointerup',{clientX:514,clientY:280})
  expect(w.emitted('selection')![0][0]).toEqual([0,1])
})

it('drags the body of a block and adjusts both neighbours without gaps',async()=>{
  const w=mount(ReconstructionChart,{props:{points:[],blocks:[{start:0,end:20,power:200},{start:20,end:40,power:100},{start:40,end:60,power:200}],start:0,end:60,duration:60}})
  const svg=w.get('svg')
  vi.spyOn(svg.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:1000,height:350} as DOMRect)
  await send(w.get('[data-block="1"] rect'),'pointerdown',{clientX:515,clientY:250})
  await send(svg,'pointermove',{clientX:607,clientY:250})
  await send(svg,'pointerup',{clientX:607,clientY:250})
  expect(w.emitted('change')![0][0]).toEqual([{start:0,end:26,power:200},{start:26,end:46,power:100},{start:46,end:60,power:200}])
})
