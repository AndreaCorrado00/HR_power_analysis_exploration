import {mount,flushPromises} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import App from './App.vue'
import ReconstructionPage from './components/ReconstructionPage.vue'
import ReconstructionChart from './components/ReconstructionChart.vue'

vi.mock('vue-echarts',()=>({default:{template:'<div />'}}))
afterEach(()=>vi.unstubAllGlobals())
const summary={id:'loaded_0001.csv',activityId:'ride.fit',firstLap:1,lastLap:1,durationSeconds:30,sampleCount:31,gapCount:0,medianStepSeconds:1,missing:{power_w:0,heart_rate_bpm:0}}
const imported={datasetId:'snapshot',segments:[summary]}
const proposal={points:[{elapsed_seconds:0,power_w:200,power_ma_w:200,heart_rate_bpm:130},{elapsed_seconds:30,power_w:210,power_ma_w:210,heart_rate_bpm:140}],blocks:[{start:0,end:31,power:205}],end:31,step:1,gapCount:0,missingPower:0,sensitivity:50,saved:null}

it('transfers the selected lap into processing without creating or uploading a file',async()=>{
  let transfer:any
  vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>({ok:true,json:async()=>{
    if(url==='/api/datasets/load')return {datasetId:'fits',datasetPath:'dataset',excluded:[],extractable:[{activityId:'ride.fit',recordCount:31,durationSeconds:30,extractable:true,laps:[{index:1,startElapsedSeconds:0,endElapsedSeconds:30,durationSeconds:30}]}]}
    if(url.endsWith('/series'))return {points:[{elapsedSeconds:0,power:200,heartRate:130}]}
    if(url==='/api/processing/from-loaded'){transfer=JSON.parse(init.body as string);return imported}
    return {segments:[{id:summary.id,points:proposal.points}]}
  }})))
  const w=mount(App),button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  await button('Carica dataset').trigger('click');await flushPromises()
  await w.get('.card').trigger('click');await flushPromises()
  await button('Lap 1').trigger('click')
  expect(button('Elabora selezionati')).toBeDefined()
  await button('Elabora selezionati').trigger('click');await flushPromises()
  expect(transfer).toEqual({datasetId:'fits',segments:[{activityId:'ride.fit',firstLap:1,lastLap:1}]})
  expect(w.get('.processing-page').isVisible()).toBe(true)
  expect(w.get('.processing-page').text()).toContain('1 / 1 selezionati')
  await button('Elabora e aggiorna anteprima').trigger('click');await flushPromises()
  expect(button('Esporta ZIP').attributes('disabled')).toBeUndefined()
  w.unmount()
})

it('opens another loaded whole activity and restores the previous draft from session history',async()=>{
  const requests:any[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{
    if(url.endsWith('/from-loaded'))requests.push(JSON.parse(init.body as string))
    return {ok:true,json:async()=>url.endsWith('/from-loaded')?{...imported,datasetId:`snapshot${requests.length}`} :proposal}
  }))
  const w=mount(ReconstructionPage,{props:{loadedDatasetId:'fits',loadedActivities:[{activityId:'ride.fit',recordCount:31} as any]}})
  const button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  expect(w.find('#loaded-activity').exists()).toBe(true)
  await w.get('#loaded-activity').setValue('ride.fit')
  await button('Apri attività caricata').trigger('click');await flushPromises()
  expect(w.find('[aria-label="Potenza blocco 1"]').exists()).toBe(false)
  await w.get('[data-block="0"] rect').trigger('click')
  await button('Valori precisi').trigger('click')
  expect(requests[0]).toEqual({datasetId:'fits',segments:[{activityId:'ride.fit'}]})
  await w.get('[aria-label="Potenza blocco 1"]').setValue(220)
  await button('Apri attività caricata').trigger('click');await flushPromises()
  expect(requests).toHaveLength(2)
  await w.get('#reconstruction-session').setValue('snapshot1');await flushPromises()
  await w.get('[data-block="0"] rect').trigger('click')
  await button('Valori precisi').trigger('click')
  expect((w.get('[aria-label="Potenza blocco 1"]').element as HTMLInputElement).value).toBe('220')
  w.unmount()
})

it('draws, undoes and navigates a long loaded activity without refetching its signal',async()=>{
  let proposals=0
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    if(url.endsWith('/propose'))proposals++
    return {ok:true,json:async()=>url.endsWith('/from-loaded')?imported:{...proposal,
      end:10000,blocks:Array.from({length:1000},(_,i)=>({start:i*10,end:(i+1)*10,power:200}))}}
  }))
  const w=mount(ReconstructionPage,{props:{loadedDatasetId:'fits',loadedActivities:[{activityId:'ride.fit'} as any]}})
  const button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  await w.get('#loaded-activity').setValue('ride.fit')
  await button('Apri attività caricata').trigger('click');await flushPromises()
  expect(w.findAll('input[type=number]')).toHaveLength(0)
  expect(w.find('#reconstruction-sensitivity').exists()).toBe(false)
  await button('Zoom +').trigger('click')
  const plot=w.findComponent(ReconstructionChart),svg=plot.get('svg')
  expect(plot.props('start')).toBe(2500)
  vi.spyOn(svg.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:1000,height:350} as DOMRect)
  await button('Aggiungi').trigger('click')
  for(const [event,x] of [['pointerdown',55],['pointermove',515],['pointerup',515]] as const){
    svg.element.dispatchEvent(new MouseEvent(event,{bubbles:true,clientX:x,clientY:140}));await flushPromises()
  }
  await svg.trigger('click')
  expect(plot.props('blocks')).toContainEqual({start:2500,end:5000,power:150})
  await button('Annulla ultima modifica').trigger('click')
  expect(plot.props('blocks')).toHaveLength(1000)
  await w.get('[aria-label="Scorri attività"]').setValue(4000)
  expect(plot.props('start')).toBe(4000);expect(plot.props('end')).toBe(9000)
  await w.get('[data-block="400"] rect').trigger('click')
  await button('Elimina blocchi').trigger('click')
  expect(plot.props('blocks')).toHaveLength(999)
  await button('Annulla ultima modifica').trigger('click')
  expect(plot.props('blocks')).toHaveLength(1000)
  expect(proposals).toBe(1)
  w.unmount()
})

it('identifies the selected existing blocks then allows editing, merging and undo without locks',async()=>{
  const blocks=[{start:0,end:32,power:300},{start:32,end:46,power:100},{start:46,end:80,power:150}]
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/from-loaded')?imported:{...proposal,end:80,blocks,
    saved:{blocks,automaticBlocks:blocks,sensitivity:50,constraints:[{start:0,end:46,on:32,off:14}]}}})))
  const w=mount(ReconstructionPage,{props:{loadedDatasetId:'fits',loadedActivities:[{activityId:'ride.fit'} as any]}})
  const button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  await w.get('#loaded-activity').setValue('ride.fit');await button('Apri attività caricata').trigger('click');await flushPromises()
  expect(w.findComponent(ReconstructionChart).props('constraints')).toEqual([])
  await button('Selezione rettangolare').trigger('click')
  const svg=w.findComponent(ReconstructionChart).get('svg')
  vi.spyOn(svg.element,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:1000,height:350} as DOMRect)
  for(const [event,x] of [['pointerdown',56],['pointermove',580],['pointerup',580]] as const){
    svg.element.dispatchEvent(new MouseEvent(event,{bubbles:true,clientX:x,clientY:200}));await flushPromises()
  }
  await svg.trigger('click')
  expect(button('Identifica ripetute')).toBeDefined()
  await button('Identifica ripetute').trigger('click')
  await w.get('[aria-label="Potenza ON"]').setValue(320)
  await w.get('[aria-label="Potenza OFF"]').setValue(120)
  await button('Applica ripetute').trigger('click')
  const plot=w.findComponent(ReconstructionChart)
  expect(plot.props('blocks')).toEqual([{start:0,end:30,power:320},{start:30,end:45,power:120},{start:45,end:80,power:150}])
  expect(plot.props('constraints')).toEqual([])
  await button('Unisci blocchi').trigger('click')
  expect(plot.props('blocks')).toEqual([{start:0,end:45,power:253.3},{start:45,end:80,power:150}])
  await button('Annulla ultima modifica').trigger('click')
  expect(plot.props('blocks')).toHaveLength(3)
  await button('Aggiorna pre-esportazione').trigger('click')
  expect((w.emitted('queue')!.at(-1)![0] as any)[0].part.constraints).toEqual([])
  w.unmount()
})
