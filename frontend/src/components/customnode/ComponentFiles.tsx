import * as React from 'react'
import { Braces, ChevronDown, ChevronRight, Copy, FileCode2, FilePlus2, FlaskConical, Package, Plus, Trash2, Boxes } from 'lucide-react'
import type { CustomNode, CustomNodeFile } from '@/types'
import { cn } from '@/lib/utils'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown'

const templates = [
  { id: 'ranking', name: 'Ranking algorithm', description: 'Reorder candidates with a custom scoring function.', icon: FileCode2 },
  { id: 'reward', name: 'Reward function', description: 'Score documents against a learned objective.', icon: FlaskConical },
  { id: 'selection', name: 'Selection strategy', description: 'Choose context under a token budget.', icon: Boxes },
  { id: 'transform', name: 'Document transform', description: 'Normalize or enrich documents before indexing.', icon: Braces },
]

function FileIcon({ file }: { file: CustomNodeFile }) {
  if (file.language === 'python') return <FileCode2 className="h-3.5 w-3.5 text-[#7C9BFF]" />
  if (file.language === 'yaml') return <Braces className="h-3.5 w-3.5 text-[#E5B56B]" />
  if (file.name.includes('test')) return <FlaskConical className="h-3.5 w-3.5 text-[#6FD3B0]" />
  return <Package className="h-3.5 w-3.5 text-[#8E9CB2]" />
}

export function ComponentFiles({
  node,
  activeFileId,
  onSelectFile,
  onAddFile,
  onDuplicateFile,
  onDeleteFile,
  onUseTemplate,
  onVersionHistory,
}: {
  node: CustomNode
  activeFileId: string | null
  onSelectFile: (file: CustomNodeFile) => void
  onAddFile: () => void
  onDuplicateFile: (file: CustomNodeFile) => void
  onDeleteFile: (file: CustomNodeFile) => void
  onUseTemplate: (templateId: string) => void
  onVersionHistory: () => void
}) {
  const [folderOpen, setFolderOpen] = React.useState(true)
  const [templatesOpen, setTemplatesOpen] = React.useState(true)

  return (
    <aside className="flex h-full w-[204px] shrink-0 flex-col border-r border-line bg-[#0b111b]">
      <div className="flex h-[34px] items-center justify-between border-b border-line px-3">
        <span className="font-mono text-[8.5px] font-medium uppercase tracking-[0.12em] text-[#7f8da2]">Component Files</span>
        <button onClick={onAddFile} className="rounded p-0.5 text-dim hover:bg-white/5 hover:text-ink" aria-label="Add component file">
          <FilePlus2 className="h-3 w-3" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto py-1.5">
        <button onClick={() => setFolderOpen((v) => !v)} className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left">
          {folderOpen ? <ChevronDown className="h-2.5 w-2.5 text-[#58657a]" /> : <ChevronRight className="h-2.5 w-2.5 text-[#58657a]" />}
          <span className="truncate font-mono text-[10px] text-[#9aa7ba]">{node.slug}</span>
        </button>
        {folderOpen && (
          <div className="space-y-0.5 px-1.5">
            {node.files.map((file) => (
              <div
                key={file.id}
                className={cn(
                  'group flex items-center gap-2 rounded-[4px] px-2 py-[5px] transition-colors',
                  activeFileId === file.id ? 'bg-[#17233a] text-[#c8d4ff]' : 'text-[#8f9db1] hover:bg-white/[0.03] hover:text-ink',
                )}
              >
                <button onClick={() => onSelectFile(file)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                  <FileIcon file={file} />
                  <span className="truncate font-mono text-[10px]">{file.name}</span>
                  {file.dirty && <span className="ml-auto h-1 w-1 shrink-0 rounded-full bg-warn" />}
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="rounded p-0.5 text-dim opacity-0 hover:bg-white/5 hover:text-ink group-hover:opacity-100" aria-label={`Actions for ${file.name}`}>
                      <ChevronDown className="h-2.5 w-2.5" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-40">
                    <DropdownMenuItem icon={<Copy className="h-3.5 w-3.5" />} onSelect={() => onDuplicateFile(file)}>Duplicate</DropdownMenuItem>
                    <DropdownMenuItem icon={<FilePlus2 className="h-3.5 w-3.5" />} onSelect={onAddFile}>New file</DropdownMenuItem>
                    <DropdownMenuItem danger icon={<Trash2 className="h-3.5 w-3.5" />} onSelect={() => onDeleteFile(file)}>Delete</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        )}

        <div className="mx-2 my-2 h-px bg-line/60" />
        <button onClick={() => setTemplatesOpen((v) => !v)} className="flex w-full items-center gap-1.5 px-2 py-1.5">
          {templatesOpen ? <ChevronDown className="h-2.5 w-2.5 text-[#58657a]" /> : <ChevronRight className="h-2.5 w-2.5 text-[#58657a]" />}
          <span className="font-mono text-[8.5px] uppercase tracking-[0.1em] text-[#69778c]">Node Templates</span>
        </button>
        {templatesOpen && (
          <div className="space-y-0.5 px-1.5">
            {templates.map((template) => (
              <button
                key={template.id}
                onClick={() => onUseTemplate(template.id)}
                className="flex w-full items-start gap-2 rounded px-2 py-1.5 text-left text-[#8a98ad] transition-colors hover:bg-white/[0.03] hover:text-ink"
                title={template.description}
              >
                <template.icon className="mt-0.5 h-3 w-3 shrink-0 text-[#637189]" />
                <span className="text-[9.5px] leading-tight">{template.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={onVersionHistory}
        className="m-2 shrink-0 rounded-md border border-line bg-[#0e1622] px-2.5 py-2 text-left transition-colors hover:border-line-strong"
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-[9.5px] text-[#bcc8d8]">{node.draftVersion}</span>
          <span className="rounded border border-[#34445a] bg-white/[0.03] px-1 py-0.5 font-mono text-[7.5px] uppercase tracking-wider text-[#9ca9bb]">Draft</span>
        </div>
        <p className="mt-1 font-mono text-[8px] text-dim">Based on {node.basedOn}</p>
        <p className="mt-1 font-mono text-[8px] text-[#546177]">Edited just now</p>
      </button>
    </aside>
  )
}
