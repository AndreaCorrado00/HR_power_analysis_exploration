import {flushPromises, mount} from '@vue/test-utils'
import {afterEach, expect, it, vi} from 'vitest'
import App from './App.vue'

vi.mock('vue-echarts', () => ({default: {template: '<div class="plot" />'}}))
afterEach(() => vi.unstubAllGlobals())

it('imports segments, selects all, applies global defaults and invalidates an old preview', async () => {
  const requests: any[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/import')) return {ok:true, json:async()=>({datasetId:'dataset',sha256:'abc',segments:
      ['a.csv','b.csv'].map(id=>({id,activityId:'ride',firstLap:1,lastLap:2,durationSeconds:30,
        sampleCount:31,gapCount:0,medianStepSeconds:1,missing:{power_w:0,heart_rate_bpm:0}}))})}
    requests.push(JSON.parse(init.body as string))
    return {ok:true,json:async()=>({segments:[{id:'a.csv',points:[{elapsed_seconds:0,power_w:90,
      heart_rate_bpm:150,power_ma_w:90,heart_rate_ma_bpm:150,ma_sample_count:2,ma_incomplete:true}]}]})}
  }))
  const w = mount(App)
  const navigation = w.findAll('button').find(b => b.text() === 'Elaborazione dataset')
  expect(navigation, 'dedicated processing navigation').toBeDefined()
  await navigation!.trigger('click')
  const file = w.get('input[type=file]')
  Object.defineProperty(file.element, 'files', {value:[new File(['zip'],'segments.zip')]})
  await file.trigger('change'); await flushPromises()
  const button = (text:string) => w.findAll('button').find(b=>b.text()===text)!
  await button('Seleziona tutti').trigger('click')
  expect(w.text()).toContain('2 / 2 selezionati')
  expect((w.get('#processing-window').element as HTMLSelectElement).value).toBe('3')
  await button('Elabora e aggiorna anteprima').trigger('click'); await flushPromises()
  expect(requests[0]).toMatchObject({selected:['a.csv','b.csv'],windowSeconds:3})
  expect(button('Esporta ZIP').attributes('disabled')).toBeUndefined()
  await w.get('#processing-window').setValue('5')
  expect(button('Esporta ZIP').attributes('disabled')).toBeDefined()
  expect(w.text()).toContain('Aggiorna l’anteprima')
  await button('Deseleziona tutti').trigger('click')
  expect(w.text()).toContain('0 / 2 selezionati')
  await button('Seleziona tutti').trigger('click')
  const normalizationToggle=w.findAll('label').find(l=>l.text()==='W/kg')!.get('input')
  await normalizationToggle.setValue(true)
  const weight=w.get('input[placeholder="kg"]')
  await weight.setValue('65'); await weight.setValue('')
  await normalizationToggle.setValue(false)
  await button('Elabora e aggiorna anteprima').trigger('click'); await flushPromises()
  expect(requests.at(-1).normalization.weightKg).toBeNull()
  w.unmount()
})
