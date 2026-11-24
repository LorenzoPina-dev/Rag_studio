import { describe, expect, it } from 'vitest'
import { configFingerprint, databaseIdFromDefinition, firstTargetForMode, isParamVisible, paramOptions } from './databaseParams'
import type { ParamDefinition } from '@/types'

const target: ParamDefinition = {
  key: 'target',
  label: 'Posizione',
  type: 'select',
  defaultValue: 'localhost',
  options: ['embedded', 'localhost', 'docker', 'ip'],
  optionsByMode: { local: ['localhost', 'docker'], remote: ['docker', 'ip'] },
}

describe('database params', () => {
  it('hides fields outside the selected target', () => {
    const host: ParamDefinition = {
      key: 'host',
      label: 'IP o hostname',
      type: 'text',
      defaultValue: '',
      visibleWhen: { target: ['docker', 'ip'] },
    }
    expect(isParamVisible(host, { target: 'localhost' })).toBe(false)
    expect(isParamVisible(host, { target: 'docker' })).toBe(true)
    expect(isParamVisible(host, {})).toBe(false)
    expect(isParamVisible(target, {})).toBe(true)
  })

  it('switches target options and mode defaults consistently', () => {
    expect(paramOptions(target, { mode: 'local' })).toEqual(['localhost', 'docker'])
    expect(paramOptions(target, { mode: 'remote' })).toEqual(['docker', 'ip'])
    expect(firstTargetForMode(target, 'remote')).toBe('docker')
  })

  it('derives the database id only from database nodes', () => {
    expect(databaseIdFromDefinition({ id: 'db-postgresql', tags: ['database'] })).toBe('postgresql')
    expect(databaseIdFromDefinition({ id: 'qdrant-store', tags: [] })).toBeNull()
  })

  it('masks secret values in the derive cache fingerprint', () => {
    const config = { password: 'super-secret', host: '10.0.0.4', port: 5432 }
    const fingerprint = configFingerprint(config, new Set(['password']))
    expect(fingerprint).not.toContain('super-secret')
    expect(fingerprint).toContain('password=***')
    expect(configFingerprint({ ...config, password: 'another' }, new Set(['password']))).toBe(fingerprint)
  })
})
