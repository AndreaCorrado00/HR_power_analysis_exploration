import {mount} from '@vue/test-utils'
import {nextTick} from 'vue'
import {expect,it,vi} from 'vitest'
import NotificationToasts from './NotificationToasts.vue'
import {notify,notifications} from '../notifications'
it('shows errors above dialogs, supports dismissal and automatically expires notices',async()=>{
  vi.useFakeTimers()
  const w=mount(NotificationToasts)
  try{
    notify('Importazione non riuscita','error');await nextTick()
    expect(document.body.querySelector('[role=alert]')?.textContent).toContain('Importazione non riuscita')
    notify('Importazione non riuscita','error')
    expect(notifications.value).toHaveLength(1)
    ;(document.body.querySelector('[aria-label="Chiudi notifica"]') as HTMLButtonElement).click();await nextTick()
    expect(notifications.value).toHaveLength(0)
    notify('ZIP scaricato');await nextTick()
    expect(document.body.querySelector('[role=status]')?.textContent).toContain('ZIP scaricato')
    vi.advanceTimersByTime(6000);await nextTick()
    expect(document.body.querySelector('[role=status]')).toBeNull()
  }finally{w.unmount();vi.useRealTimers()}
})
