// @vitest-environment jsdom
import {mount,flushPromises} from '@vue/test-utils'
import {describe,it,expect,vi,afterEach} from 'vitest'
import PopulationPage from './PopulationPage.vue'
import type {Run} from '../types'
const run:Run={id:'train-run',manifest_filename:'run.json',status:'completed',created_at:'2026-09-29',
  dataset:{id:'dataset',name:'Athlete',created_at:'2026-09-29',segments:[],stats:{count:0,duration_mean:0,duration_sd:null},split:null,filters:null},
  split:{id:'split',unit:'activity',seed:42,percentages:[70,10,20],assignments:{train:[],val:[],test:[]},actual_percentages:[70,10,20],warnings:[]},
  model:{id:'p1d',version:'3',name:'P1D',equation:'',initial_conditions:'',parameters:[],default_config:{lower:[],upper:[],n_starts:8,seed:42,max_nfev:500}},
  signal:'raw',columns:[],progress:{done:0,total:0,failed:0},environment:{code_sha256:'test'},
  config:{lower:[],upper:[],n_starts:8,seed:42,max_nfev:500,model_structure:'p1d_full',initialization_mode:'estimated_equilibrium'}}
const config={max_rse_pct:100,max_correlation:.98,exclude_near_bounds:false,draws:200,seed:42}
const saved={id:'analysis',created_at:'2026-09-29',status:'insufficient_data',reason:'Dati insufficienti',config,train_count:4,retained_vectors:3,minimum_vectors:6,parameters:[],warnings:[],distributions:{},screening:[],model:null,test:[]}
afterEach(()=>vi.unstubAllGlobals())
describe('parametri atleta',()=>{
  it('richiede B stimato senza offrire HR test come fallback',async()=>{
    vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>null})))
    const w=mount(PopulationPage,{props:{runs:[{...run,config:{...run.config,initialization_mode:'equilibrium'}}],selected:run.id}})
    await flushPromises()
    expect(w.get('button[type=submit]').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('HR del test non viene usata')
    w.unmount()
  })
  it('salva le soglie esplicite e mostra i risultati insufficienti senza parametri inventati',async()=>{
    const mock=vi.fn(async(_url:string,options?:RequestInit)=>({ok:true,json:async()=>options?.method==='POST'?saved:null}))
    vi.stubGlobal('fetch',mock)
    const w=mount(PopulationPage,{props:{runs:[run],selected:run.id}})
    await flushPromises()
    await w.get('input[aria-label="RSE massimo"]').setValue(80)
    await w.get('form').trigger('submit');await flushPromises()
    expect(mock.mock.calls[1][0]).toBe('/api/runs/train-run/population')
    expect(JSON.parse(mock.mock.calls[1][1]!.body as string).max_rse_pct).toBe(80)
    expect(w.text()).toContain('Dati insufficienti')
    expect(w.text()).toContain('3 / 4')
    expect(w.text()).not.toContain('Modello dei parametri dell’atleta')
    w.unmount()
  })
})
