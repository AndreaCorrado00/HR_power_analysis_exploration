// @vitest-environment jsdom
import {mount,flushPromises} from '@vue/test-utils'
import {describe,it,expect,vi,afterEach} from 'vitest'
import {reactive} from 'vue'
import DatasetPage from './DatasetPage.vue'
import IdentificationPage from './IdentificationPage.vue'
import type {Dataset,Model} from '../types'
const segment=(id:string,group:string)=>({id,group,label:'UtD',filename:id,sha256:id,activity_id:'ride'+id,duration_seconds:30,samples:31,signals:['raw'],warnings:[]})
const ds:Dataset={id:'data',name:'Test',created_at:'2026-09-26',segments:[segment('a','1'),segment('b','2')],stats:{count:2,duration_mean:30,duration_sd:0},filters:null,split:{id:'split',unit:'segment',seed:42,percentages:[70,10,20],assignments:{train:['a'],val:[],test:['b']},actual_percentages:[50,0,50],warnings:[]}}
const model:Model={id:'p1d',version:'1',name:'P1D',equation:'test',initial_conditions:'equilibrium',parameters:[{key:'K',unit:'bpm/W'},{key:'L',unit:'s'},{key:'tau',unit:'s'}],default_config:{lower:[.000001,0,.01],upper:[5,null,1800],n_starts:8,seed:42,max_nfev:500}}
afterEach(()=>vi.unstubAllGlobals())
describe('workflow configurazione',()=>{
  it('distingue attività FIT, mostra anomalie e propone lo split per attività',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>[]})))
    const activity={...ds,split:null,segments:[{...segment('a','unknown'),kind:'activity' as const,warnings:['missing_power'],quality:{missing_power_samples:2,missing_hr_samples:0,gap_count:1}}]}
    const w=mount(DatasetPage,{props:{datasets:[activity],selected:'data',busy:false,act:async f=>{await f()}}})
    await flushPromises()
    expect(w.text()).toContain('1 attività complete')
    expect(w.text()).toContain('potenza mancante: 2')
    expect((w.get('select[aria-label="Unità dello split"]').element as HTMLSelectElement).value).toBe('activity')
    expect(w.get('input[type=file]').attributes('accept')).toContain('.fit')
    w.unmount()
  })
  it('configura B soltanto nella inizializzazione alternativa P1D',async()=>{
    const fetchMock=vi.fn(async()=>({ok:true,json:async()=>({id:'run'})}));vi.stubGlobal('fetch',fetchMock)
    const w=mount(IdentificationPage,{props:{datasets:[ds],selected:'data',models:[model],runs:[],busy:false,act:async f=>{await f()}}})
    await w.get('select[aria-label="Inizializzazione"]').setValue('estimated_equilibrium')
    await w.get('input[aria-label="B minimo"]').setValue(0)
    await w.get('input[aria-label="B massimo"]').setValue(250)
    await w.findAll('button').find(b=>b.text().includes('Avvia identificazione'))!.trigger('click');await flushPromises()
    const body=JSON.parse((fetchMock.mock.calls as unknown as [string,RequestInit][])[0][1].body as string)
    expect(body.config.initialization_mode).toBe('estimated_equilibrium')
    expect(body.config.equilibrium_bounds).toEqual([0,250])
    expect(body.config.lower).toHaveLength(3)
    expect(w.text()).toContain('HR(0)')
    await w.get('select[aria-label="Inizializzazione"]').setValue('equilibrium')
    expect(w.find('input[aria-label="B minimo"]').exists()).toBe(false)
    w.unmount()
  })
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
    expect(body.dataset_id).toBe('data');expect(body.signal).toBe('raw');expect(body.config.upper).toEqual([2,null,1800])
    expect(model.default_config.upper).toEqual([5,null,1800])
    expect(w.get('input[aria-label="L minimo"]').attributes('disabled')).toBeDefined()
    await w.get('input[aria-label="L massimo"]').setValue(10)
    await launch.trigger('click');await flushPromises()
    const custom=JSON.parse((fetchMock.mock.calls as unknown as [string,RequestInit][])[1][1].body as string)
    expect(custom.config.upper[1]).toBe(10)
    await w.get('input[aria-label="L massimo"]').setValue('')
    await launch.trigger('click');await flushPromises()
    const auto=JSON.parse((fetchMock.mock.calls as unknown as [string,RequestInit][])[2][1].body as string)
    expect(auto.config.upper[1]).toBeNull()
    w.unmount()
  })
  it('sceglie esplicitamente short-transient e pre-window senza ricostruire K e tau',async()=>{
    const fetchMock=vi.fn(async()=>({ok:true,json:async()=>({id:'run'})}));vi.stubGlobal('fetch',fetchMock)
    const extended={...model,structures:[{id:'p1d_full',name:'P1D full',parameters:model.parameters,default_config:model.default_config},{id:'short_transient',name:'Short-transient',parameters:[{key:'gamma',unit:'bpm/(W s)'},{key:'L',unit:'s'}],default_config:{lower:[1e-6/1800,0],upper:[500,null],n_starts:8,seed:42,max_nfev:500,model_structure:'short_transient',use_pre_window:false}}]}
    const w=mount(IdentificationPage,{props:{datasets:[ds],selected:'data',models:[extended],runs:[],busy:false,act:async f=>{await f()}}})
    await w.get('select[aria-label="Struttura del modello"]').setValue('short_transient')
    expect(w.find('input[aria-label="tau massimo"]').exists()).toBe(false)
    expect(w.find('input[aria-label="gamma massimo"]').exists()).toBe(true)
    expect((w.get('input[aria-label="Usa pre-window"]').element as HTMLInputElement).checked).toBe(false)
    await w.get('input[aria-label="Usa pre-window"]').setValue(true)
    await w.findAll('button').find(b=>b.text().includes('Avvia identificazione'))!.trigger('click');await flushPromises()
    const body=JSON.parse((fetchMock.mock.calls as unknown as [string,RequestInit][])[0][1].body as string)
    expect(body.config.model_structure).toBe('short_transient')
    expect(body.config.use_pre_window).toBe(true)
    expect(body.config.lower).toHaveLength(2)
    w.unmount()
  })
})
