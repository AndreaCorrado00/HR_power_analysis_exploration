export async function api<T>(path:string, method='GET', data?:unknown):Promise<T> {
  const form = data instanceof FormData
  const response = await fetch('/api'+path,{method,headers:data&&!form?{'Content-Type':'application/json'}:undefined,body:data?(form?data:JSON.stringify(data)):undefined})
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try { const result=await response.json();message=typeof result.detail==='string'?result.detail:JSON.stringify(result.detail) } catch {}
    throw new Error(message)
  }
  return response.json()
}
export const fmt = (n:number|null|undefined,digits=2) => n==null||!Number.isFinite(n)?'n.d.':n.toLocaleString('it-IT',{maximumFractionDigits:digits})
export const date = (s:string) => new Date(s).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})
export const statusLabel = (s:string) => ({queued:'In coda',running:'In esecuzione',completed:'Completata',completed_with_errors:'Completata con errori',failed:'Fallita',interrupted:'Interrotta'}[s]||s)
