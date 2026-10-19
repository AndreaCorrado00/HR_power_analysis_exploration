import {mount,flushPromises} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import DatasetBrowser from './DatasetBrowser.vue'
import {notifications,clearNotifications} from '../notifications'
afterEach(()=>{vi.unstubAllGlobals();clearNotifications()})
it('navigates into a ZIP folder and emits only the selected FIT',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({path:'C:/rides.zip',folder:'',isZip:true,parent:'C:/',entries:[{name:'rides',path:'rides',kind:'directory'}]})})
    .mockResolvedValueOnce({ok:true,json:async()=>({path:'C:/rides.zip',folder:'rides',isZip:true,parent:'C:/',entries:[{name:'a.fit',path:'rides/a.fit',kind:'fit'},{name:'b.fit',path:'rides/b.fit',kind:'fit'}]})})
  vi.stubGlobal('fetch',fetcher)
  const w=mount(DatasetBrowser,{props:{initialPath:'C:/rides.zip'}});await flushPromises()
  await w.findAll('button').find(b=>b.text()==='Cartella: rides')!.trigger('click');await flushPromises()
  expect(fetcher.mock.calls[1][0]).toContain('folder=rides')
  await w.get('input[aria-label="b.fit"]').setValue(true)
  await w.findAll('button').find(b=>b.text().startsWith('Importa selezionati'))!.trigger('click')
  expect(w.emitted('choose')![0]).toEqual([{path:'C:/rides.zip',folder:'rides',selectedFiles:['rides/b.fit']}])
})
it('imports the current folder recursively without limiting selection',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({path:'C:/data',folder:'',isZip:false,parent:'C:/',entries:[]})}))
  const w=mount(DatasetBrowser,{props:{initialPath:'C:/data'}});await flushPromises()
  await w.findAll('button').find(b=>b.text()==='Importa cartella e sottocartelle')!.trigger('click')
  expect(w.emitted('choose')![0]).toEqual([{path:'C:/data',folder:'',selectedFiles:null}])
})
it('shows a readable error when an archive cannot be opened',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Archivio non valido'})}))
  const w=mount(DatasetBrowser,{props:{initialPath:'broken.zip'}});await flushPromises()
  expect(notifications.value[0]).toMatchObject({text:'Archivio non valido',kind:'error'})
})
it('selects and deselects all visible FITs with partial selection feedback',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({path:'C:/data',folder:'',isZip:false,parent:'C:/',entries:[{name:'a.fit',path:'C:/data/a.fit',kind:'fit'},{name:'b.fit',path:'C:/data/b.fit',kind:'fit'},{name:'subfolder',path:'C:/data/subfolder',kind:'directory'}]})}))
  const w=mount(DatasetBrowser,{props:{initialPath:'C:/data'}});await flushPromises()
  const all=w.get<HTMLInputElement>('input[aria-label="Seleziona tutti i FIT"]')
  await all.setValue(true)
  expect(w.get<HTMLInputElement>('input[aria-label="a.fit"]').element.checked).toBe(true)
  expect(w.get<HTMLInputElement>('input[aria-label="b.fit"]').element.checked).toBe(true)
  await w.get('input[aria-label="a.fit"]').setValue(false)
  expect(all.element.indeterminate).toBe(true)
  await all.setValue(true)
  await w.findAll('button').find(b=>b.text().startsWith('Importa selezionati'))!.trigger('click')
  expect(w.emitted('choose')![0]).toEqual([{path:'C:/data',folder:'',selectedFiles:['a.fit','b.fit']}])
  await all.setValue(false)
  expect(w.get<HTMLInputElement>('input[aria-label="b.fit"]').element.checked).toBe(false)
})
