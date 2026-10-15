import type {ProcessingDataset} from './processingApi'
export interface LoadedSelection {activityId:string;firstLap?:number;lastLap?:number}
export interface LoadedRequest {datasetId:string;segments:LoadedSelection[]}
export async function importLoaded(target:'processing'|'reconstruction',selection:LoadedRequest):Promise<ProcessingDataset> {
  const response=await fetch(`/api/${target}/from-loaded`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selection)})
  if(!response.ok){let message=`Errore ${response.status}`;try{const result=await response.json();if(typeof result.detail==='string')message=result.detail}catch{}throw Error(message)}
  return response.json()
}
