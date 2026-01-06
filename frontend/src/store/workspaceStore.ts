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
        tabs: [createPlaceholderTab()],
        activeTabId: PLACEHOLDER_TAB_ID,
        isPanelVisible: true, // Panel always visible
        panelSize: DEFAULT_PANEL_SIZE,

        addTab: (tabData) => {
        console.log('[WorkspaceStore] addTab called:', {
          type: tabData.type,
          title: tabData.title,
          spreadsheetId: tabData.data?.spreadsheetId,
          action: tabData.data?.action
        })
        set((state) => {
          
          // Check if tab with same spreadsheetId already exists (for sheets tabs)
          if (tabData.type === 'sheets' && tabData.data?.spreadsheetId) {
            console.log('[WorkspaceStore] Checking for existing tab with spreadsheetId:', tabData.data.spreadsheetId)
            const existingTab = state.tabs.find(
              t => t.type === 'sheets' && t.data?.spreadsheetId === tabData.data?.spreadsheetId
            )
            
            
            if (existingTab) {
              console.log('[WorkspaceStore] Found existing tab, updating:', existingTab.id)
              // Update existing tab with new action data
              const updatedData = {
                ...existingTab.data,
                ...tabData.data,
                // Merge actions array
                actions: [
                  ...(existingTab.data?.actions || []),
                  {
                    action: tabData.data?.action,
                    description: tabData.data?.description,
                    range: tabData.data?.range,
                    timestamp: tabData.data?.timestamp || Date.now()
                  }
                ].filter(Boolean) // Remove null/undefined entries
              }
              
              const updatedTabs = state.tabs.map(t =>
                t.id === existingTab.id
                  ? { ...t, title: tabData.title || t.title, url: tabData.url || t.url, data: updatedData }
                  : t
              )
              
              
              return {
                tabs: updatedTabs,
                activeTabId: existingTab.id, // Activate the existing tab
                isPanelVisible: true, // Ensure panel is visible
              }
            }
          }
          
          // Create new tab
          console.log('[WorkspaceStore] Creating new tab')
          const newTab: WorkspaceTab = {
            ...tabData,
            id: `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: Date.now(),
            // Initialize actions array for sheets tabs
            data: tabData.type === 'sheets' && tabData.data?.action
              ? {
                  ...tabData.data,
                  actions: [
                    {
                      action: tabData.data.action,
                      description: tabData.data.description,
                      range: tabData.data.range,
                      timestamp: tabData.data.timestamp || Date.now()
                    }
                  ]
                }
              : tabData.data
          }
          
          // Remove placeholder if it exists and we're adding a real tab
          const tabs = state.tabs.filter(t => t.id !== PLACEHOLDER_TAB_ID)
          const updatedTabs = [...tabs, newTab]
          
          const finalState = {
            tabs: updatedTabs,
            activeTabId: newTab.id,
            isPanelVisible: true, // Ensure panel is visible
          }
          
          
          console.log('[WorkspaceStore] Tab added, new state:', {
            tabsCount: finalState.tabs.length,
            activeTabId: finalState.activeTabId,
            newTabId: newTab.id,
            isPanelVisible: finalState.isPanelVisible,
            newTab: { id: newTab.id, type: newTab.type, title: newTab.title }
          })
          return finalState
        })

        get().saveToLocalStorage()
        
        const finalTabs = get().tabs
        
        console.log('[WorkspaceStore] addTab completed, final tabs:', get().tabs.map(t => ({ id: t.id, type: t.type, title: t.title })))
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
            
            // If only placeholder in localStorage, don't load it (keep initial state with placeholder)
            if (onlyPlaceholder) {
              console.log('Only placeholder in localStorage, keeping initial state')
              return
            }
            
            // Load real tabs from localStorage
            const hasRealTabs = parsed.state.tabs?.some((t: WorkspaceTab) => 
              t.id !== PLACEHOLDER_TAB_ID
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

