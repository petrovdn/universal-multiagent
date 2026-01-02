import React, { useState, useEffect } from 'react'
import { RefreshCw, AlertCircle } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import { ActionOverlay } from './ActionOverlay'

interface SheetsViewerProps {
  tab: WorkspaceTab
}

export function SheetsViewer({ tab }: SheetsViewerProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [currentAction, setCurrentAction] = useState<{
    action: 'create' | 'append' | 'update' | 'read'
    description: string
  } | null>(null)
  
  // Build URL with range parameter if available
  const buildUrl = () => {
    const baseUrl = tab.url || (tab.data?.spreadsheetId 
      ? `https://docs.google.com/spreadsheets/d/${tab.data.spreadsheetId}/edit`
      : null)
    
    if (!baseUrl) return null
    
    // Add range parameter if available
    if (tab.data?.range) {
      const range = tab.data.range
      // Remove sheet name if present (e.g., "Sheet1!A1:B10" -> "A1:B10")
      const cellRange = range.includes('!') ? range.split('!')[1] : range
      return `${baseUrl}#range=${cellRange}`
    }
    
    return baseUrl
  }
  
  const url = buildUrl()

  // Show action overlay when action data is present
  useEffect(() => {
    if (tab.data?.action && tab.data?.description) {
      setCurrentAction({
        action: tab.data.action as 'create' | 'append' | 'update' | 'read',
        description: tab.data.description
      })
    }
  }, [tab.data?.action, tab.data?.description])

  const handleLoad = () => {
    setIsLoading(false)
    setError(null)
  }

  const handleError = () => {
    setIsLoading(false)
    setError('Не удалось загрузить таблицу')
  }


  if (!url) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-slate-400 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">URL таблицы не указан</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900" style={{ height: '100%', width: '100%' }}>
      {/* Content - iframe занимает всю область */}
      <div className="flex-1 relative" style={{ flex: '1 1 auto', minHeight: 0, width: '100%', height: '100%' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50 dark:bg-slate-950 z-10">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Загрузка таблицы...</p>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50 dark:bg-slate-950 z-10">
            <div className="text-center">
              <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          </div>
        )}
        <iframe
          id={`sheets-iframe-${tab.id}`}
          src={url}
          className="w-full h-full border-0"
          style={{ width: '100%', height: '100%', border: 'none' }}
          onLoad={handleLoad}
          onError={handleError}
          title={tab.title}
        />
        
        {/* Action Overlay */}
        {currentAction && (
          <ActionOverlay
            action={currentAction.action}
            description={currentAction.description}
            onDismiss={() => setCurrentAction(null)}
          />
        )}
        
        {/* Action Log - скрыт, чтобы не занимать место */}
      </div>
    </div>
  )
}

