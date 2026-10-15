import {mount,flushPromises} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import App from './App.vue'
import ProcessingPage from './components/ProcessingPage.vue'
vi.mock('vue-echarts',()=>({default:{template:'<div />'}}))
afterEach(()=>vi.unstubAllGlobals())
const segments=[{id:'a.csv',activityId:'ride',firstLap:1,lastLap:1,durationSeconds:10,sampleCount:11,medianStepSeconds:1,gapCount:0,missing:{power_w:0,heart_rate_bpm:0}}]
const points=Array.from({length:11},(_,i)=>({elapsed_seconds:i,power_w:200,power_ma_w:200,heart_rate_bpm:150,heart_rate_ma_bpm:150}))
async function upload(input:any,name:string){Object.defineProperty(input.element,'files',{value:[new File(['zip'],name)],configurable:true});await input.trigger('change');await flushPromises()}

it('keeps queued reconstructions across imports, scopes dirty flags and exports every dataset',async()=>{
  let imported=0,exportBody:any
  vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{
    if(url.endsWith('/import'))return {ok:true,json:async()=>({datasetId:`d${++imported}`,segments})}
    if(url.endsWith('/export')){exportBody=JSON.parse(init.body as string);return {ok:true,headers:new Headers(),json:async()=>({writtenPath:'test.zip'})}}
    return {ok:true,json:async()=>({points,blocks:[{start:0,end:11,power:200}],end:11,step:1,gapCount:0,missingPower:0})}
  }))
  const w=mount(App),button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  await button('Ricostruzione allenamenti').trigger('click')
  await upload(w.get('#reconstruction-file'),'first.zip')
  await w.get('#reconstruction-source').setValue('a.csv');await flushPromises()
  await button('Aggiorna pre-esportazione').trigger('click')
  await upload(w.get('#reconstruction-file'),'second.zip')
  await w.get('#reconstruction-source').setValue('a.csv');await flushPromises()
  await w.get('[data-block="0"] rect').trigger('click');await button('Valori precisi').trigger('click')
  await w.get('[aria-label="Potenza blocco 1"]').setValue(300)
  await button('Aggiorna pre-esportazione').trigger('click')
  await button('Apri pre-esportazione').trigger('click');await flushPromises()
  expect(w.findAll('.review-card')).toHaveLength(2)
  expect(w.get('.review').text()).not.toContain('Bozza modificata')
  await button('Esporta 2 segmenti').trigger('click');await flushPromises()
  expect(exportBody.segments.map((p:any)=>p.datasetId)).toEqual(['d1','d2'])
  expect(exportBody.segments.map((p:any)=>p.blocks[0].power)).toEqual([200,300])
  await w.get('.review .close').trigger('click')
  await w.get('#reconstruction-session').setValue('d1');await flushPromises()
  await w.get('[data-block="0"] rect').trigger('click');await button('Valori precisi').trigger('click')
  await w.get('[aria-label="Potenza blocco 1"]').setValue(210)
  await button('Apri pre-esportazione').trigger('click');await flushPromises()
  expect(w.findAll('.review-card')[0].text()).toContain('Bozza modificata')
  expect(w.findAll('.review-card')[1].text()).not.toContain('Bozza modificata')
  w.unmount()
})

it('restores processing selection, parameters and exportable preview after another import',async()=>{
  let imported=0
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/import')?
    {datasetId:`d${++imported}`,segments}:{segments:[{id:'a.csv',points}]}})))
  const w=mount(ProcessingPage),button=(label:string)=>w.findAll('button').find(b=>b.text()===label)!
  await upload(w.get('input[type=file]'),'first.zip')
  await button('Seleziona tutti').trigger('click');await w.get('#processing-window').setValue(5)
  await button('Elabora e aggiorna anteprima').trigger('click');await flushPromises()
  expect(button('Esporta ZIP').attributes('disabled')).toBeUndefined()
  await upload(w.get('input[type=file]'),'second.zip')
  await w.get('#processing-window').setValue(10)
  await w.get('#processing-session').setValue('d1');await flushPromises()
  expect((w.get('#processing-window').element as HTMLSelectElement).value).toBe('5')
  expect(w.text()).toContain('1 / 1 selezionati')
  expect(button('Esporta ZIP').attributes('disabled')).toBeUndefined()
  expect(w.find('.preview').exists()).toBe(true)
  w.unmount()
})
