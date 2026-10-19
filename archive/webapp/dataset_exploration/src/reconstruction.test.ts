import {expect,it} from 'vitest'
import {applyRepeat,moveBoundary,splitBlock,mergeBlocks,cutRanges} from './reconstruction'

const blocks=[{start:0,end:32,power:300},{start:32,end:46,power:100},
  {start:46,end:76,power:310},{start:76,end:91,power:110},{start:91,end:120,power:150}]

it('anchors 30/15 repeats and adjusts only the adjacent boundary',()=>{
  const result=applyRepeat(blocks,[0,1,2,3],30,15,120,[])
  expect(result.blocks.map(b=>[b.start,b.end])).toEqual([[0,30],[30,45],[45,75],[75,90],[90,120]])
  expect(result.blocks.map(b=>b.power)).toEqual([300,100,310,110,150])
  expect(()=>moveBoundary(result.blocks,0,'end',31,[result.constraint])).toThrow()
  expect(()=>splitBlock(result.blocks,20,[result.constraint])).toThrow()
  expect(()=>applyRepeat(blocks,[0,2],30,15,120,[])).toThrow()
})

it('flags a repeat which extends into the next block and rejects crossing its end',()=>{
  expect(applyRepeat(blocks,[0,1],35,15,120,[]).overlap).toBe(true)
  expect(()=>applyRepeat(blocks,[0,1],75,15,120,[])).toThrow()
})

it('moves shared edges without overlap and refuses crossing a neighbour',()=>{
  expect(moveBoundary(blocks,1,'start',31,[]).slice(0,2)).toEqual([
    {start:0,end:31,power:300},{start:31,end:46,power:100}])
  expect(()=>moveBoundary(blocks,1,'start',50,[])).toThrow()
  expect(blocks[0].end).toBe(32)
})

it('splits, merges and partitions cuts without duplicating boundary samples',()=>{
  const split=splitBlock(blocks,15,[])
  expect(split.slice(0,2)).toEqual([{start:0,end:15,power:300},{start:15,end:32,power:300}])
  expect(mergeBlocks(split,[0,1],[])).toEqual(blocks)
  expect(cutRanges([45,20],90)).toEqual([{start:0,end:20},{start:20,end:45},{start:45,end:90}])
})
