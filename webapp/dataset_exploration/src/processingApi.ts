import type {Norm} from './types'

export interface SegmentSummary {
  id:string; activityId:string; firstLap:number; lastLap:number; durationSeconds:number
  sampleCount:number; gapCount:number; medianStepSeconds:number; missing:Record<string,number>
}
export interface ProcessingDataset {datasetId:string; sha256:string; segments:SegmentSummary[]}
export interface ProcessPoint {
  elapsed_seconds:number; power_w:number|null; heart_rate_bpm:number|null
  power_ma_w:number|null; heart_rate_ma_bpm:number|null; ma_sample_count:number; ma_incomplete:boolean
  [key:string]:string|number|boolean|null
}
export interface ProcessedSegment {id:string; points:ProcessPoint[]}
export interface ProcessingOptions {datasetId:string; selected:string[]; windowSeconds:number; normalization:Norm}

async function checked(response:Response) {
  if (!response.ok) {
    let message = `Errore ${response.status}`
    try {const body=await response.json(); message=typeof body.detail==='string'?body.detail:message} catch {}
    throw new Error(message)
  }
  return response
}
export async function importSegments(file:File):Promise<ProcessingDataset> {
  return (await checked(await fetch('/api/processing/import', {
    method:'POST', headers:{'Content-Type':'application/zip'}, body:file
  }))).json()
}
async function post(action:string, options:ProcessingOptions) {
  return checked(await fetch(`/api/processing/${action}`, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(options)}))
}
export async function processSegments(options:ProcessingOptions):Promise<{segments:ProcessedSegment[]}> {
  return (await post('preview',options)).json()
}
export async function exportProcessed(options:ProcessingOptions):Promise<Blob> {
  return (await post('export',options)).blob()
}
