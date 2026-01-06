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
import { Plus } from 'lucide-react'
import type { CodeData, WorkspaceTabType } from '../types/workspace'

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
  const { tabs, activeTabId, setActiveTab, closeTab, addTab, updateTab } = useWorkspaceStore()
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0]
  
  // Получаем актуальное состояние store для синхронного доступа
  const getStoreState = () => useWorkspaceStore.getState()

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

  // Определяем тип файла по mimeType и имени
  const determineFileType = (mimeType: string, fileName: string): WorkspaceTabType => {
    if (mimeType === 'application/vnd.google-apps.spreadsheet') {
      return 'sheets'
    } else if (mimeType === 'application/vnd.google-apps.document') {
      return 'docs'
    } else if (mimeType === 'application/vnd.google-apps.presentation') {
      return 'slides'
    } else if (mimeType.startsWith('text/') || 
               fileName.match(/\.(py|js|ts|tsx|jsx|html|css|json|md|java|cpp|c|go|rs|php|rb|swift|kt)$/i)) {
      return 'code'
    }
    return 'placeholder'
  }

  const handleFileSelect = async (file: { id: string; name: string; mimeType: string }) => {
    // Определяем тип файла заранее
    const fileType = determineFileType(file.mimeType, file.name)
    
    // Для sheets проверяем, существует ли уже таб с таким spreadsheetId
    let tabId: string | null = null
    if (fileType === 'sheets') {
      // Проверяем существующие табы (но мы еще не знаем spreadsheetId, так что создаем новый)
      // addTab сам проверит существование по spreadsheetId после загрузки
    }
    
    // Создаем таб сразу с isLoading: true
    addTab({
      type: fileType,
      title: file.name,
      closeable: true,
      isLoading: true
    })
    
    // Получаем ID созданного/активного таба из актуального состояния store
    // addTab устанавливает activeTabId на новый таб (или существующий для sheets)
    const storeState = getStoreState()
    tabId = storeState.activeTabId
    
    // Если таб не найден, ищем по названию и isLoading
    if (!tabId) {
      const loadingTab = storeState.tabs.find(t => t.title === file.name && t.isLoading)
      tabId = loadingTab?.id || null
    }
    
    // Устанавливаем isLoading: true на активный таб (на случай, если addTab обновил существующий)
    if (tabId) {
      updateTab(tabId, { isLoading: true })
    } else {
      console.error('Failed to get tab ID after creation')
      return
    }

    try {
      const fileContent = await getWorkspaceFileContent(file.id)
      
      // Обновляем таб с данными и убираем isLoading
      if (fileContent.is_spreadsheet && fileContent.spreadsheet_id) {
        updateTab(tabId, {
          type: 'sheets',
          url: fileContent.url,
          data: {
            spreadsheetId: fileContent.spreadsheet_id
          },
          isLoading: false
        })
      } else if (file.mimeType === 'application/vnd.google-apps.document') {
        updateTab(tabId, {
          type: 'docs',
          url: fileContent.url || `https://docs.google.com/document/d/${file.id}/preview`,
          data: {
            documentId: file.id
          },
          isLoading: false
        })
      } else if (fileContent.is_presentation && fileContent.presentation_id) {
        updateTab(tabId, {
          type: 'slides',
          url: fileContent.url || `https://docs.google.com/presentation/d/${file.id}/edit`,
          data: {
            presentationId: fileContent.presentation_id
          },
          isLoading: false
        })
      } else {
        // Determine if it's a code file
        const isCodeFile = file.mimeType.startsWith('text/') || 
                         file.name.match(/\.(py|js|ts|tsx|jsx|html|css|json|md|java|cpp|c|go|rs|php|rb|swift|kt)$/i)
        
        if (isCodeFile && fileContent.content) {
          updateTab(tabId, {
            type: 'code',
            data: {
              language: fileContent.language || 'text',
              code: fileContent.content,
              filename: file.name
            } as CodeData,
            isLoading: false
          })
        } else if (fileContent.content) {
          updateTab(tabId, {
            type: 'code',
            data: {
              language: fileContent.language || 'text',
              code: fileContent.content,
              filename: file.name
            } as CodeData,
            isLoading: false
          })
        } else {
          // Не удалось загрузить содержимое - закрываем таб
          closeTab(tabId)
          alert('Не удалось загрузить содержимое файла')
        }
      }
    } catch (error: any) {
      console.error('Failed to load file:', error)
      // Закрываем таб при ошибке
      closeTab(tabId)
      alert(error.message || 'Не удалось загрузить файл')
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
        paddingTop: '0', /* Header теперь часть flex layout, padding не нужен */
        backgroundColor: document.documentElement.classList.contains('dark')
          ? 'rgb(30 41 59)'
          : 'rgb(255 255 255)'
      }}
    >
      {/* Tab Bar - Always visible */}
      <div 
        className="flex border-t border-slate-200 dark:border-slate-700 overflow-x-auto scrollbar-thin bg-slate-100 dark:bg-slate-900 flex-shrink-0"
        style={{ 
          borderTopWidth: '1px', 
          minHeight: '35px',
          flexWrap: 'nowrap',
          overflowX: 'auto',
          overflowY: 'hidden'
        }}
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
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            color: 'rgb(100 116 139)', // slate-500
            marginLeft: '8px',
            marginRight: '8px',
            alignSelf: 'center'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgb(226 232 240)' // slate-200
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
          title="Добавить файл из рабочей области"
        >
          <Plus size={15} strokeWidth={2} />
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

