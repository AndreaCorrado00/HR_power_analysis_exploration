import type {ProcessPoint,ProcessingDataset} from './processingApi'
export interface Block {start:number;end:number;power:number}
export interface Repeat {start:number;end:number;on:number;off:number;phase?:number;partialStart?:boolean;partialEnd?:boolean}
export interface ReconstructionState {blocks:Block[];automaticBlocks:Block[];constraints:Repeat[];sensitivity:number}
export interface Proposal extends ReconstructionState {points:ProcessPoint[];end:number;step:number;gapCount:number;missingPower:number;gaps?:{start:number;end:number}[];laps?:{index:number;start:number;end:number;validSamples:number;invalidSamples:number}[];initialization?:string;saved:ReconstructionState|null}
export interface ReconstructionPart extends ReconstructionState {sourceId:string;start:number;end:number}
export interface ReconstructionItem {key:string;datasetId:string;activityId:string;part:ReconstructionPart;points:ProcessPoint[];exported:boolean;stale?:boolean}
export const copy=<T>(value:T):T=>JSON.parse(JSON.stringify(value))
const near=(a:number,b:number)=>Math.abs(a-b)<1e-6
export const locked=(b:Block,locks:Repeat[])=>locks.some(c=>b.start<c.end&&b.end>c.start)
function selectedRun(blocks:Block[],selection:number[],locks:Repeat[]) {
  const ids=[...new Set(selection)].sort((a,b)=>a-b)
  if(!ids.length||ids.some((i,k)=>!blocks[i]||(k>0&&(i!==ids[k-1]+1||!near(blocks[ids[k-1]].end,blocks[i].start)))))throw Error('Seleziona blocchi consecutivi senza gap.')
  if(ids.some(i=>locked(blocks[i],locks)))throw Error('Rimuovi prima il vincolo ON/OFF della sequenza.')
  return ids
}
export function moveBoundary(blocks:Block[],i:number,edge:'start'|'end',value:number,locks:Repeat[],cuts:number[]=[],duration?:number) {
  const out=copy(blocks),b=out[i],old=b[edge]
  if(!Number.isFinite(value)||value<0)throw Error('Tempo non valido.')
  if(cuts.some(t=>t>=Math.min(old,value)&&t<=Math.max(old,value))&&!near(old,value))throw Error('Il confine coincide con un taglio o lo attraversa.')
  if(duration!==undefined&&!near(old,value)&&((edge==='start'&&near(old,0))||(edge==='end'&&near(old,duration))))throw Error('Il confine esterno della porzione resta fisso.')
  if(locks.some(c=>old>=c.start&&old<=c.end))throw Error('Confine vincolato ON/OFF.')
  const j=edge==='start'?i-1:i+1,other=out[j]
  const adjacent=other&&near(edge==='start'?other.end:other.start,old)
  if(edge==='start') {
    if(value>=b.end||value<(other?(adjacent?other.start+.1:other.end):0))throw Error('Il confine supera il blocco adiacente.')
    b.start=value;if(adjacent)other.end=value
  } else {
    if(value<=b.start||other&&value>(adjacent?other.end-.1:other.start))throw Error('Il confine supera il blocco adiacente.')
    b.end=value;if(adjacent)other.start=value
  }
  return out
}
export function applyRepeat(blocks:Block[],selection:number[],on:number,off:number,end:number,locks:Repeat[],gaps:{start:number;end:number}[]=[]) {
  const ids=selectedRun(blocks,selection,locks)
  if(ids.length<2||!Number.isFinite(on)||!Number.isFinite(off)||on<=0||off<=0)throw Error('Seleziona almeno due blocchi e durate ON/OFF positive.')
  const out=copy(blocks),first=ids[0],last=ids.at(-1)!,oldEnd=out[last].end
  let cursor=out[first].start
  ids.forEach((i,k)=>{out[i].start=cursor;cursor+=k%2?off:on;out[i].end=cursor})
  if(gaps.some(g=>out[first].start<g.end&&cursor>g.start))throw Error('Le ripetute attraversano un gap di registrazione.')
  const next=out[last+1]
  if(cursor>end||next&&cursor>=next.end)throw Error('Le ripetute superano la porzione successiva o la fine della sorgente.')
  if(next&&near(next.start,oldEnd)) {
    if(locked(next,locks)&&!near(cursor,oldEnd))throw Error('La porzione successiva è vincolata.')
    next.start=cursor
  }else if(next&&cursor>next.start)throw Error('Le ripetute attraversano un gap.')
  return {blocks:out,constraint:{start:out[first].start,end:cursor,on,off},overlap:cursor>oldEnd}
}
export function splitBlock(blocks:Block[],time:number,locks:Repeat[]) {
  const i=blocks.findIndex(b=>b.start<time&&b.end>time)
  if(i<0||!Number.isFinite(time))throw Error('Scegli un tempo interno a un blocco.')
  if(locked(blocks[i],locks))throw Error('Rimuovi prima il vincolo ON/OFF.')
  const out=copy(blocks),b=out[i];out.splice(i,1,{...b,end:time},{...b,start:time});return out
}
export function mergeBlocks(blocks:Block[],selection:number[],locks:Repeat[],cuts:number[]=[]) {
  const ids=selectedRun(blocks,selection,locks)
  if(ids.length<2)throw Error('Seleziona almeno due blocchi.')
  const out=copy(blocks),start=out[ids[0]].start,end=out[ids.at(-1)!].end
  if(cuts.some(t=>t>start&&t<end))throw Error('La selezione attraversa un taglio.')
  const power=ids.reduce((sum,i)=>sum+out[i].power*(out[i].end-out[i].start),0)/(end-start)
  out.splice(ids[0],ids.length,{start,end,power:Math.round(power*10)/10});return out
}
export function moveBlock(blocks:Block[],i:number,delta:number,duration:number,cuts:number[]) {
  if(!Number.isFinite(delta))throw Error('Spostamento non valido.')
  const b=blocks[i],previous=blocks[i-1],next=blocks[i+1]
  if(!b)throw Error('Blocco non valido.')
  if(near(delta,0))return copy(blocks)
  const start=b.start+delta,end=b.end+delta
  if(cuts.some(t=>t>=Math.min(start,b.start)&&t<=Math.max(end,b.end)))throw Error('Lo spostamento incontra un taglio.')
  if(!previous||!next||!near(previous.end,b.start)||!near(next.start,b.end)||
     start<=previous.start||end>=next.end||start<0||end>duration)throw Error('Lo spostamento supererebbe un vicino o il confine della porzione.')
  const out=copy(blocks)
  out[i]={...b,start,end};out[i-1].end=start;out[i+1].start=end
  return out
}

export function identifyRepeats(blocks:Block[],selection:number[],on:number,off:number,powerOn:number,powerOff:number,duration:number,cuts:number[]) {
  const ids=selectedRun(blocks,selection,[])
  if(ids.length<2||![on,off,powerOn,powerOff].every(Number.isFinite)||on<=0||off<=0||powerOff<0||powerOn<=powerOff)throw Error('Servono due blocchi, durate positive e potenza ON maggiore della potenza OFF.')
  const out=copy(blocks),first=ids[0],last=ids.at(-1)!,oldEnd=out[last].end,start=out[first].start
  if(cuts.some(t=>t>start&&t<oldEnd))throw Error('La selezione attraversa un taglio.')
  const startsOn=out[first].power>=out[ids[1]].power
  let cursor=start
  ids.forEach((i,k)=>{const isOn=k%2===0?startsOn:!startsOn;out[i]={start:cursor,end:cursor+(isOn?on:off),power:isOn?powerOn:powerOff};cursor=out[i].end})
  if(cuts.some(t=>t>start&&t<=Math.max(cursor,oldEnd))&&!near(cursor,oldEnd))throw Error('La durata delle ripetute supera o sposta un taglio.')
  const next=out[last+1]
  if(cursor>duration||next&&cursor>=next.end)throw Error('Le ripetute superano il blocco successivo o la fine attività.')
  if(!near(cursor,oldEnd)){
    if(!next||!near(next.start,oldEnd))throw Error('Le nuove durate lascerebbero un buco al confine della porzione.')
    next.start=cursor
  }
  return out
}
export function cutRanges(cuts:number[],end:number) {
  const bounds=[0,...[...new Set(cuts)].filter(t=>t>0&&t<end).sort((a,b)=>a-b),end]
  return bounds.slice(0,-1).map((start,i)=>({start,end:bounds[i+1]}))
}
export function insertBlock(blocks:Block[],block:Block,locks:Repeat[],end:number) {
  if(!Object.values(block).every(Number.isFinite)||block.start<0||block.end> end||block.end<=block.start||block.power<0)throw Error('Intervallo non valido.')
  if(locked(block,locks))throw Error('Rimuovi prima il vincolo ON/OFF della porzione interessata.')
  const out:Block[]=[]
  for(const b of blocks){
    if(b.end<=block.start||b.start>=block.end)out.push({...b})
    else {if(b.start<block.start)out.push({...b,end:block.start});if(b.end>block.end)out.push({...b,start:block.end})}
  }
  return [...out,{...block}].sort((a,b)=>a.start-b.start)
}
export function deleteBlocks(blocks:Block[],selection:number[],locks:Repeat[]) {
  if(selection.some(i=>blocks[i]&&locked(blocks[i],locks)))throw Error('Rimuovi prima il vincolo ON/OFF.')
  return blocks.filter((_,i)=>!selection.includes(i)).map(b=>({...b}))
}
export function viewport(start:number,end:number,duration:number) {
  const width=Math.min(duration,Math.max(Math.min(1,duration),end-start))
  const left=Math.min(Math.max(0,start),duration-width)
  return {start:left,end:left+width}
}
async function checked(response:Response) {
  if(!response.ok){let message=`Errore ${response.status}`;try{const d=await response.json();if(typeof d.detail==='string')message=d.detail}catch{}throw Error(message)}
  return response
}
export async function importReconstruction(file:File):Promise<ProcessingDataset> {
  return (await checked(await fetch('/api/reconstruction/import',{method:'POST',body:file}))).json()
}
export async function proposeReconstruction(datasetId:string,sourceId:string,sensitivity:number):Promise<Proposal> {
  return (await checked(await fetch('/api/reconstruction/propose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({datasetId,sourceId,sensitivity})}))).json()
}
export async function exportReconstruction(items:ReconstructionItem[],extraction:unknown) {
  return checked(await fetch('/api/reconstruction/export',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({segments:items.map(x=>({...x.part,datasetId:x.datasetId})),extraction})}))
}
