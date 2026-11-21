type Handler = (detail?: unknown) => void

const handlers = new Map<string, Set<Handler>>()

export const bus = {
  on(event: string, handler: Handler) {
    if (!handlers.has(event)) handlers.set(event, new Set())
    handlers.get(event)!.add(handler)
    return () => handlers.get(event)?.delete(handler)
  },
  emit(event: string, detail?: unknown) {
    handlers.get(event)?.forEach((handler) => handler(detail))
  },
}
