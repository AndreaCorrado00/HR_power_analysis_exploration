import {expect,it} from 'vitest'
import {identifyRepeats,moveBlock,moveBoundary,mergeBlocks} from './reconstruction'

const blocks=[{start:0,end:20,power:150},{start:20,end:52,power:300},
  {start:52,end:66,power:100},{start:66,end:96,power:310},{start:96,end:111,power:110},
  {start:111,end:150,power:150}]

it('identifies the existing repeats with editable powers and no persistent constraint',()=>{
  const result=identifyRepeats(blocks,[1,2,3,4],30,15,320,120,150,[])
  expect(result).toHaveLength(6)
  expect(result.slice(1,5)).toEqual([{start:20,end:50,power:320},{start:50,end:65,power:120},
    {start:65,end:95,power:320},{start:95,end:110,power:120}])
  expect(result[5]).toEqual({start:110,end:150,power:150})
  expect(moveBoundary(result,1,'end',51,[])[2].start).toBe(51)
  expect(mergeBlocks(result,[1,2],[])).toHaveLength(5)
  expect(blocks[1].end).toBe(52)
})

it('recognizes a selection starting with recovery and validates power order and cut limits',()=>{
  const result=identifyRepeats(blocks,[2,3],30,15,320,120,150,[])
  expect(result[2]).toEqual({start:52,end:67,power:120})
  expect(result[3]).toEqual({start:67,end:97,power:320})
  expect(()=>identifyRepeats(blocks,[1,2],30,15,100,200,150,[])).toThrow()
  expect(()=>identifyRepeats(blocks,[1,2],30,15,320,120,150,[52])).toThrow(/taglio/)
  expect(()=>identifyRepeats(blocks,[1,2],100,100,320,120,150,[])).toThrow()
})

it('translates one block while changing only the two contiguous neighbours',()=>{
  const result=moveBlock(blocks,2,5,150,[])
  expect(result[1]).toEqual({start:20,end:57,power:300})
  expect(result[2]).toEqual({start:57,end:71,power:100})
  expect(result[3]).toEqual({start:71,end:96,power:310})
  expect(result[0]).toEqual(blocks[0]);expect(result.slice(4)).toEqual(blocks.slice(4))
  expect(()=>moveBlock(blocks,2,40,150,[])).toThrow()
  expect(()=>moveBlock(blocks,2,5,150,[52])).toThrow(/taglio/)
})

it('keeps explicit cut boundaries and activity endpoints fixed',()=>{
  expect(()=>moveBoundary(blocks,2,'start',53,[],[52],150)).toThrow(/taglio/)
  expect(()=>moveBoundary(blocks,0,'start',2,[],[],150)).toThrow()
  expect(()=>moveBoundary(blocks,5,'end',140,[],[],150)).toThrow()
  expect(()=>mergeBlocks(blocks,[1,2],[],[52])).toThrow(/taglio/)
})
