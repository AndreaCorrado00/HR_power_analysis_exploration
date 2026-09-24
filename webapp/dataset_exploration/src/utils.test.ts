import { describe,expect,it } from 'vitest'
import { formatDuration, normalizationError, initialSegments, mergeSegments, undoMerge } from './utils'
describe('formatDuration',()=>{it('formats h:mm:ss',()=>expect(formatDuration(3661)).toBe('1:01:01'))})
describe('normalizationError',()=>{it('rejects zero only when active',()=>{expect(normalizationError(true,'0','Peso')).toContain('maggiore di zero');expect(normalizationError(false,'0','Peso')).toBeNull()})})
describe('lap partitions',()=>{
  const laps=[{index:1},{index:2},{index:3},{index:4}] as any
  it('starts with one segment per lap',()=>expect(initialSegments(laps).map(x=>x.laps)).toEqual([[1],[2],[3],[4]]))
  it('merges only adjacent selected segments',()=>expect(mergeSegments(initialSegments(laps),[1,2]).map(x=>x.laps)).toEqual([[1],[2,3],[4]]))
  it('undoes a merge into original laps',()=>expect(undoMerge([{laps:[1,2,3]}],0).map(x=>x.laps)).toEqual([[1],[2],[3]]))
  it('rejects non-adjacent merge indexes',()=>expect(()=>mergeSegments(initialSegments(laps),[0,2])).toThrow(/adiacenti/))
})
