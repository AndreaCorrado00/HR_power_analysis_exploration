import {mount} from '@vue/test-utils'
import {expect,it,vi} from 'vitest'
import SignalChart from './SignalChart.vue'
vi.mock('vue-echarts',()=>({default:{name:'ChartStub',props:['option'],template:'<div />'}}))
it('marks selected and queued laps at their actual time boundaries and clears selection',async()=>{
  const w=mount(SignalChart,{props:{points:[],duration:60,laps:[{index:1,startElapsedSeconds:0,endElapsedSeconds:20,durationSeconds:20},{index:2,startElapsedSeconds:20,endElapsedSeconds:60,durationSeconds:40}],selectedLaps:[2],queuedLaps:[1]},global:{stubs:{VChart:{props:['option'],template:'<div />'}}}})
  const chart=w.findComponent({name:'ChartStub'})
  const areas=()=>chart.props('option').series[0].markArea.data
  expect(areas()[1][0]).toMatchObject({name:'Lap 2',xAxis:20,itemStyle:{color:'rgba(245,158,11,.30)'}})
  expect(areas()[1][1].xAxis).toBe(60)
  expect(areas()[0][0].itemStyle.color).toBe('rgba(22,163,74,.20)')
  await w.setProps({selectedLaps:[],queuedLaps:[]})
  expect(areas()[1][0].label.show).toBe(false)
  expect(areas()[1][0].itemStyle.color).toBe('rgba(37,99,235,.035)')
  w.unmount()
})
