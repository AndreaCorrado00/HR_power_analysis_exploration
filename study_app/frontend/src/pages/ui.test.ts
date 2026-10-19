// @vitest-environment jsdom
import {afterEach,describe,it,expect,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import AthletesPage from './AthletesPage.vue'
import BlockEditor from '../components/BlockEditor.vue'
import ExperimentsPage from './ExperimentsPage.vue'
afterEach(()=>vi.restoreAllMocks())
describe('local study flows',()=>{
 it('creates an athlete explicitly and emits the saved selection',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({id:'new',first_name:'Anna',last_name:'Rossi',age:30})})))
  const w=mount(AthletesPage,{props:{athletes:[]}})
  await w.findAll('button')[0].trigger('click')
  const inputs=w.findAll('input');await inputs[0].setValue('Anna');await inputs[1].setValue('Rossi')
  await w.find('form').trigger('submit');await flushPromises()
  expect(w.emitted('select')?.[0][0]).toMatchObject({id:'new',first_name:'Anna'})
  expect(w.emitted('refresh')).toHaveLength(1)
  w.unmount()
 })
 it('edits repetitions without expanding or deleting the underlying blocks',async()=>{
  const blocks:any[]=[{duration_s:300,target:{kind:'constant',watts:150}}]
  const w=mount(BlockEditor,{props:{blocks}})
  await w.findAll('button').find(x=>x.text()==='+ Ripetizione')!.trigger('click')
  expect(blocks[1].repeat).toBe(3);expect(blocks[1].blocks).toHaveLength(2)
  expect(blocks[0].duration_s).toBe(300)
  w.unmount()
 })
 it('never starts identification while opening the experiment page',async()=>{
  const paths:string[]=[]
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>{paths.push(path);return {ok:true,json:async()=>[]}}))
  const w=mount(ExperimentsPage,{props:{athlete:{id:'a'}}});await flushPromises()
  expect(paths).toEqual(['/api/athletes/a/experiments','/api/athletes/a/jobs'])
  expect(w.text()).toContain('Prepara esperimento')
  expect(w.text()).not.toContain('Avvia identificazione')
  w.unmount()
 })
})
