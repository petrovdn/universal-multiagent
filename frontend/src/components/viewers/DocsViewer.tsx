import React, { useState } from 'react'
import { RefreshCw, AlertCircle } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'

interface DocsViewerProps {
  tab: WorkspaceTab
}

export function DocsViewer({ tab }: DocsViewerProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Build URL with edit mode for full interface with formatting toolbar
  const buildUrl = () => {
    const baseUrl = tab.url || (tab.data?.documentId
      ? `https://docs.google.com/document/d/${tab.data.documentId}/edit`
      : null)
    
    if (!baseUrl) return null
    
    // Ensure we're using edit mode (not preview) to show full interface
    return baseUrl.replace('/preview', '/edit')
  }
  
  const url = buildUrl()

  const handleLoad = () => {
    setIsLoading(false)
    setError(null)
  }

  const handleError = () => {
    setIsLoading(false)
    setError('Не удалось загрузить документ')
  }

  if (!url) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-slate-400 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">URL документа не указан</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900" style={{ height: '100%', width: '100%', minHeight: 0 }}>
      {/* Content - iframe занимает всю область */}
      <div className="flex-1 relative bg-white dark:bg-slate-900" style={{ flex: '1 1 auto', minHeight: 0, width: '100%', height: '100%' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-slate-900 z-10">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Загрузка документа...</p>
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-slate-900 z-10">
            <div className="text-center">
              <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          </div>
        )}
        <iframe
          id={`docs-iframe-${tab.id}`}
          src={url}
          className="w-full h-full border-0 bg-white dark:bg-slate-900"
          style={{ width: '100%', height: '100%', border: 'none', minHeight: 0 }}
          onLoad={handleLoad}
          onError={handleError}
          title={tab.title}
          allow="fullscreen"
        />
      </div>
    </div>
  )
}

