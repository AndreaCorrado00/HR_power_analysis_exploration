import {describe,it,expect} from 'vitest'
import {elapsed,metricColor,trajectory} from './populationReview'

describe('visualizzazione revisione',()=>{
  it('colora bias assoluto e gestisce parità e mancanti',()=>{
    const colors={best:'#c7ead2',worst:'#f4b9b4',neutral:'#edf0f2'}
    const scale={min:0,max:10,absolute:true}
    expect(metricColor(-10,scale,colors)).toBe('#f4b9b4')
    expect(metricColor(0,scale,colors)).toBe('#c7ead2')
    expect(metricColor(null,scale,colors)).toBe('#edf0f2')
    expect(metricColor(5,{...scale,min:5,max:5},colors)).toBe('#edf0f2')
  })
  it('mantiene ore oltre 24 e allinea potenza e HR',()=>{
    expect(elapsed(90061)).toBe('25:01:01')
    expect(elapsed(-10)).toBe('-00:00:10')
    const option=trajectory({series:{time:[0,65],power:[100,200],observed:[110,120],predicted:[111,122],lower:[105,115],upper:[115,125],residual:[-1,-2]}} as any)
    expect(option.series.find(s=>s.name==='Potenza')?.data).toEqual([[0,100],[65,200]])
    expect(option.xAxis[0].axisLabel.formatter(65)).toBe('00:01:05')
    expect(option.tooltip.formatter([{axisValue:65,seriesName:'Potenza',value:[65,200],marker:''}])).toBe('00:01:05<br/>Potenza: 200')
  })
})
