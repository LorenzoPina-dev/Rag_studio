import { loader } from '@monaco-editor/react'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'

type MonacoModule = typeof import('monaco-editor')

let setup: Promise<MonacoModule> | null = null

/**
 * Monaco is several megabytes: load it only when an editor is actually shown,
 * keep the locally bundled worker so the IDE still works offline, and share
 * the promise so repeated mounts do not re-import the module.
 */
export function loadMonaco(): Promise<MonacoModule> {
  if (!setup) {
    setup = import('monaco-editor').then((monaco) => {
      self.MonacoEnvironment = {
        getWorker() {
          return new editorWorker()
        },
      }
      loader.config({ monaco })
      return monaco
    })
  }
  return setup
}
