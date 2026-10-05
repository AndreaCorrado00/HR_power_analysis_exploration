import {describe,it,expect} from 'vitest'
import {trajectoryOption,residualOption} from './diagnostics'
import type {Fit} from '../types'
const fit={segment_id:'a',series:{time:[0,1],power:[200,200],observed:[120,121],predicted:[120,120.9],residual:[0,.1]},pre_window:{available:true,used:true,samples:2,time:[-2,-1],power:[100,100],observed:[119,120]}} as Fit
describe('contesto nei grafici',()=>{
  it('include il contesto solo per HR osservata e Power',()=>{
    const option=trajectoryOption(fit)
    expect(option.series?.[0].data).toEqual([[-2,119],[-1,120],[0,120],[1,121]])
    expect(option.series?.[1].data).toEqual([[0,120],[1,120.9]])
    expect(residualOption(fit).series[0].data).toEqual([[0,0],[1,.1]])
  })
  it('non duplica campioni gia inclusi nel protocollo storico',()=>{
    const option=trajectoryOption({...fit,pre_window:{...fit.pre_window!,included_in_objective:true}})
    expect(option.series?.[0].data).toHaveLength(2)
  })
})
