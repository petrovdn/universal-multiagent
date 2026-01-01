import React, { useState } from 'react'
import { RefreshCw, ExternalLink, AlertCircle } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'

interface DocsViewerProps {
  tab: WorkspaceTab
}

export function DocsViewer({ tab }: DocsViewerProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const url = tab.url || (tab.data?.documentId
    ? `https://docs.google.com/document/d/${tab.data.documentId}/edit`
    : null)

  const handleLoad = () => {
    setIsLoading(false)
    setError(null)
  }

  const handleError = () => {
    setIsLoading(false)
    setError('Не удалось загрузить документ')
  }

  const handleRefresh = () => {
    setIsLoading(true)
    setError(null)
    const iframe = document.getElementById(`docs-iframe-${tab.id}`) as HTMLIFrameElement
    if (iframe) {
      iframe.src = iframe.src
    }
  }

  const handleOpenExternal = () => {
    if (url) {
      window.open(url, '_blank')
    }
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
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {tab.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Обновить"
          >
            <RefreshCw className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </button>
          <button
            onClick={handleOpenExternal}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Открыть в новой вкладке"
          >
            <ExternalLink className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50 dark:bg-slate-950 z-10">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Загрузка документа...</p>
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
          id={`docs-iframe-${tab.id}`}
          src={url}
          className="w-full h-full border-0"
          onLoad={handleLoad}
          onError={handleError}
          title={tab.title}
        />
      </div>
    </div>
  )
}

