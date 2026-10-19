import {describe,it,expect} from 'vitest'
import {points,chartOption} from './charts'
describe('scientific charts',()=>{
 it('breaks the line across recording gaps',()=>{expect(points([0,1,5],[100,110,120])).toEqual([[0,100],[1,110],[3,null],[5,120]])})
 it('does not convert missing measurements to zero',()=>{expect(points([0,1],[null,0])).toEqual([[0,null],[1,0]])})
 it('keeps power and HR bands independent',()=>{
  const s={elapsed:[0,1],power_mean:[100,110],power_low:[90,100],power_high:[110,120],hr_chain:[120,121],hr_low:[110,111],hr_high:[130,131]}
  const p=chartOption(s,true,false);expect(p.series.some((x:any)=>x.name==='HR · limite inferiore')).toBe(false)
  expect(p.series.some((x:any)=>x.name==='P · limite inferiore')).toBe(true)
 })
})
