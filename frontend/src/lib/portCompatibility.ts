import type { PortDefinition } from '@/types'

/**
 * Semantic port type used by the editor to allow only meaningful connections.
 * `dataType` alone is too coarse: both Qdrant's index and a generic JSON payload
 * are "json", but only an IndexRef may feed an `in_index` port.
 */
type SemanticType =
  | 'documents'
  | 'chunks'
  | 'embedding'
  | 'query'
  | 'index'
  | 'candidates'
  | 'text'
  | 'json'
  | 'array'
  | 'any'

type PortLike = Pick<PortDefinition, 'dataType' | 'typeLabel'> & { id?: string }

export type ConnectionLike = {
  source: string | null
  target: string | null
  sourceHandle?: string | null
  targetHandle?: string | null
}

export function semanticPortType(port: PortLike): SemanticType {
  const label = (port.typeLabel ?? '').toLowerCase().trim()
  const id = (port.id ?? '').toLowerCase()

  if (label.includes('indexref') || label === 'index' || id.endsWith('_index') || id === 'index') return 'index'
  if (label.includes('candidate') || label.includes('ranked') || id.includes('candidate') || id.includes('ranked') || id.includes('context')) {
    return 'candidates'
  }
  if (label.includes('document') || label === 'list[document]') return 'documents'
  if (label.includes('chunk')) return 'chunks'
  if (label.includes('embedding')) return 'embedding'
  if (label.includes('query')) return 'query'
  if (label.includes('answer')) return 'text'

  if (port.dataType === 'any') return 'any'
  return port.dataType as SemanticType
}

export function portsCompatible(source: PortLike, target: PortLike): boolean {
  const sourceType = semanticPortType(source)
  const targetType = semanticPortType(target)
  if (sourceType === 'any' || targetType === 'any') return true
  return sourceType === targetType
}

/** Guard used both by React Flow dragging and by the store-level onConnect. */
export function connectionIsCompatible(
  connection: ConnectionLike,
  nodes: Array<{ id: string; outputs: PortDefinition[]; inputs: PortDefinition[] }>,
): boolean {
  if (!connection.source || !connection.target || connection.source === connection.target) return false

  const source = nodes.find((node) => node.id === connection.source)
  const target = nodes.find((node) => node.id === connection.target)
  if (!source || !target) return false

  const output = source.outputs.find((port) => port.id === connection.sourceHandle)
  const input = target.inputs.find((port) => port.id === connection.targetHandle)
  if (!output || !input) return false

  return portsCompatible(output, input)
}
