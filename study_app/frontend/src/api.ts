export async function api(path:string, options:RequestInit={}):Promise<any>{
 const response=await fetch('/api'+path,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers}})
 const data=await response.json()
 if(!response.ok)throw new Error(data.message || JSON.stringify(data.detail || data))
 return data
}
export const post=(path:string,body:any)=>api(path,{method:'POST',body:JSON.stringify(body)})
export const fmt=(n:any,d=2)=>n==null?'—':Number(n).toLocaleString('it-IT',{maximumFractionDigits:d})
export const date=(s:string)=>new Date(s).toLocaleString('it-IT')
