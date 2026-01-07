import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ExecutionMode = 'query' | 'plan' | 'agent'
type Theme = 'light' | 'dark'

interface IntegrationInfo {
  enabled: boolean
  authenticated: boolean
  email?: string
}

interface IntegrationsState {
  googleCalendar: IntegrationInfo
  gmail: IntegrationInfo
  googleSheets: IntegrationInfo
  googleWorkspace: IntegrationInfo & {
    folderConfigured?: boolean
    folderName?: string
    folderId?: string
  }
  onec: IntegrationInfo
  projectlad: IntegrationInfo
}

interface SettingsState {
  executionMode: ExecutionMode
  timezone: string
  theme: Theme
  debugMode: boolean
  showReasoning: boolean // Show reasoning blocks in Query mode
  integrations: IntegrationsState
  thinkingPreferences: {
    defaultCollapsed: boolean      // По умолчанию свёрнуто?
    pinnedThinkingIds: string[]    // Закреплённые thinking блоки (сохраняются между сессиями)
  }
  setExecutionMode: (mode: ExecutionMode) => void
  setTimezone: (tz: string) => void
  setTheme: (theme: Theme) => void
  setDebugMode: (enabled: boolean) => void
  setShowReasoning: (enabled: boolean) => void
  setIntegrationStatus: (integration: keyof IntegrationsState, status: Partial<IntegrationsState[keyof IntegrationsState]>) => void
  addPinnedThinkingId: (thinkingId: string) => void
  removePinnedThinkingId: (thinkingId: string) => void
}

// Migration function for old execution modes
const migrateExecutionMode = (mode: any): ExecutionMode => {
  if (mode === 'query' || mode === 'plan' || mode === 'agent') {
    return mode as ExecutionMode
  }
  // Map legacy modes to new ones
  if (mode === 'instant' || mode === 'react') {
    return 'agent'
  }
  if (mode === 'approval') {
    return 'plan'
  }
  // Default to agent
  return 'agent'
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      executionMode: 'agent',
      timezone: 'Europe/Moscow',
      theme: 'light',
      debugMode: false,
      showReasoning: false, // Hide reasoning by default in Query mode
      thinkingPreferences: {
        defaultCollapsed: true,  // По умолчанию свёрнуто
        pinnedThinkingIds: [],   // Закреплённые thinking блоки
      },
      integrations: {
        googleCalendar: {
          enabled: false,
          authenticated: false,
        },
        gmail: {
          enabled: false,
          authenticated: false,
        },
        googleSheets: {
          enabled: false,
          authenticated: false,
        },
        googleWorkspace: {
          enabled: false,
          authenticated: false,
          folderConfigured: false,
        },
        onec: {
          enabled: false,
          authenticated: false,
        },
        projectlad: {
          enabled: false,
          authenticated: false,
        },
      },
      
      setExecutionMode: (mode) =>
        set({ executionMode: mode }),
      
      setTimezone: (tz) =>
        set({ timezone: tz }),
      
      setTheme: (theme) =>
        set({ theme }),
      
      setDebugMode: (enabled) =>
        set({ debugMode: enabled }),
      
      setShowReasoning: (enabled) =>
        set({ showReasoning: enabled }),
      
      setIntegrationStatus: (integration, status) =>
        set((state) => ({
          integrations: {
            ...state.integrations,
            [integration]: {
              ...state.integrations[integration],
              ...status,
            },
          },
        })),
      
      addPinnedThinkingId: (thinkingId) =>
        set((state) => ({
          thinkingPreferences: {
            ...state.thinkingPreferences,
            pinnedThinkingIds: [...state.thinkingPreferences.pinnedThinkingIds.filter(id => id !== thinkingId), thinkingId],
          },
        })),
      
      removePinnedThinkingId: (thinkingId) =>
        set((state) => ({
          thinkingPreferences: {
            ...state.thinkingPreferences,
            pinnedThinkingIds: state.thinkingPreferences.pinnedThinkingIds.filter(id => id !== thinkingId),
          },
        })),
    }),
    {
      name: 'settings-storage',
      migrate: (persistedState: any, version: number) => {
        // Migrate old execution modes to new ones
        if (persistedState?.state?.executionMode) {
          persistedState.state.executionMode = migrateExecutionMode(persistedState.state.executionMode)
        }
        return persistedState
      },
    }
  )
)



