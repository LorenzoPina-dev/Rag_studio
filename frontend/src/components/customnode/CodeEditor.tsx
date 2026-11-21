import * as React from 'react'
import Editor, { loader, type Monaco } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'

// Use the locally bundled Monaco instead of the CDN loader so the IDE works offline.
self.MonacoEnvironment = {
  getWorker() {
    return new editorWorker()
  },
}

loader.config({ monaco })

const theme: monaco.editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'keyword', foreground: 'C4A7FF' },
    { token: 'keyword.control', foreground: 'C4A7FF' },
    { token: 'string', foreground: '8FD6A8' },
    { token: 'string.escape', foreground: 'E0B77A' },
    { token: 'number', foreground: 'E8B985' },
    { token: 'comment', foreground: '5A6C86', fontStyle: 'italic' },
    { token: 'type', foreground: 'E5C07B' },
    { token: 'identifier', foreground: 'D4DCE8' },
    { token: 'delimiter', foreground: '8795AA' },
    { token: 'delimiter.parenthesis', foreground: '8795AA' },
    { token: 'function', foreground: '7FB0FF' },
  ],
  colors: {
    'editor.background': '#0A111C',
    'editor.foreground': '#C9D4E3',
    'editorLineNumber.foreground': '#3F4D63',
    'editorLineNumber.activeForeground': '#8593A9',
    'editorCursor.foreground': '#8FA6FF',
    'editor.selectionBackground': '#243B63',
    'editor.inactiveSelectionBackground': '#18283F',
    'editor.lineHighlightBackground': '#0E1826',
    'editorLineNumber.activeBackground': '#00000000',
    'editorIndentGuide.background1': '#1A2638',
    'editorIndentGuide.activeBackground1': '#2C3B52',
    'editorWidget.background': '#101A28',
    'editorWidget.border': '#2A3A51',
    'editorSuggestWidget.background': '#0F1927',
    'editorSuggestWidget.border': '#2A3A51',
    'editorSuggestWidget.selectedBackground': '#1B2B44',
    'scrollbarSlider.background': '#26344A66',
    'scrollbarSlider.hoverBackground': '#33445C88',
    'editorError.foreground': '#F06A6A',
    'editorWarning.foreground': '#F0B45C',
  },
}

export function CodeEditor({
  value,
  language,
  onChange,
  readOnly,
}: {
  value: string
  language: string
  onChange: (value: string) => void
  readOnly?: boolean
}) {
  const handleMount = React.useCallback((monacoInstance: Monaco) => {
    monacoInstance.editor.defineTheme('rag-studio', theme)
    monacoInstance.editor.setTheme('rag-studio')
  }, [])

  return (
    <Editor
      value={value}
      language={language}
      onChange={(next) => onChange(next ?? '')}
      beforeMount={handleMount}
      theme="rag-studio"
      loading={
        <div className="flex h-full items-center justify-center bg-[#0a111c]">
          <span className="font-mono text-[9px] uppercase tracking-wider text-dim">Loading editor…</span>
        </div>
      }
      options={{
        readOnly,
        fontSize: 11.5,
        fontFamily: '"JetBrains Mono", ui-monospace, monospace',
        fontLigatures: false,
        lineHeight: 20,
        padding: { top: 14, bottom: 14 },
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        cursorBlinking: 'smooth',
        renderLineHighlight: 'line',
        renderWhitespace: 'none',
        tabSize: 4,
        wordWrap: 'off',
        lineNumbersMinChars: 3,
        glyphMargin: false,
        folding: true,
        bracketPairColorization: { enabled: true },
        guides: { indentation: true, bracketPairs: false },
        contextmenu: true,
        automaticLayout: true,
        scrollbar: { verticalScrollbarSize: 9, horizontalScrollbarSize: 9, useShadows: false },
        overviewRulerLanes: 0,
        hideCursorInOverviewRuler: true,
        overviewRulerBorder: false,
        stickyScroll: { enabled: false },
      }}
    />
  )
}
