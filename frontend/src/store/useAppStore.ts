import { create } from 'zustand'
import type { AppNotification } from '@/types'

const seedNotifications: AppNotification[] = [
  { id: 'n1', title: 'Evaluation completed', body: 'Hybrid RAG pipeline scored 0.92 on rag_benchmark_v3.', time: '12 min ago', read: false, type: 'success' },
  { id: 'n2', title: 'Ingestion in progress', body: 'customer_feedback is syncing · 73% complete.', time: '24 min ago', read: false, type: 'info' },
  { id: 'n3', title: 'Custom node draft', body: 'Diversity-aware ranker v1.3.0 has unpublished changes.', time: '1 hour ago', read: false, type: 'warning' },
  { id: 'n4', title: 'Run failed', body: 'Run #2,485 failed at Hybrid Retrieval — Qdrant unreachable.', time: '1 hour ago', read: true, type: 'warning' },
]

interface AppState {
  sidebarCollapsed: boolean
  mobileNavOpen: boolean
  commandOpen: boolean
  createProjectOpen: boolean
  createPipelineOpen: boolean
  notificationsOpen: boolean
  shortcutsOpen: boolean
  aboutOpen: boolean
  notifications: AppNotification[]
  toggleSidebar: () => void
  setMobileNav: (open: boolean) => void
  setCommandOpen: (open: boolean) => void
  setCreateProjectOpen: (open: boolean) => void
  setCreatePipelineOpen: (open: boolean) => void
  setNotificationsOpen: (open: boolean) => void
  setShortcutsOpen: (open: boolean) => void
  setAboutOpen: (open: boolean) => void
  markAllRead: () => void
  pushNotification: (notification: Omit<AppNotification, 'id' | 'time' | 'read'>) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  mobileNavOpen: false,
  commandOpen: false,
  createProjectOpen: false,
  createPipelineOpen: false,
  notificationsOpen: false,
  shortcutsOpen: false,
  aboutOpen: false,
  notifications: seedNotifications,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setMobileNav: (open) => set({ mobileNavOpen: open }),
  setCommandOpen: (open) => set({ commandOpen: open }),
  setCreateProjectOpen: (open) => set({ createProjectOpen: open }),
  setCreatePipelineOpen: (open) => set({ createPipelineOpen: open }),
  setNotificationsOpen: (open) => set({ notificationsOpen: open }),
  setShortcutsOpen: (open) => set({ shortcutsOpen: open }),
  setAboutOpen: (open) => set({ aboutOpen: open }),
  markAllRead: () => set((s) => ({ notifications: s.notifications.map((n) => ({ ...n, read: true })) })),
  pushNotification: (notification) =>
    set((s) => ({
      notifications: [
        { ...notification, id: `n_${Date.now()}`, time: 'just now', read: false },
        ...s.notifications,
      ],
    })),
}))
