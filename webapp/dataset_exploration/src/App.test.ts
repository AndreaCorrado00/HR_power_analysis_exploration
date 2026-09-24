import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import App from './App.vue'
describe('App', () => { it('shows the dataset path control', () => { const w=mount(App); expect(w.get('label[for="dataset-path"]').text()).toBe('Percorso dataset') }) })
