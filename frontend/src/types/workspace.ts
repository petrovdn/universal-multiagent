/**
 * TypeScript definitions for workspace tabs and panels
 */

export type WorkspaceTabType = 
  | 'sheets' 
  | 'docs' 
  | 'email' 
  | 'dashboard' 
  | 'chart' 
  | 'code' 
  | 'calendar' 
  | 'placeholder'

export interface WorkspaceTab {
  id: string
  type: WorkspaceTabType
  title: string
  url?: string
  data?: any
  closeable: boolean
  timestamp: number
}

export interface WorkspaceStore {
  tabs: WorkspaceTab[]
  activeTabId: string | null
  isPanelVisible: boolean
  panelSize: number // percentage width for chat panel (default: 33)
  
  // Actions
  addTab: (tab: Omit<WorkspaceTab, 'id' | 'timestamp'>) => void
  closeTab: (id: string) => void
  setActiveTab: (id: string) => void
  updateTab: (id: string, updates: Partial<WorkspaceTab>) => void
  setPanelSize: (size: number) => void
  togglePanel: () => void
  
  // Persistence
  loadFromLocalStorage: () => void
  saveToLocalStorage: () => void
}

// Chart data structure for ChartViewer
export interface ChartData {
  chartType: 'line' | 'bar' | 'pie' | 'area' | 'scatter' | 'donut' | 'radialBar'
  series: Array<{
    name: string
    data: number[] | Array<[number, number]>
  }>
  options?: any // ApexCharts options
}

// Code viewer data structure
export interface CodeData {
  language: string
  code: string
  filename?: string
}

// Calendar data structure
export interface CalendarData {
  calendarId?: string
}

