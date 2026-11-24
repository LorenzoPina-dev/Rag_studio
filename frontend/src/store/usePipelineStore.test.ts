import { beforeEach, describe, expect, it } from 'vitest'
import type { NodeDefinition, Pipeline, PortDefinition } from '@/types'
import { usePipelineStore } from './usePipelineStore'

const port = (id: string, dataType: PortDefinition['dataType'], typeLabel: string): PortDefinition => ({
  id,
  label: id,
  dataType,
  typeLabel,
  color: '#ffffff',
})

const sourceDefinition: NodeDefinition = {
  id: 'source',
  name: 'Document source',
  category: 'Data Sources',
  kind: 'input',
  description: 'Fixture source node',
  accent: '#7296FF',
  inputs: [],
  outputs: [port('out_documents', 'documents', 'documents')],
  params: [{ key: 'limit', label: 'Limit', type: 'number', defaultValue: 10 }],
  tags: [],
}

const consumerDefinition: NodeDefinition = {
  ...sourceDefinition,
  id: 'consumer',
  name: 'Chunker',
  kind: 'chunking',
  inputs: [port('in_documents', 'documents', 'documents')],
  outputs: [port('out_chunks', 'chunks', 'chunks')],
  params: [],
}

const indexedDefinition: NodeDefinition = {
  ...sourceDefinition,
  id: 'indexed',
  name: 'Index writer',
  kind: 'indexing',
  inputs: [port('in_index', 'json', 'IndexRef')],
  outputs: [],
  params: [],
}

const pipeline: Pipeline = {
  id: 'pl_test',
  projectId: 'pr_test',
  name: 'Test pipeline',
  description: 'Fixture',
  environment: 'Development',
  status: 'draft',
  version: 'v0.1.0',
  updatedAt: '2026-01-01T00:00:00Z',
  nodes: [],
  edges: [],
}

beforeEach(() => {
  usePipelineStore.getState().reset()
})

describe('usePipelineStore', () => {
  it('creates nodes from the catalog definition, including default params and ports', () => {
    usePipelineStore.getState().addNode(sourceDefinition, { x: 10, y: 20 })
    const state = usePipelineStore.getState()

    expect(state.nodes).toHaveLength(1)
    expect(state.nodes[0].data.pipelineNode).toMatchObject({
      definitionId: 'source',
      name: 'Document source',
      position: { x: 10, y: 20 },
      config: { limit: 10 },
    })
    expect(state.nodes[0].data.pipelineNode.outputs).toEqual(sourceDefinition.outputs)
    expect(state.dirty).toBe(true)
    expect(state.selectedNodeId).toBe(state.nodes[0].id)
  })

  it('accepts compatible connections and rejects mismatched semantic ports', () => {
    const store = usePipelineStore.getState()
    store.addNode(sourceDefinition, { x: 0, y: 0 })
    store.addNode(consumerDefinition, { x: 200, y: 0 })
    store.addNode(indexedDefinition, { x: 400, y: 0 })

    const current = usePipelineStore.getState()
    const [source, consumer, indexed] = current.nodes

    current.onConnect({
      source: source.id,
      sourceHandle: 'out_documents',
      target: consumer.id,
      targetHandle: 'in_documents',
    })
    expect(usePipelineStore.getState().edges).toHaveLength(1)

    usePipelineStore.getState().onConnect({
      source: source.id,
      sourceHandle: 'out_documents',
      target: indexed.id,
      targetHandle: 'in_index',
    })
    expect(usePipelineStore.getState().edges).toHaveLength(1)
  })

  it('records the source dataType on the edge', () => {
    const store = usePipelineStore.getState()
    store.addNode(sourceDefinition, { x: 0, y: 0 })
    store.addNode(consumerDefinition, { x: 200, y: 0 })
    const [source, consumer] = usePipelineStore.getState().nodes

    usePipelineStore.getState().onConnect({
      source: source.id,
      sourceHandle: 'out_documents',
      target: consumer.id,
      targetHandle: 'in_documents',
    })

    expect(usePipelineStore.getState().edges[0].data).toEqual({ dataType: 'documents' })
  })

  it('removes edges attached to a deleted node', () => {
    const store = usePipelineStore.getState()
    store.addNode(sourceDefinition, { x: 0, y: 0 })
    store.addNode(consumerDefinition, { x: 200, y: 0 })
    const [source, consumer] = usePipelineStore.getState().nodes
    usePipelineStore.getState().onConnect({
      source: source.id,
      sourceHandle: 'out_documents',
      target: consumer.id,
      targetHandle: 'in_documents',
    })

    usePipelineStore.setState({ selectedNodeId: source.id })
    usePipelineStore.getState().removeNode(source.id)
    expect(usePipelineStore.getState().nodes).toHaveLength(1)
    expect(usePipelineStore.getState().edges).toHaveLength(0)
    expect(usePipelineStore.getState().selectedNodeId).toBeNull()
  })

  it('undoes and redoes a node addition', () => {
    const store = usePipelineStore.getState()
    store.addNode(sourceDefinition, { x: 0, y: 0 })
    expect(usePipelineStore.getState().nodes).toHaveLength(1)

    usePipelineStore.getState().undo()
    expect(usePipelineStore.getState().nodes).toHaveLength(0)

    usePipelineStore.getState().redo()
    expect(usePipelineStore.getState().nodes).toHaveLength(1)
  })

  it('serializes positions and handles back into the pipeline model', () => {
    const store = usePipelineStore.getState()
    store.loadPipeline(pipeline)
    store.addNode(sourceDefinition, { x: 42, y: 84 })
    store.addNode(consumerDefinition, { x: 200, y: 84 })
    const [source, consumer] = usePipelineStore.getState().nodes
    usePipelineStore.getState().onConnect({
      source: source.id,
      sourceHandle: 'out_documents',
      target: consumer.id,
      targetHandle: 'in_documents',
    })

    const saved = usePipelineStore.getState().toPipeline()
    expect(saved).not.toBeNull()
    expect(saved?.nodes).toHaveLength(2)
    expect(saved?.nodes[0].position).toEqual({ x: 42, y: 84 })
    expect(saved?.edges[0]).toMatchObject({
      source: source.id,
      target: consumer.id,
      sourceHandle: 'out_documents',
      targetHandle: 'in_documents',
      dataType: 'documents',
    })
  })
})
