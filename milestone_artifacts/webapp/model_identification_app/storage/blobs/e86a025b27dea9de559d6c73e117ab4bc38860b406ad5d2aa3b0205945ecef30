// @vitest-environment jsdom
import {mount,flushPromises} from '@vue/test-utils'
import {describe,it,expect,vi,afterEach} from 'vitest'
import {reactive} from 'vue'
import DatasetPage from './DatasetPage.vue'
import IdentificationPage from './IdentificationPage.vue'
import type {Dataset,Model} from '../types'
const segment=(id:string,group:string)=>({id,group,label:'UtD',filename:id,sha256:id,activity_id:'ride'+id,duration_seconds:30,samples:31,signals:['raw'],warnings:[]})
const ds:Dataset={id:'data',name:'Test',created_at:'2026-09-26',segments:[segment('a','1'),segment('b','2')],stats:{count:2,duration_mean:30,duration_sd:0},filters:null,split:{id:'split',unit:'segment',seed:42,percentages:[70,10,20],assignments:{train:['a'],val:[],test:['b']},actual_percentages:[50,0,50],warnings:[]}}
const model:Model={id:'p1d',version:'1',name:'P1D',equation:'test',initial_conditions:'equilibrium',parameters:[{key:'K',unit:'bpm/W'},{key:'L',unit:'s'},{key:'tau',unit:'s'}],default_config:{lower:[.000001,0,.01],upper:[5,120,1800],n_starts:8,seed:42,max_nfev:500}}
afterEach(()=>vi.unstubAllGlobals())
describe('workflow configurazione',()=>{
  it('inizializza i filtri anche quando il dataset arriva dopo la selezione',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>[]})))
    const w=mount(DatasetPage,{props:{datasets:[],selected:'data',busy:false,act:async f=>{await f()}}})
    await w.setProps({datasets:[ds]});await flushPromises()
    expect(w.text()).toContain('2 segmenti selezionati')
    const groups=w.findAll('.choices input[type=checkbox]')
    await groups[0].setValue(false)
    expect(w.text()).toContain('1 segmenti selezionati')
    w.unmount()
  })
  it('lancia una run da metadata reattivi con i bounds impostati e solo il dataset scelto',async()=>{
    const fetchMock=vi.fn(async()=>({ok:true,json:async()=>({id:'run'})}));vi.stubGlobal('fetch',fetchMock)
    const w=mount(IdentificationPage,{props:{datasets:[ds],selected:'data',models:reactive([model]),runs:[],busy:false,act:async f=>{await f()}}})
    await w.get('input[aria-label="K massimo"]').setValue(2)
    const launch=w.findAll('button').find(b=>b.text().includes('Avvia identificazione'))!
    expect(launch.attributes('disabled')).toBeUndefined()
    await launch.trigger('click');await flushPromises()
    const body=JSON.parse((fetchMock.mock.calls as unknown as [string,RequestInit][])[0][1].body as string)
    expect(body.dataset_id).toBe('data');expect(body.signal).toBe('raw');expect(body.config.upper).toEqual([2,120,1800])
    expect(model.default_config.upper).toEqual([5,120,1800])
    w.unmount()
  })
})
