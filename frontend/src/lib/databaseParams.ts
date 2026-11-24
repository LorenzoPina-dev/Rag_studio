import type { NodeDefinition, ParamDefinition, PipelineNode } from '@/types'

type Config = PipelineNode['config']

/** Regola condivisa con FieldSpec.visible_when del backend. */
export function isParamVisible(param: Pick<ParamDefinition, 'visibleWhen'>, config: Config): boolean {
  if (!param.visibleWhen) return true
  return Object.entries(param.visibleWhen).every(([key, allowed]) => {
    const values = Array.isArray(allowed) ? allowed : [allowed]
    return values.some((value) => String(value) === String(config[key] ?? ''))
  })
}

/** Il selettore target cambia opzioni in base alla modalità scelta. */
export function paramOptions(param: ParamDefinition, config: Config): string[] | undefined {
  if (!param.optionsByMode) return param.options
  const mode = String(config.mode ?? '')
  return param.optionsByMode[mode] ?? param.options
}

export function firstTargetForMode(param: ParamDefinition, mode: string): string | undefined {
  return param.optionsByMode?.[mode]?.[0]
}

export function databaseIdFromDefinition(definition?: Pick<NodeDefinition, 'id' | 'tags'>): string | null {
  if (!definition?.id.startsWith('db-')) return null
  return definition.id.slice(3)
}

/** Firma non segreta per la cache della configurazione derivata. */
export function configFingerprint(config: Config, secretKeys: Set<string>): string {
  return Object.entries(config)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${secretKeys.has(key) ? '***' : String(value)}`)
    .join('&')
}
