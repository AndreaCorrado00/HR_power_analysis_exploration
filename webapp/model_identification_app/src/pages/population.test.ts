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
afterEach(()=>{vi.unstubAllGlobals();sessionStorage.clear()})
describe('parametri atleta',()=>{
  it('salva e recupera giudizio e note, bloccando export delle modifiche non salvate',async()=>{
    const data={...saved, status:'completed',reviews:{},review_context:{warnings:['B costante nel segmento'],labels:{systematic_overestimate:'Sovrastima sistematica'},verdicts:{unreviewed:'Non valutata',positive:'Positiva',negative:'Negativa'},scales:{},colors:{best:'#c7ead2',worst:'#f4b9b4',neutral:'#edf0f2'},legend:'Qualità relativa'},
      model:{keys:[],mean:[],sd:[],mean_ci95:[],fixed:[],covariance:[],correlation:[],observed_correlation:[]},
      test:[{segment_id:'test',filename:'ride.csv',status:'predicted',series:{time:[0,60],power:[100,200],observed:[100,110],predicted:[101,111],lower:[90,100],upper:[110,120],residual:[-1,-1]},metrics:{MAE:1},band_available:true}]}
    vi.stubGlobal('fetch',vi.fn(async(url:string,options?:RequestInit)=>{
      if(options?.method==='PUT'){
        const body=JSON.parse(options.body as string)
        if(!url.endsWith('/reviews/test')||body.analysis_id!=='analysis')throw Error('Wrong identity')
        const review={verdict:body.verdict,labels:body.labels,notes:body.notes,updated_at:'2026-10-01'}
        data.reviews={test:review};return {ok:true,json:async()=>review}
      }
      return {ok:true,json:async()=>data}
    }))
    const options={props:{runs:[run],selected:run.id},global:{stubs:{Chart:true}}}
    let w=mount(PopulationPage,options);await flushPromises()
    await w.get('select[aria-label="Valutazione predizione"]').setValue('negative')
    await w.get('input[value="systematic_overestimate"]').setValue(true)
    await w.get('textarea[aria-label="Note osservazione"]').setValue('Recupero sovrastimato')
    w.unmount();w=mount(PopulationPage,options);await flushPromises()
    expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('Recupero sovrastimato')
    expect(w.get('button[data-export="json"]').attributes('disabled')).toBeDefined()
    await w.get('button[data-save-review]').trigger('click');await flushPromises()
    expect(w.text()).toContain('Osservazione salvata')
    w.unmount();w=mount(PopulationPage,options);await flushPromises()
    expect((w.get('select[aria-label="Valutazione predizione"]').element as HTMLSelectElement).value).toBe('negative')
    expect((w.get('textarea').element as HTMLTextAreaElement).value).toBe('Recupero sovrastimato')
    expect(w.text()).not.toContain('HR prevista troppo piatta')
    w.unmount()
  })
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
    await w.get('select[aria-label="Protocollo predittivo"]').setValue('local_B_10s')
    await w.get('form').trigger('submit');await flushPromises()
    expect(mock.mock.calls[1][0]).toBe('/api/runs/train-run/population')
    expect(JSON.parse(mock.mock.calls[1][1]!.body as string).max_rse_pct).toBe(80)
    expect(JSON.parse(mock.mock.calls[1][1]!.body as string).prediction_mode).toBe('local_B_10s')
    expect(w.text()).toContain('Dati insufficienti')
    expect(w.text()).toContain('3 / 4')
    expect(w.text()).not.toContain('Modello dei parametri dell’atleta')
    w.unmount()
  })
})
