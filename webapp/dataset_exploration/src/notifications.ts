import {ref} from 'vue'

export const notifications=ref<{id:number;text:string;kind:'error'|'info'}[]>([])
let nextId=0
const timers=new Map<number,ReturnType<typeof setTimeout>>()
export function dismissNotification(id:number){
  clearTimeout(timers.get(id));timers.delete(id)
  notifications.value=notifications.value.filter(n=>n.id!==id)
}
export function notify(text:string,kind:'error'|'info'='info'){
  if(notifications.value.some(n=>n.text===text&&n.kind===kind))return
  const id=++nextId
  if(notifications.value.length>=4)dismissNotification(notifications.value[0].id)
  notifications.value.push({id,text,kind})
  timers.set(id,setTimeout(()=>dismissNotification(id),kind==='error'?10000:6000))
}
export function clearNotifications(){for(const id of timers.keys())dismissNotification(id)}
