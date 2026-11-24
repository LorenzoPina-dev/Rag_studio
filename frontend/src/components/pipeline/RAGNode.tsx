import { memo, useState } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { AlertCircle, Check, Loader2, X, Zap } from 'lucide-react'
import { toast } from 'sonner'
import { nodesApi } from '@/api/nodes.api'
import type { RagFlowNode } from '@/store/usePipelineStore'
import { usePipelineStore } from '@/store/usePipelineStore'
import { isNodeTestable } from '@/lib/nodeTest'
import { cn } from '@/lib/utils'

const dataTypeColor: Record<string, string> = {
  documents: '#39D6D0',
  chunks: '#A78BFA',
  embedding: '#7296FF',
  text: '#8AA0C0',
  json: '#F0B45C',
  query: '#5B7CFA',
  any: '#8C9AB2',
  array: '#E48EF0',
}

function displayValue(value: string | number | boolean) {
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

export const RAGNode = memo(({ data, selected, id }: NodeProps<RagFlowNode>) => {
  const node = data.pipelineNode
  const removeNode = usePipelineStore((s) => s.removeNode)
  const status = usePipelineStore((s) => s.nodeStatus[id])
  const running = status?.status === 'running'
  const completed = status?.status === 'completed'
  const failed = status?.status === 'failed'
  const [testing, setTesting] = useState(false)
  const testable = isNodeTestable(node.definitionId)

  const runTest = async () => {
    setTesting(true)
    try {
      const result = await nodesApi.test({ definitionId: node.definitionId, config: node.config })
      if (result.ok) toast.success(result.detail)
      else toast.error(result.detail)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Test non riuscito')
    } finally {
      setTesting(false)
    }
  }

  const fields = Object.entries(node.config).slice(0, 3)

  return (
    <div
      className={cn(
        'rag-node relative w-[178px] rounded-[6px] border bg-[#0a121c] text-left transition-shadow',
        selected ? 'border-[#6080fa]' : 'border-[#243149]',
        running && 'border-accent/70 shadow-[0_0_0_1px_rgba(91,124,250,0.25),0_0_30px_rgba(91,124,250,0.16)]',
      )}
      style={{ borderTopColor: node.accent, borderTopWidth: 2 }}
    >
      {testable && (
        <button
          type="button"
          title={`Test preventivo di ${node.name}`}
          aria-label={`Test nodo ${node.name}`}
          className="nodrag nopan absolute -left-2 -top-2 z-10 flex h-[18px] w-[18px] items-center justify-center rounded-full border border-[#3a4a66] bg-[#0b121c] text-[#9fb0c8] shadow-[0_2px_10px_rgba(0,0,0,0.45)] transition-colors hover:border-accent hover:text-accent disabled:opacity-60"
          onPointerDown={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation()
            void runTest()
          }}
          disabled={testing}
        >
          {testing ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <Zap className="h-2.5 w-2.5" />}
        </button>
      )}
      <button
        type="button"
        title="Rimuovi nodo"
        aria-label={`Rimuovi nodo ${node.name}`}
        className="nodrag nopan absolute -right-2 -top-2 z-10 flex h-[18px] w-[18px] items-center justify-center rounded-full border border-[#3a4a66] bg-[#0b121c] text-[#9fb0c8] shadow-[0_2px_10px_rgba(0,0,0,0.45)] transition-colors hover:border-danger hover:text-danger"
        onPointerDown={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation()
          removeNode(id)
          toast.success('Node removed')
        }}
      >
        <X className="h-2.5 w-2.5" strokeWidth={2.4} />
      </button>
      {node.inputs.map((input, index) => (
        <Handle
          key={input.id}
          id={input.id}
          type="target"
          position={Position.Left}
          title={`${input.label} · ${input.typeLabel ?? input.dataType}`}
          style={{ top: `${38 + index * 18}%`, background: dataTypeColor[input.dataType] }}
        />
      ))}
      {node.outputs.map((output, index) => (
        <Handle
          key={output.id}
          id={output.id}
          type="source"
          position={Position.Right}
          title={`${output.label} · ${output.typeLabel ?? output.dataType}`}
          style={{ top: `${38 + index * 18}%`, background: dataTypeColor[output.dataType] }}
        />
      ))}

      <div className="px-2.5 pb-2 pt-2">
        <div className="flex items-start justify-between gap-1.5">
          <h3 className="text-[11px] font-medium leading-[1.25] tracking-[-0.01em] text-ink">{node.name}</h3>
          {running && <Loader2 className="mt-0.5 h-3 w-3 shrink-0 animate-spin text-accent" />}
          {completed && <Check className="mt-0.5 h-3 w-3 shrink-0 text-success" strokeWidth={2.6} />}
          {failed && <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-danger" />}
        </div>
        <p className="mt-1 font-mono text-[7.5px] uppercase tracking-[0.12em]" style={{ color: node.accent }}>
          {node.category}
        </p>
      </div>

      <div className="border-t border-[#1b2637]">
        {fields.map(([key, value], index) => (
          <div
            key={key}
            className={cn('flex items-center justify-between gap-2 px-2.5 py-[5px]', index < fields.length - 1 && 'border-b border-[#182233]')}
          >
            <span className="min-w-0 truncate font-mono text-[8px] text-[#78859a]">{key}</span>
            <span
              className={cn(
                'max-w-[92px] shrink-0 truncate font-mono text-[8px]',
                typeof value === 'boolean' ? (value ? 'text-success' : 'text-dim') : 'text-[#c2ccdb]',
                running && 'animate-pulse',
              )}
            >
              {displayValue(value)}
            </span>
          </div>
        ))}
      </div>

      <div className="absolute bottom-1.5 right-2 flex items-center gap-1">
        {status?.durationMs !== undefined && status.durationMs > 0 && (
          <span className="font-mono text-[7px] text-[#59677e]">{status.durationMs}ms</span>
        )}
        <span
          className="h-2.5 w-2.5 rounded-[2px] border"
          style={{ borderColor: `${node.accent}55`, background: `${node.accent}12` }}
        />
      </div>
    </div>
  )
})

RAGNode.displayName = 'RAGNode'
