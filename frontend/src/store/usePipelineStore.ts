import { create } from 'zustand'
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import type { NodeDefinition, Pipeline, PipelineNode, PipelineEdge, ValidationResult } from '@/types'
import { connectionIsCompatible } from '@/lib/portCompatibility'

export type RagFlowNode = Node<{ pipelineNode: PipelineNode }, 'rag'>

interface Snapshot {
  nodes: RagFlowNode[]
  edges: Edge[]
}

interface PipelineEditorState {
  pipeline: Pipeline | null
  nodes: RagFlowNode[]
  edges: Edge[]
  selectedNodeId: string | null
  dirty: boolean
  history: Snapshot[]
  future: Snapshot[]
  validation: ValidationResult | null
  validating: boolean
  inspectorTab: 'params' | 'io' | 'docs'
  libraryTab: 'all' | 'favorites'
  librarySearch: string
  favorites: string[]
  nodeStatus: Record<string, { status: PipelineNode['status']; durationMs?: number }>
  loadPipeline: (pipeline: Pipeline) => void
  setNodes: (nodes: RagFlowNode[]) => void
  setEdges: (edges: Edge[]) => void
  onNodesChange: (changes: NodeChange<RagFlowNode>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  addNode: (definition: NodeDefinition, position: { x: number; y: number }) => void
  removeNode: (id: string) => void
  removeEdges: (ids: string[]) => void
  duplicateNode: (id: string) => void
  updateNodeConfig: (id: string, key: string, value: string | number | boolean) => void
  updateNodeName: (id: string, name: string) => void
  selectNode: (id: string | null) => void
  setInspectorTab: (tab: PipelineEditorState['inspectorTab']) => void
  setLibraryTab: (tab: PipelineEditorState['libraryTab']) => void
  setLibrarySearch: (search: string) => void
  toggleFavorite: (id: string) => void
  undo: () => void
  redo: () => void
  pushHistory: () => void
  markSaved: (pipeline: Pipeline) => void
  setEnvironment: (environment: Pipeline['environment']) => void
  setLastRun: (lastRun: Pipeline['lastRun']) => void
  setValidation: (validation: ValidationResult | null) => void
  setValidating: (validating: boolean) => void
  setNodeStatus: (statuses: Record<string, { status: PipelineNode['status']; durationMs?: number }>) => void
  clearNodeStatus: () => void
  toPipeline: () => Pipeline | null
  reset: () => void
}

const toFlowNode = (node: PipelineNode): RagFlowNode => ({
  id: node.id,
  type: 'rag',
  position: node.position,
  data: { pipelineNode: node },
  selected: false,
})

export const toFlowEdge = (edge: PipelineEdge): Edge => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
  sourceHandle: edge.sourceHandle ?? undefined,
  targetHandle: edge.targetHandle ?? undefined,
  type: 'rag',
  data: { dataType: edge.dataType },
  animated: false,
})

function cloneSnapshot(state: { nodes: RagFlowNode[]; edges: Edge[] }): Snapshot {
  return {
    nodes: JSON.parse(JSON.stringify(state.nodes)),
    edges: JSON.parse(JSON.stringify(state.edges)),
  }
}

export const usePipelineStore = create<PipelineEditorState>((set, get) => ({
  pipeline: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  dirty: false,
  history: [],
  future: [],
  validation: null,
  validating: false,
  inspectorTab: 'params',
  libraryTab: 'all',
  librarySearch: '',
  favorites: ['semantic-chunking', 'hybrid-retrieval', 'bge-reranker'],
  nodeStatus: {},

  loadPipeline: (pipeline) => {
    set({
      pipeline,
      nodes: pipeline.nodes.map(toFlowNode),
      edges: pipeline.edges.map(toFlowEdge),
      selectedNodeId: pipeline.nodes.find((n) => n.definitionId === 'semantic-chunking')?.id ?? null,
      dirty: false,
      history: [],
      future: [],
      validation: null,
      nodeStatus: {},
    })
  },

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    const meaningful = changes.some((c) => c.type === 'position' || c.type === 'remove' || c.type === 'add' || c.type === 'replace')
    if (meaningful) get().pushHistory()
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
      dirty: state.dirty || meaningful,
    }))
    const removal = changes.find((c) => c.type === 'remove')
    if (removal && 'id' in removal) {
      set({ selectedNodeId: get().selectedNodeId === removal.id ? null : get().selectedNodeId })
    }
  },

  onEdgesChange: (changes) => {
    if (changes.some((c) => c.type === 'remove' || c.type === 'add')) get().pushHistory()
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      dirty: state.dirty || changes.some((c) => c.type === 'remove'),
    }))
  },

  onConnect: (connection) => {
    if (!connection.source || !connection.target) return
    const state = get()
    const connectableNodes = state.nodes.map((n) => ({
      id: n.id,
      inputs: n.data.pipelineNode.inputs,
      outputs: n.data.pipelineNode.outputs,
    }))
    if (!connectionIsCompatible(connection, connectableNodes)) return
    get().pushHistory()
    const sourceNode = state.nodes.find((n) => n.id === connection.source)?.data.pipelineNode
    const output = sourceNode?.outputs.find((o) => o.id === connection.sourceHandle) ?? sourceNode?.outputs[0]
    const edge: Edge = {
      id: `e_${Date.now()}`,
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle ?? undefined,
      targetHandle: connection.targetHandle ?? undefined,
      type: 'rag',
      data: { dataType: output?.dataType ?? 'any' },
    }
    set({
      edges: addEdge(edge, state.edges),
      dirty: true,
      validation: null,
    })
  },

  addNode: (definition, position) => {
    get().pushHistory()
    const id = `n_${Math.random().toString(36).slice(2, 9)}`
    // Use the catalog definition (real backend or mock), never the hardcoded seed:
    // ids and port names must match the node the runtime will actually execute.
    const node: PipelineNode = {
      id,
      definitionId: definition.id,
      name: definition.name,
      category: definition.category,
      kind: definition.kind,
      accent: definition.accent,
      position,
      config: Object.fromEntries(definition.params.map((param) => [param.key, param.defaultValue])),
      inputs: definition.inputs,
      outputs: definition.outputs,
    }
    const flowNode: RagFlowNode = {
      id,
      type: 'rag',
      position,
      selected: true,
      data: { pipelineNode: node },
    }
    set((state) => ({
      nodes: [...state.nodes.map((n) => ({ ...n, selected: false })), flowNode],
      selectedNodeId: id,
      dirty: true,
      validation: null,
    }))
  },

  removeNode: (id) => {
    get().pushHistory()
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
      dirty: true,
    }))
  },

  removeEdges: (ids) => {
    if (ids.length === 0) return
    const remove = new Set(ids)
    get().pushHistory()
    set((state) => ({
      edges: state.edges.filter((e) => !remove.has(e.id)),
      dirty: true,
      validation: null,
    }))
  },

  duplicateNode: (id) => {
    const state = get()
    const source = state.nodes.find((n) => n.id === id)
    if (!source) return
    get().pushHistory()
    const newId = `n_${Math.random().toString(36).slice(2, 9)}`
    const copy: RagFlowNode = {
      ...JSON.parse(JSON.stringify(source)),
      id: newId,
      position: { x: source.position.x + 28, y: source.position.y + 28 },
      selected: true,
      data: { pipelineNode: { ...source.data.pipelineNode, id: newId, position: { x: source.position.x + 28, y: source.position.y + 28 } } },
    }
    set({
      nodes: [...state.nodes.map((n) => ({ ...n, selected: false })), copy],
      selectedNodeId: newId,
      dirty: true,
    })
  },

  updateNodeConfig: (id, key, value) => {
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === id
          ? {
              ...n,
              data: {
                pipelineNode: { ...n.data.pipelineNode, config: { ...n.data.pipelineNode.config, [key]: value } },
              },
            }
          : n,
      ),
      dirty: true,
      validation: null,
    }))
  },

  updateNodeName: (id, name) => {
    set((state) => ({
      nodes: state.nodes.map((n) => (n.id === id ? { ...n, data: { pipelineNode: { ...n.data.pipelineNode, name } } } : n)),
      dirty: true,
    }))
  },

  selectNode: (id) => {
    set((state) => ({
      selectedNodeId: id,
      nodes: state.nodes.map((n) => ({ ...n, selected: n.id === id })),
    }))
  },

  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  setLibraryTab: (tab) => set({ libraryTab: tab }),
  setLibrarySearch: (search) => set({ librarySearch: search }),
  toggleFavorite: (id) =>
    set((state) => ({
      favorites: state.favorites.includes(id) ? state.favorites.filter((f) => f !== id) : [...state.favorites, id],
    })),

  pushHistory: () => {
    const state = get()
    set({
      history: [...state.history.slice(-30), cloneSnapshot(state)],
      future: [],
    })
  },

  undo: () => {
    const state = get()
    const previous = state.history[state.history.length - 1]
    if (!previous) return
    set({
      history: state.history.slice(0, -1),
      future: [cloneSnapshot(state), ...state.future.slice(0, 30)],
      nodes: previous.nodes,
      edges: previous.edges,
      dirty: true,
    })
  },

  redo: () => {
    const state = get()
    const next = state.future[0]
    if (!next) return
    set({
      history: [...state.history, cloneSnapshot(state)],
      future: state.future.slice(1),
      nodes: next.nodes,
      edges: next.edges,
      dirty: true,
    })
  },

  markSaved: (pipeline) => set({ pipeline, dirty: false, validation: null }),
  setEnvironment: (environment) =>
    set((state) => ({
      pipeline: state.pipeline ? { ...state.pipeline, environment } : state.pipeline,
      dirty: true,
    })),
  setLastRun: (lastRun) =>
    set((state) => ({
      pipeline: state.pipeline ? { ...state.pipeline, lastRun, status: lastRun?.status === 'failed' ? 'failed' : 'valid' } : state.pipeline,
    })),
  setValidation: (validation) => set({ validation }),
  setValidating: (validating) => set({ validating }),
  setNodeStatus: (nodeStatus) => set({ nodeStatus }),
  clearNodeStatus: () => set({ nodeStatus: {} }),

  toPipeline: () => {
    const state = get()
    if (!state.pipeline) return null
    const nodes: PipelineNode[] = state.nodes.map((node) => ({
      ...node.data.pipelineNode,
      position: node.position,
      id: node.id,
    }))
    const edges: PipelineEdge[] = state.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? null,
      targetHandle: edge.targetHandle ?? null,
      dataType: (edge.data as { dataType?: PipelineEdge['dataType'] } | undefined)?.dataType,
    }))
    return { ...state.pipeline, nodes, edges, updatedAt: new Date().toISOString(), status: state.validation?.valid === false ? 'draft' : state.pipeline.status }
  },

  reset: () =>
    set({
      pipeline: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      dirty: false,
      history: [],
      future: [],
      validation: null,
      nodeStatus: {},
    }),
}))
