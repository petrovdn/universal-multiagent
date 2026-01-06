import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ExecutionMode = 'instant' | 'approval' | 'react' | 'query'
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
  integrations: IntegrationsState
  setExecutionMode: (mode: ExecutionMode) => void
  setTimezone: (tz: string) => void
  setTheme: (theme: Theme) => void
  setDebugMode: (enabled: boolean) => void
  setIntegrationStatus: (integration: keyof IntegrationsState, status: Partial<IntegrationsState[keyof IntegrationsState]>) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      executionMode: 'instant',
      timezone: 'Europe/Moscow',
      theme: 'light',
      debugMode: false,
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
    }),
    {
      name: 'settings-storage',
    }
  )
)



