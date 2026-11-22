import * as React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  ChevronDown,
  FileCode2,
  FlaskConical,
  History,
  Loader2,
  Play,
  Plus,
  Save,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { customNodesApi } from '@/api/customNodes.api'
import { nodesApi } from '@/api/nodes.api'
import type { CustomNode, CustomNodeFile, CustomNodeTestOutput, CustomNodeVersion, TestRun } from '@/types'
import { createCustomNodeFromDefinition, customNodeIdFromDefinitionId } from '@/lib/customNodeFromDefinition'
import { useAppStore } from '@/store/useAppStore'
import { Breadcrumbs } from '@/components/shared/page'
import { Button } from '@/components/ui/button'
import { StatusDot, ErrorState } from '@/components/ui/badge'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { ComponentFiles } from '@/components/customnode/ComponentFiles'
import { CodeEditor } from '@/components/customnode/CodeEditor'
import { TestConsole } from '@/components/customnode/TestConsole'
import { ComponentConfig, type ConfigTab } from '@/components/customnode/ComponentConfig'
import { TestNodeDialog, VersionHistoryDialog } from '@/components/customnode/VersionHistory'
import { cn } from '@/lib/utils'

const templateContent: Record<string, { name: string; content: string; language: 'python' | 'yaml' | 'text' }> = {
  ranking: {
    name: 'ranking_node.py',
    language: 'python',
    content: `from typing import List\nfrom rag_studio import CustomNode, Document\n\n\nclass CustomRanker(CustomNode):\n    """Score and reorder candidate documents."""\n\n    name = "Custom ranker"\n    category = "Selection"\n\n    def execute(self, documents: List[Document]) -> List[Document]:\n        return sorted(\n            documents,\n            key=lambda doc: doc.relevance_score,\n            reverse=True,\n        )\n`,
  },
  reward: {
    name: 'reward_node.py',
    language: 'python',
    content: `from rag_studio import CustomNode, Document\n\n\nclass RewardModel(CustomNode):\n    """Score documents against a learned reward objective."""\n\n    name = "Reward function"\n    category = "Selection"\n\n    def execute(self, documents: list[Document]) -> list[float]:\n        return [self.score(doc) for doc in documents]\n\n    def score(self, doc: Document) -> float:\n        return 0.6 * doc.relevance_score + 0.4 * doc.freshness\n`,
  },
  selection: {
    name: 'selection_node.py',
    language: 'python',
    content: `from rag_studio import CustomNode, Document\n\n\nclass BudgetSelector(CustomNode):\n    """Select the best context that fits a token budget."""\n\n    name = "Budget selector"\n    category = "Selection"\n\n    def execute(self, documents: list[Document], budget: int = 2048) -> list[Document]:\n        selected, used = [], 0\n        for doc in sorted(documents, key=lambda d: d.relevance_score, reverse=True):\n            if used + doc.token_count > budget:\n                continue\n            selected.append(doc)\n            used += doc.token_count\n        return selected\n`,
  },
  transform: {
    name: 'transform_node.py',
    language: 'python',
    content: `from rag_studio import CustomNode, Document\n\n\nclass DocumentTransform(CustomNode):\n    """Normalize content before indexing."""\n\n    name = "Document transform"\n    category = "Document Processing"\n\n    def execute(self, documents: list[Document]) -> list[Document]:\n        for doc in documents:\n            doc.content = " ".join(doc.content.split())\n        return documents\n`,
  },
}

const initialFileTabOrder = ['f_py', 'f_yaml']

export function CustomNodePage() {
  const queryClient = useQueryClient()
  const pushNotification = useAppStore((s) => s.pushNotification)
  const [searchParams] = useSearchParams()
  const fromId = searchParams.get('from')
  const derivedId = fromId ? customNodeIdFromDefinitionId(fromId) : 'cn_diversity'
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({ queryKey: ['custom-node', derivedId], queryFn: () => customNodesApi.get(derivedId), enabled: !fromId })
  const { data: initialTests } = useQuery({
    queryKey: ['custom-node-tests', derivedId],
    queryFn: () => customNodesApi.testResults(derivedId),
    enabled: !fromId,
  })
  const sourceDefinitionQuery = useQuery({
    queryKey: ['nodes'],
    queryFn: nodesApi.list,
    enabled: Boolean(fromId),
    staleTime: 300_000,
  })
  const sourceImplementationQuery = useQuery({
    queryKey: ['node-implementation', fromId],
    queryFn: () => nodesApi.implementation(fromId ?? ''),
    enabled: Boolean(fromId),
  })

  const [node, setNode] = React.useState<CustomNode | null>(null)
  const [dirty, setDirty] = React.useState(false)
  const [activeFileId, setActiveFileId] = React.useState<string | null>(null)
  const [openTabs, setOpenTabs] = React.useState<string[]>(initialFileTabOrder)
  const [configTab, setConfigTab] = React.useState<ConfigTab>('configuration')
  const [testRun, setTestRun] = React.useState<TestRun | null>(null)
  const [testRunning, setTestRunning] = React.useState(false)
  const [versionOpen, setVersionOpen] = React.useState(false)
  const [testOpen, setTestOpen] = React.useState(false)
  const [testOutput, setTestOutput] = React.useState<CustomNodeTestOutput | null>(null)
  const [testOutputRunning, setTestOutputRunning] = React.useState(false)
  const [addFileOpen, setAddFileOpen] = React.useState(false)
  const [newFileName, setNewFileName] = React.useState('')
  const [newFileLanguage, setNewFileLanguage] = React.useState<'python' | 'yaml' | 'text'>('python')
  const [versions, setVersions] = React.useState<CustomNodeVersion[]>([])
  const [publishedStatus, setPublishedStatus] = React.useState<string | null>(null)
  const snapshots = React.useRef<Record<string, CustomNodeFile[]>>({})
  const loadedRef = React.useRef(false)
  const createdRef = React.useRef(!fromId)

  React.useEffect(() => {
    if (!fromId && data && !loadedRef.current) {
      setNode(data)
      setVersions(data.versions)
      setActiveFileId(data.files[0]?.id ?? null)
      setOpenTabs(data.files.slice(0, 2).map((file) => file.id))
      loadedRef.current = true
    }
  }, [data, fromId])

  React.useEffect(() => {
    if (!fromId || !sourceDefinitionQuery.data || !sourceImplementationQuery.data || loadedRef.current) return
    const definition = sourceDefinitionQuery.data.find((item) => item.id === fromId)
    if (!definition) return
    const draft = createCustomNodeFromDefinition(definition, sourceImplementationQuery.data)
    setNode(draft)
    setVersions(draft.versions)
    setActiveFileId(draft.files[0]?.id ?? null)
    setOpenTabs(draft.files.slice(0, 2).map((file) => file.id))
    loadedRef.current = true
  }, [fromId, sourceDefinitionQuery.data, sourceImplementationQuery.data])

  React.useEffect(() => {
    if (initialTests) setTestRun(initialTests)
  }, [initialTests])

  const saveMutation = useMutation({
    mutationFn: (payload: CustomNode) =>
      fromId && !createdRef.current
        ? customNodesApi.create(payload)
        : customNodesApi.update(payload.id, payload),
    onSuccess: (saved) => {
      createdRef.current = true
      setNode((current) => (current ? { ...current, ...saved } : saved))
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ['custom-node', derivedId] })
      if (node) snapshots.current[node.draftVersion] = JSON.parse(JSON.stringify(node.files))
      toast.success('Component saved', { description: `${node?.draftVersion} draft updated with ${node?.files.length} files.` })
    },
    onError: (err: Error) => toast.error('Save failed', { description: err.message }),
  })

  const runTestsMutation = useMutation({
    mutationFn: () => customNodesApi.runTests(derivedId),
    onMutate: () => setTestRunning(true),
    onSuccess: (result) => {
      setTestRun(result)
      toast.success('Tests passed', { description: result.summary + ' · node is ready to use.' })
    },
    onError: (err: Error) => toast.error('Tests failed', { description: err.message }),
    onSettled: () => setTestRunning(false),
  })

  const testMutation = useMutation({
    mutationFn: () => customNodesApi.test(derivedId),
    onMutate: () => setTestOutputRunning(true),
    onSuccess: (result) => {
      setTestOutput(result)
      toast.success('Component executed', { description: `${result.documents.length} documents ranked in ${result.durationMs}ms.` })
    },
    onError: (err: Error) => toast.error('Test failed', { description: err.message }),
    onSettled: () => setTestOutputRunning(false),
  })

  const publishMutation = useMutation({
    mutationFn: () => customNodesApi.publish(derivedId),
    onSuccess: (result) => {
      setVersionOpen(false)
      setDirty(false)
      setPublishedStatus(result.status)
      const versionLabel = result.version || node?.draftVersion || 'versione non disponibile'
      // Il backend restituisce id/versione/stato: data e autore non inventati se assenti.
      const published: CustomNodeVersion = {
        id: result.id,
        version: versionLabel,
        label: 'Published',
        date: '',
        author: '',
        changes: `Pubblicazione confermata dal backend (${result.status}).`,
      }
      setVersions((current) => [{ ...published, current: true }, ...current.map((v) => ({ ...v, current: false }))])
      pushNotification({ title: 'Custom node published', body: `${node?.name ?? ''} · ${versionLabel}`, type: 'success' })
      toast.success('Component published', { description: `${versionLabel} · ${result.status}` })
    },
    onError: (err: Error) => toast.error('Publish failed', { description: err.message }),
  })

  const sourceLoading = Boolean(fromId) && (sourceDefinitionQuery.isLoading || sourceImplementationQuery.isLoading)
  const activeError = fromId
    ? sourceImplementationQuery.error ?? sourceDefinitionQuery.error
    : error
  const activeRefetch = fromId ? sourceImplementationQuery.refetch : refetch
  const sourceMissing = Boolean(fromId) && sourceDefinitionQuery.data
    && !sourceDefinitionQuery.data.some((item) => item.id === fromId)

  if (sourceMissing) {
    return <div className="p-6"><ErrorState message={`Source block “${fromId}” was not found.`} onRetry={() => void activeRefetch()} /></div>
  }

  if (isLoading || sourceLoading || !node) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim">Loading component</p>
        </div>
      </div>
    )
  }

  if (isError || activeError) {
    return <div className="p-6"><ErrorState message={(activeError as Error)?.message} onRetry={() => void activeRefetch()} /></div>
  }

  const activeFile = node.files.find((f) => f.id === activeFileId) ?? node.files[0]
  const engineLabel = activeFile?.language === 'python' ? 'Python' : activeFile?.language === 'yaml' ? 'YAML' : 'Plain text'

  const updateNode = (patch: Partial<CustomNode>) => {
    setNode((current) => (current ? { ...current, ...patch } : current))
    setDirty(true)
  }

  const updateFileContent = (content: string) => {
    if (!activeFile) return
    updateNode({
      files: node.files.map((f) => (f.id === activeFile.id ? { ...f, content, dirty: true } : f)),
    })
  }

  const openFile = (file: CustomNodeFile) => {
    setActiveFileId(file.id)
    setOpenTabs((tabs) => (tabs.includes(file.id) ? tabs : [...tabs, file.id]))
  }

  const closeTab = (fileId: string) => {
    setOpenTabs((tabs) => {
      const next = tabs.filter((id) => id !== fileId)
      if (activeFileId === fileId && next.length > 0) setActiveFileId(next[next.length - 1])
      return next
    })
  }

  const duplicateFile = (file: CustomNodeFile) => {
    const copy: CustomNodeFile = {
      ...file,
      id: `f_${Date.now()}`,
      name: file.name.replace(/(\.[^.]+)$/, (ext) => `_copy${ext}`),
      dirty: true,
    }
    updateNode({ files: [...node.files, copy] })
    openFile(copy)
    toast.success('File duplicated')
  }

  const deleteFile = (file: CustomNodeFile) => {
    if (node.files.length <= 1) {
      toast.error('A component needs at least one file')
      return
    }
    const nextFiles = node.files.filter((f) => f.id !== file.id)
    updateNode({ files: nextFiles })
    setOpenTabs((tabs) => tabs.filter((id) => id !== file.id))
    if (activeFileId === file.id) setActiveFileId(nextFiles[0]?.id ?? null)
    toast.success(`${file.name} deleted`, {
      action: {
        label: 'Undo',
        onClick: () => {
          updateNode({ files: [...node.files] })
          setOpenTabs((tabs) => [...tabs, file.id])
        },
      },
    })
  }

  const addDependency = (name: string, version: string) => {
    updateNode({ dependencies: [...node.dependencies, { name, version, installed: true }] })
    toast.success(`${name} added`, { description: 'Dependency resolved in the isolated runtime.' })
  }

  const removeDependency = (name: string) => {
    updateNode({ dependencies: node.dependencies.filter((d) => d.name !== name) })
    toast.success(`${name} removed`)
  }

  const handleRestore = (version: CustomNodeVersion) => {
    const snapshot = snapshots.current[version.version]
    updateNode({
      basedOn: version.version,
      draftVersion: node.draftVersion,
      files: snapshot ? snapshot.map((f) => ({ ...f, dirty: true })) : node.files,
    })
    if (snapshot && snapshot[0]) {
      setActiveFileId(snapshot[0].id)
      setOpenTabs(snapshot.slice(0, 2).map((f) => f.id))
    }
  }

  const handleUseTemplate = (templateId: string) => {
    const template = templateContent[templateId]
    if (!template) return
    const file: CustomNodeFile = {
      id: `f_${Date.now()}`,
      name: template.name,
      language: template.language,
      content: template.content,
      dirty: true,
    }
    updateNode({ files: [...node.files, file] })
    openFile(file)
    toast.success('Template loaded', { description: `${file.name} added to the component.` })
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      <header className="shrink-0 border-b border-line/80 px-4 pb-2.5 pt-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Breadcrumbs items={[{ label: 'Custom nodes', to: '/custom-nodes' }, { label: node.category }]} />
            <div className="mt-1.5 flex flex-wrap items-center gap-3">
              <h1 className="text-[20px] font-semibold leading-none tracking-[-0.02em] text-ink">{node.name}</h1>
              <span className="flex items-center gap-1.5 font-mono text-[9px] text-dim">
                <StatusDot status={dirty ? 'warning' : 'success'} />
                {dirty ? 'Unsaved changes' : `${node.draftVersion} · Draft`}
              </span>
              {publishedStatus && (
                <span className="flex items-center gap-1.5 font-mono text-[9px] text-dim">
                  <StatusDot status="success" /> Pubblicato · {publishedStatus}
                </span>
              )}
            </div>
            <p className="mt-1.5 text-[10.5px] text-muted">{node.description}</p>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Button variant="secondary" size="sm" onClick={() => setVersionOpen(true)}>
              <History className="h-3 w-3" /> Version history
            </Button>
            <Button variant="secondary" size="sm" onClick={() => saveMutation.mutate(node)} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
            </Button>
            <Button variant="primary" size="sm" onClick={() => setTestOpen(true)}>
              <Play className="h-3 w-3 fill-white" /> Test node
            </Button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <ComponentFiles
          node={node}
          activeFileId={activeFile?.id ?? null}
          onSelectFile={openFile}
          onAddFile={() => setAddFileOpen(true)}
          onDuplicateFile={duplicateFile}
          onDeleteFile={deleteFile}
          onUseTemplate={handleUseTemplate}
          onVersionHistory={() => setVersionOpen(true)}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-[34px] shrink-0 items-stretch border-b border-line bg-[#0b111b]">
            <div className="flex min-w-0 flex-1 items-stretch overflow-x-auto no-scrollbar">
              {openTabs.map((tabId) => {
                const file = node.files.find((f) => f.id === tabId)
                if (!file) return null
                const active = activeFileId === file.id
                return (
                  <div
                    key={file.id}
                    className={cn(
                      'group flex min-w-[120px] max-w-[210px] items-center gap-2 border-r border-line px-3 text-[10.5px] transition-colors',
                      active ? 'bg-[#0a111c] text-[#d2dbe8]' : 'bg-[#0b111b] text-[#7f8da2] hover:bg-[#0d1520]',
                    )}
                  >
                    {file.language === 'python' ? <FileCode2 className="h-3 w-3 shrink-0 text-[#7C9BFF]" /> : <FlaskConical className="h-3 w-3 shrink-0 text-[#E5B56B]" />}
                    <button onClick={() => setActiveFileId(file.id)} className="min-w-0 flex-1 truncate text-left font-mono">
                      {file.name}
                    </button>
                    {file.dirty && <span className="h-1 w-1 shrink-0 rounded-full bg-[#c9a26b]" />}
                    <button onClick={() => closeTab(file.id)} className="shrink-0 rounded p-0.5 text-dim opacity-0 transition-opacity hover:bg-white/5 hover:text-ink group-hover:opacity-100" aria-label={`Close ${file.name}`}>
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </div>
                )
              })}
            </div>
            <div className="flex shrink-0 items-center gap-4 border-l border-line px-3 font-mono text-[8.5px] text-[#66748a]">
              <span>{engineLabel}</span>
              <span>UTF-8</span>
              <button onClick={() => setAddFileOpen(true)} className="rounded p-0.5 text-dim hover:bg-white/5 hover:text-ink" aria-label="New file">
                <Plus className="h-3 w-3" />
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1">
            {activeFile ? (
              <CodeEditor value={activeFile.content} language={activeFile.language === 'yaml' ? 'yaml' : activeFile.language === 'python' ? 'python' : 'plaintext'} onChange={updateFileContent} />
            ) : (
              <div className="flex h-full items-center justify-center text-[11px] text-dim">Select a file to edit.</div>
            )}
          </div>

          <TestConsole
            node={node}
            testRun={testRun}
            running={testRunning}
            onRun={() => runTestsMutation.mutate()}
            onOpenTest={() => setTestOpen(true)}
          />
        </div>

        <ComponentConfig
          node={node}
          tab={configTab}
          onTabChange={setConfigTab}
          onUpdate={updateNode}
          onAddDependency={addDependency}
          onRemoveDependency={removeDependency}
        />
      </div>

      <VersionHistoryDialog
        open={versionOpen}
        onOpenChange={setVersionOpen}
        node={node}
        versions={versions}
        onRestore={handleRestore}
        onPublish={() => publishMutation.mutate()}
        publishing={publishMutation.isPending}
      />

      <TestNodeDialog
        open={testOpen}
        onOpenChange={setTestOpen}
        node={node}
        onRun={() => testMutation.mutate()}
        running={testOutputRunning}
        output={testOutput}
      />

      <Dialog open={addFileOpen} onOpenChange={setAddFileOpen}>
        <DialogContent size="sm">
          <DialogHeader eyebrow="Component file" title="Add a file" description="Add source, configuration or test files to this component." />
          <DialogBody className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">File name</label>
              <Input value={newFileName} onChange={(e) => setNewFileName(e.target.value)} placeholder="e.g. utils.py" autoFocus />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11.5px] text-muted">Language</label>
              <Select
                value={newFileLanguage}
                onValueChange={(v) => setNewFileLanguage(v as typeof newFileLanguage)}
                options={[
                  { value: 'python', label: 'Python' },
                  { value: 'yaml', label: 'YAML' },
                  { value: 'text', label: 'Plain text' },
                ]}
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAddFileOpen(false)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!newFileName.trim()}
              onClick={() => {
                const file: CustomNodeFile = { id: `f_${Date.now()}`, name: newFileName.trim(), language: newFileLanguage, content: '', dirty: true }
                updateNode({ files: [...node.files, file] })
                openFile(file)
                setAddFileOpen(false)
                setNewFileName('')
                toast.success('File created')
              }}
            >
              Create file
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
