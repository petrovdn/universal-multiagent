import React from 'react'
import { useWorkspaceStore } from '../store/workspaceStore'
import { TabComponent } from './TabComponent'
import { SheetsViewer } from './viewers/SheetsViewer'
import { DocsViewer } from './viewers/DocsViewer'
import { EmailPreview } from './viewers/EmailPreview'
import { DashboardViewer } from './viewers/DashboardViewer'
import { ChartViewer } from './viewers/ChartViewer'
import { CodeViewer } from './viewers/CodeViewer'
import { CalendarViewer } from './viewers/CalendarViewer'
import { PlaceholderViewer } from './viewers/PlaceholderViewer'

function TabContent({ tab }: { tab: any }) {
  switch (tab.type) {
    case 'sheets':
      return <SheetsViewer tab={tab} />
    case 'docs':
      return <DocsViewer tab={tab} />
    case 'email':
      return <EmailPreview tab={tab} />
    case 'dashboard':
      return <DashboardViewer tab={tab} />
    case 'chart':
      return <ChartViewer tab={tab} />
    case 'code':
      return <CodeViewer tab={tab} />
    case 'calendar':
      return <CalendarViewer tab={tab} />
    case 'placeholder':
    default:
      return <PlaceholderViewer />
  }
}

export function WorkspacePanel() {
  const { tabs, activeTabId, setActiveTab, closeTab } = useWorkspaceStore()
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0]

  // Debug logging
  React.useEffect(() => {
    console.log('[WorkspacePanel] Render:', {
      tabsCount: tabs.length,
      activeTabId,
      activeTabIdInTabs: tabs.some(t => t.id === activeTabId),
      activeTab: activeTab ? { id: activeTab.id, type: activeTab.type, title: activeTab.title } : null,
      allTabIds: tabs.map(t => t.id)
    })
  }, [tabs, activeTabId, activeTab])

  return (
    <div 
      style={{ 
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        paddingTop: '56px',
        backgroundColor: document.documentElement.classList.contains('dark')
          ? 'rgb(30 41 59)'
          : 'rgb(255 255 255)'
      }}
    >
      {/* Tab Bar - Always visible */}
      {tabs.length > 0 && (
        <div 
          className="flex border-t border-slate-200 dark:border-slate-700 overflow-x-auto scrollbar-thin bg-slate-100 dark:bg-slate-900 flex-shrink-0"
          style={{ borderTopWidth: '1px', minHeight: '35px' }}
        >
          {tabs.map((tab, index) => (
            <TabComponent
              key={tab.id}
              tab={tab}
              isActive={activeTabId === tab.id}
              onClick={() => setActiveTab(tab.id)}
              onClose={() => closeTab(tab.id)}
              isLast={index === tabs.length - 1}
            />
          ))}
        </div>
      )}

      {/* Tab Content */}
      <div 
        style={{
          backgroundColor: document.documentElement.classList.contains('dark')
            ? 'rgb(30 41 59)'
            : 'rgb(255 255 255)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          flex: '1 1 auto',
          minHeight: 0,
          width: '100%'
        }}
      >
        {activeTab && <TabContent tab={activeTab} />}
      </div>
    </div>
  )
}

