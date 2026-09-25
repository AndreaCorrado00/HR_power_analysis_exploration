import {mount,flushPromises} from '@vue/test-utils'
import {expect,it,vi} from 'vitest'
import App from './App.vue'
import {loadDataset,series,preview} from './api'
import SignalChart from './components/SignalChart.vue'
vi.mock('./api',()=>({loadDataset:vi.fn(),series:vi.fn(),preview:vi.fn(),exportZip:vi.fn()}))
it('propagates selected, merged, undone and queued laps to the activity chart',async()=>{
  const points=[{elapsedSeconds:0,power:200,heartRate:120},{elapsedSeconds:30,power:220,heartRate:125}]
  vi.mocked(loadDataset).mockResolvedValue({datasetPath:'rides.zip',excluded:[],extractable:[{activityId:'ride.fit',sourcePath:'rides.zip!ride.fit',durationSeconds:30,recordCount:2,hasPower:true,hasHeartRate:true,extractable:true,exclusionReason:null,laps:[1,2,3].map(index=>({index,startElapsedSeconds:(index-1)*10,endElapsedSeconds:index*10,durationSeconds:10}))}]})
  vi.mocked(series).mockResolvedValue(points);vi.mocked(preview).mockResolvedValue(points)
  const w=mount(App,{global:{stubs:{SignalChart:true}}})
  const button=(text:string)=>w.findAll('button').find(b=>b.text()===text)!
  try{
    await button('Carica dataset').trigger('click');await flushPromises()
    await w.get('.card').trigger('click');await flushPromises()
    const chart=()=>w.findAllComponents(SignalChart).find(c=>c.props('detail'))!
    await button('Lap 1').trigger('click');await button('Lap 2').trigger('click')
    expect(chart().props('selectedLaps')).toEqual([1,2])
    await button('Unisci selezionati').trigger('click')
    expect(chart().props('selectedLaps')).toEqual([1,2])
    await button('Annulla unione').trigger('click')
    expect(chart().props('selectedLaps')).toEqual([])
    await button('Lap 1').trigger('click');await button('Lap 3').trigger('click')
    expect(chart().props('selectedLaps')).toEqual([1,3])
    await button("Aggiungi selezionati all'esportazione").trigger('click');await flushPromises()
    expect(chart().props('selectedLaps')).toEqual([])
    expect(chart().props('queuedLaps')).toEqual([1,3])
    expect(vi.mocked(preview).mock.calls.map(c=>c.slice(0,3))).toEqual([['ride.fit',1,1],['ride.fit',3,3]])
  }finally{w.unmount()}
})
