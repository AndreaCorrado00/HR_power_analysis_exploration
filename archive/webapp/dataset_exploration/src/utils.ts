export function formatDuration(v:number){const s=Math.max(0,Math.round(v));return `${Math.floor(s/3600)}:${String(Math.floor(s%3600/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}
export function normalizationError(active:boolean,value:string,label:string){if(!active)return null;const n=Number(value);return !value||!Number.isFinite(n)||n<=0?`${label}: il valore deve essere maggiore di zero`:null}
export interface LapSegment { laps:number[] }
export function initialSegments(laps:{index:number}[]):LapSegment[]{return laps.map(l=>({laps:[l.index]}))}
export function mergeSegments(segments:LapSegment[],indexes:number[]):LapSegment[]{
  const sorted=[...new Set(indexes)].sort((a,b)=>a-b)
  if(sorted.length<2||sorted.some((v,i)=>i>0&&v!==sorted[i-1]+1))throw new Error('Selezionare segmenti adiacenti')
  const out=segments.map(x=>({laps:[...x.laps]}));const merged={laps:sorted.flatMap(i=>out[i].laps)}
  out.splice(sorted[0],sorted.length,merged);return out
}
export function undoMerge(segments:LapSegment[],index:number):LapSegment[]{
  const out=segments.map(x=>({laps:[...x.laps]}));const source=out[index]
  out.splice(index,1,...source.laps.map(l=>({laps:[l]})));return out
}
