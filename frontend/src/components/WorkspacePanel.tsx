import React, { useState, useEffect } from 'react'
import { useWorkspaceStore } from '../store/workspaceStore'
import { TabComponent } from './TabComponent'
import { getWorkspaceFileContent } from '../services/api'
import { SheetsViewer } from './viewers/SheetsViewer'
import { DocsViewer } from './viewers/DocsViewer'
import { SlidesViewer } from './viewers/SlidesViewer'
import { EmailPreview } from './viewers/EmailPreview'
import { DashboardViewer } from './viewers/DashboardViewer'
import { ChartViewer } from './viewers/ChartViewer'
import { CodeViewer } from './viewers/CodeViewer'
import { CalendarViewer } from './viewers/CalendarViewer'
import { PlaceholderViewer } from './viewers/PlaceholderViewer'
import { Plus, Loader2 } from 'lucide-react'
import type { CodeData } from '../types/workspace'

function TabContent({ tab }: { tab: any }) {
  switch (tab.type) {
    case 'sheets':
      return <SheetsViewer tab={tab} />
    case 'docs':
      return <DocsViewer tab={tab} />
    case 'slides':
      return <SlidesViewer tab={tab} />
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
  const { tabs, activeTabId, setActiveTab, closeTab, addTab } = useWorkspaceStore()
  const [isLoadingFile, setIsLoadingFile] = useState(false)
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0]

  // Listen for file selection from popup window
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Verify origin for security
      if (event.origin !== window.location.origin) return

      if (event.data.type === 'workspace-file-selected') {
        const file = event.data.file
        await handleFileSelect(file)
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  const openFileSelector = () => {
    const width = 950  // 864 * 1.1 = 950.4 (увеличено на 10%)
    const height = 700
    const left = (window.screen.width - width) / 2
    const top = (window.screen.height - height) / 2
    
    window.open(
      '/file-selector.html',
      'workspaceFileSelector',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    )
  }

  const handleFileSelect = async (file: { id: string; name: string; mimeType: string }) => {
    setIsLoadingFile(true)
    try {
      const fileContent = await getWorkspaceFileContent(file.id)
      
      // Check if it's a Google Sheets spreadsheet
      if (fileContent.is_spreadsheet && fileContent.spreadsheet_id) {
        // Add as sheets tab
        addTab({
          type: 'sheets',
          title: file.name,
          closeable: true,
          url: fileContent.url,
          data: {
            spreadsheetId: fileContent.spreadsheet_id
          }
        })
      } else if (file.mimeType === 'application/vnd.google-apps.document') {
        // Google Docs document - use DocsViewer
        addTab({
          type: 'docs',
          title: file.name,
          closeable: true,
          url: fileContent.url || `https://docs.google.com/document/d/${file.id}/preview`,
          data: {
            documentId: file.id
          }
        })
      } else if (fileContent.is_presentation && fileContent.presentation_id) {
        // Google Slides presentation - use SlidesViewer
        addTab({
          type: 'slides',
          title: file.name,
          closeable: true,
          url: fileContent.url || `https://docs.google.com/presentation/d/${file.id}/edit`,
          data: {
            presentationId: fileContent.presentation_id
          }
        })
      } else {
        // Determine if it's a code file
        const isCodeFile = file.mimeType.startsWith('text/') || 
                         file.name.match(/\.(py|js|ts|tsx|jsx|html|css|json|md|java|cpp|c|go|rs|php|rb|swift|kt)$/i)
        
        if (isCodeFile && fileContent.content) {
          // Add as code tab
          addTab({
            type: 'code',
            title: file.name,
            closeable: true,
            data: {
              language: fileContent.language || 'text',
              code: fileContent.content,
              filename: file.name
            } as CodeData
          })
        } else if (fileContent.content) {
          // For other text files, add as code tab
          addTab({
            type: 'code',
            title: file.name,
            closeable: true,
            data: {
              language: fileContent.language || 'text',
              code: fileContent.content,
              filename: file.name
            } as CodeData
          })
        } else {
          alert('Не удалось загрузить содержимое файла')
        }
      }
    } catch (error: any) {
      console.error('Failed to load file:', error)
      alert(error.message || 'Не удалось загрузить файл')
    } finally {
      setIsLoadingFile(false)
    }
  }

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
        
        {/* Add File Button */}
        <button
          onClick={openFileSelector}
          disabled={isLoadingFile}
          style={{ 
            width: '24px',
            height: '24px',
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '3px',
            backgroundColor: 'transparent',
            border: 'none',
            cursor: isLoadingFile ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
            color: 'rgb(100 116 139)', // slate-500
            opacity: isLoadingFile ? 0.5 : 1,
            marginLeft: '8px',
            alignSelf: 'center'
          }}
          onMouseEnter={(e) => {
            if (!isLoadingFile) {
              e.currentTarget.style.backgroundColor = 'rgb(226 232 240)' // slate-200
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
          title="Добавить файл из рабочей области"
        >
          {isLoadingFile ? (
            <Loader2 size={15} strokeWidth={2} />
          ) : (
            <Plus size={15} strokeWidth={2} />
          )}
        </button>
      </div>

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

