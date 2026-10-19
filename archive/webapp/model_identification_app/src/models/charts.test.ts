import {describe,it,expect} from 'vitest'
import {boxSummary,compatibleParameters} from './charts'
describe('distribuzioni',()=>{
  it('conserva gli outlier fuori dai baffi di Tukey',()=>{
    const r=boxSummary([1,2,3,4,5,6,7,8,100])!
    expect(r.box).toEqual([1,3,5,7,8]);expect(r.outliers).toEqual([100]);expect(r.n).toBe(9)
  })
  it('non inventa statistiche per gruppi vuoti o valori non finiti',()=>{
    expect(boxSummary([])).toBeNull();expect(boxSummary([NaN,2])!.box).toEqual([2,2,2,2,2])
  })
  it('confronta soltanto parametri con la stessa unità',()=>{
    expect(compatibleParameters([{key:'K',unit:'bpm/W'},{key:'L',unit:'s'}],[{key:'K',unit:'bpm/W'},{key:'L',unit:'samples'}])).toEqual([{key:'K',unit:'bpm/W'}])
  })
})
