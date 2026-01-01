import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WorkspaceTab, WorkspaceStore } from '../types/workspace'

const STORAGE_KEY = 'workspace-store'
const DEFAULT_PANEL_SIZE = 33
const PLACEHOLDER_TAB_ID = 'placeholder-tab'

const createPlaceholderTab = (): WorkspaceTab => ({
  id: PLACEHOLDER_TAB_ID,
  type: 'placeholder',
  title: 'Начало работы',
  closeable: true, // Placeholder теперь можно закрыть
  timestamp: Date.now(),
})

const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set, get) => {
      return {
        tabs: [
          createPlaceholderTab(),
          {
            id: 'test-tab-1',
            type: 'sheets',
            title: 'Таблица продаж',
            closeable: true,
            timestamp: Date.now(),
            data: { url: 'https://docs.google.com/spreadsheets/d/1example' }
          },
          {
            id: 'test-tab-2',
            type: 'docs',
            title: 'Отчет Q4',
            closeable: true,
            timestamp: Date.now() + 1,
            data: { url: 'https://docs.google.com/document/d/1example' }
          },
          {
            id: 'test-tab-3',
            type: 'code',
            title: 'analytics.py',
            closeable: true,
            timestamp: Date.now() + 2,
            data: { code: 'import pandas as pd\n\ndef analyze_data():\n    df = pd.read_csv("data.csv")\n    return df.describe()' }
          }
        ],
        activeTabId: PLACEHOLDER_TAB_ID,
        isPanelVisible: true, // Panel always visible
        panelSize: DEFAULT_PANEL_SIZE,

        addTab: (tabData) => {
        const newTab: WorkspaceTab = {
          ...tabData,
          id: `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: Date.now(),
        }

        set((state) => {
          // Remove placeholder if it exists and we're adding a real tab
          const tabs = state.tabs.filter(t => t.id !== PLACEHOLDER_TAB_ID)
          const updatedTabs = [...tabs, newTab]
          
          const newState = {
            tabs: updatedTabs,
            activeTabId: newTab.id,
            // Panel always visible - don't change isPanelVisible
          }
          return newState
        })

        get().saveToLocalStorage()
      },

      closeTab: (id) => {
        // Allow closing placeholder now
        set((state) => {
          const tabs = state.tabs.filter(t => t.id !== id)
          let activeTabId = state.activeTabId

          // If we closed the active tab, switch to another one
          if (activeTabId === id) {
            if (tabs.length > 0) {
              activeTabId = tabs[tabs.length - 1].id
            } else {
              // No tabs left, add placeholder
              const placeholder = createPlaceholderTab()
              tabs.push(placeholder)
              activeTabId = placeholder.id
            }
          }

          // Panel always visible - don't change isPanelVisible
          return {
            tabs,
            activeTabId,
          }
        })

        get().saveToLocalStorage()
      },

      setActiveTab: (id) => {
        set({ activeTabId: id })
        get().saveToLocalStorage()
      },

      updateTab: (id, updates) => {
        set((state) => ({
          tabs: state.tabs.map(tab =>
            tab.id === id ? { ...tab, ...updates } : tab
          ),
        }))
        get().saveToLocalStorage()
      },

      setPanelSize: (size) => {
        set({ panelSize: Math.max(25, Math.min(50, size)) }) // Clamp between 25% and 50%
        get().saveToLocalStorage()
      },

      togglePanel: () => {
        set((state) => ({ isPanelVisible: !state.isPanelVisible }))
        get().saveToLocalStorage()
      },

      loadFromLocalStorage: () => {
        try {
          const stored = localStorage.getItem(STORAGE_KEY)
          if (stored) {
            const parsed = JSON.parse(stored)
            
            // Check if localStorage only has placeholder tab (old state)
            const onlyPlaceholder = parsed.state.tabs?.length === 1 && 
                                    parsed.state.tabs[0].id === PLACEHOLDER_TAB_ID
            
            // If only placeholder in localStorage, don't load it (keep test tabs from initial state)
            if (onlyPlaceholder) {
              console.log('Only placeholder in localStorage, keeping test tabs')
              return
            }
            
            // Load real tabs from localStorage
            const hasRealTabs = parsed.state.tabs?.some((t: WorkspaceTab) => 
              t.id !== PLACEHOLDER_TAB_ID && 
              !t.id.startsWith('test-tab')
            )
            
            if (hasRealTabs) {
              // Fix old placeholder tabs
              parsed.state.tabs = parsed.state.tabs.map((tab: WorkspaceTab) => {
                if (tab.id === PLACEHOLDER_TAB_ID) {
                  return { ...tab, closeable: true, title: 'Начало работы' }
                }
                return tab
              })
              
              set(parsed.state)
            }
          }
        } catch (error) {
          console.error('Failed to load workspace from localStorage:', error)
        }
      },

      saveToLocalStorage: () => {
        try {
          const state = get()
          localStorage.setItem(STORAGE_KEY, JSON.stringify({
            state: {
              tabs: state.tabs,
              activeTabId: state.activeTabId,
              isPanelVisible: state.isPanelVisible,
              panelSize: state.panelSize,
            },
          }))
        } catch (error) {
          console.error('Failed to save workspace to localStorage:', error)
        }
      },
    }},
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        tabs: state.tabs,
        activeTabId: state.activeTabId,
        isPanelVisible: state.isPanelVisible,
        panelSize: state.panelSize,
      }),
    }
  )
)

export { useWorkspaceStore }

