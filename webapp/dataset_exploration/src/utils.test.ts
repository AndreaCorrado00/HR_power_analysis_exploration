import { describe,expect,it } from 'vitest'
import { formatDuration, normalizationError } from './utils'
describe('formatDuration',()=>{it('formats h:mm:ss',()=>expect(formatDuration(3661)).toBe('1:01:01'))})
describe('normalizationError',()=>{it('rejects zero only when active',()=>{expect(normalizationError(true,'0','Peso')).toContain('maggiore di zero');expect(normalizationError(false,'0','Peso')).toBeNull()})})
