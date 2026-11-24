import * as React from 'react'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { NodeProps } from '@xyflow/react'
import type { PipelineNode } from '@/types'
import { RAGNode } from './RAGNode'
import { nodesApi } from '@/api/nodes.api'
import { usePipelineStore, type RagFlowNode } from '@/store/usePipelineStore'

vi.mock('@/api/nodes.api', () => ({ nodesApi: { test: vi.fn() } }))

vi.mock('@xyflow/react', () => ({
  Handle: () => null,
  Position: { Left: 'left', Right: 'right' },
}))

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const pipelineNode: PipelineNode = {
  id: 'n_delete_test',
  definitionId: 'document-source',
  name: 'Document source',
  category: 'Data Sources',
  kind: 'source',
  accent: '#2FC9C3',
  position: { x: 0, y: 0 },
  config: {},
  inputs: [],
  outputs: [],
}

describe('RAGNode delete control', () => {
  let container: HTMLDivElement
  let root: Root

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('removes the node directly without bubbling a click that would open the inspector', () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    const flowNode: RagFlowNode = {
      id: pipelineNode.id,
      type: 'rag',
      position: { x: 0, y: 0 },
      data: { pipelineNode },
    }
    act(() => {
      usePipelineStore.setState({ nodes: [flowNode], edges: [], selectedNodeId: pipelineNode.id, dirty: false })
    })

    const onParentClick = vi.fn()
    act(() => {
      root.render(
        React.createElement(
          'div',
          { onClick: onParentClick },
          React.createElement(RAGNode, {
            id: pipelineNode.id,
            data: flowNode.data,
            selected: true,
          } as unknown as NodeProps<RagFlowNode>),
        ),
      )
    })

    const button = container.querySelector<HTMLButtonElement>(`button[aria-label="Rimuovi nodo ${pipelineNode.name}"]`)
    expect(button).not.toBeNull()

    act(() => {
      button!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(usePipelineStore.getState().nodes).toHaveLength(0)
    expect(usePipelineStore.getState().edges).toHaveLength(0)
    expect(usePipelineStore.getState().selectedNodeId).toBeNull()
    expect(onParentClick).not.toHaveBeenCalled()
  })

  it('mostra il pulsante Test solo sui componenti remoti e chiama la API', async () => {
    const remoteNode: PipelineNode = {
      ...pipelineNode,
      id: 'n_test_remote',
      definitionId: 'provider-embeddings',
      name: 'Model embeddings',
      config: { provider: 'huggingface', model: 'BAAI/bge-small-en-v1.5' },
    }
    const flowNode: RagFlowNode = {
      id: remoteNode.id,
      type: 'rag',
      position: { x: 0, y: 0 },
      data: { pipelineNode: remoteNode },
    }
    act(() => {
      usePipelineStore.setState({ nodes: [flowNode], edges: [], selectedNodeId: remoteNode.id, dirty: false })
    })

    vi.mocked(nodesApi.test).mockResolvedValue({
      ok: true,
      detail: 'Embedding OK',
      category: 'model',
      latencyMs: 5,
      supported: true,
    })

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => {
      root.render(
        React.createElement(RAGNode, {
          id: remoteNode.id,
          data: flowNode.data,
          selected: true,
        } as unknown as NodeProps<RagFlowNode>),
      )
    })

    expect(container.querySelector(`button[aria-label="Test nodo ${remoteNode.name}"]`)).not.toBeNull()

    const button = container.querySelector<HTMLButtonElement>(`button[aria-label="Test nodo ${remoteNode.name}"]`)
    await act(async () => {
      button!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(nodesApi.test).toHaveBeenCalledWith({
      definitionId: 'provider-embeddings',
      config: remoteNode.config,
    })
  })
})
