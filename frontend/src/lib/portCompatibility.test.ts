import { describe, expect, it } from 'vitest'
import type { PortDefinition } from '@/types'
import { connectionIsCompatible, portsCompatible, semanticPortType } from './portCompatibility'

const port = (id: string, dataType: PortDefinition['dataType'], typeLabel: string): PortDefinition => ({
  id,
  label: id,
  dataType,
  typeLabel,
  color: '#ffffff',
})

describe('semanticPortType', () => {
  it('prefers strong labels over the coarse dataType', () => {
    expect(semanticPortType(port('out_index', 'json', 'IndexRef'))).toBe('index')
    expect(semanticPortType(port('in_context', 'json', 'Context'))).toBe('context')
    expect(semanticPortType(port('out_ranked', 'array', 'RankedCandidates'))).toBe('candidates')
    expect(semanticPortType(port('docs', 'json', 'List[Document]'))).toBe('documents')
  })

  it('falls back to dataType for generic ports', () => {
    expect(semanticPortType(port('vector', 'embedding', 'vector'))).toBe('embedding')
    expect(semanticPortType(port('payload', 'json', 'payload'))).toBe('json')
    expect(semanticPortType(port('anything', 'any', 'anything'))).toBe('any')
  })
})

describe('portsCompatible', () => {
  it('allows matching semantic types', () => {
    expect(portsCompatible(port('a', 'json', 'IndexRef'), port('b', 'json', 'IndexRef'))).toBe(true)
    expect(portsCompatible(port('a', 'documents', 'documents'), port('b', 'documents', 'documents'))).toBe(true)
  })

  it('does not confuse an IndexRef with a generic JSON payload', () => {
    expect(portsCompatible(port('a', 'json', 'IndexRef'), port('b', 'json', 'payload'))).toBe(false)
  })

  it('keeps context ports isolated from every other type', () => {
    expect(portsCompatible(port('a', 'json', 'Context'), port('b', 'json', 'payload'))).toBe(false)
    expect(portsCompatible(port('a', 'text', 'answer'), port('b', 'json', 'Context'))).toBe(false)
  })

  it('treats "any" as a wildcard', () => {
    expect(portsCompatible(port('a', 'any', 'anything'), port('b', 'json', 'IndexRef'))).toBe(true)
    expect(portsCompatible(port('a', 'json', 'IndexRef'), port('b', 'any', 'anything'))).toBe(true)
  })
})

describe('connectionIsCompatible', () => {
  const nodes = [
    { id: 'a', outputs: [port('out_index', 'json', 'IndexRef')], inputs: [] },
    { id: 'b', outputs: [], inputs: [port('in_index', 'json', 'IndexRef')] },
    { id: 'c', outputs: [], inputs: [port('in_context', 'json', 'Context')] },
    { id: 'd', outputs: [port('out_any', 'any', 'anything')], inputs: [] },
  ]

  it('accepts a compatible pair of handles', () => {
    expect(connectionIsCompatible({ source: 'a', target: 'b', sourceHandle: 'out_index', targetHandle: 'in_index' }, nodes)).toBe(true)
  })

  it('rejects incompatible handles, unknown nodes and self-connections', () => {
    expect(connectionIsCompatible({ source: 'a', target: 'c', sourceHandle: 'out_index', targetHandle: 'in_context' }, nodes)).toBe(false)
    expect(connectionIsCompatible({ source: 'a', target: 'missing', sourceHandle: 'out_index', targetHandle: 'in_index' }, nodes)).toBe(false)
    expect(connectionIsCompatible({ source: 'a', target: 'a', sourceHandle: 'out_index', targetHandle: 'in_index' }, nodes)).toBe(false)
    expect(connectionIsCompatible({ source: 'a', target: 'b', sourceHandle: 'nope', targetHandle: 'in_index' }, nodes)).toBe(false)
  })

  it('allows a wildcard output to feed a typed input', () => {
    expect(connectionIsCompatible({ source: 'd', target: 'b', sourceHandle: 'out_any', targetHandle: 'in_index' }, nodes)).toBe(true)
  })
})
