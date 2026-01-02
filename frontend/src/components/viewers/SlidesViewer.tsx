import React, { useState } from 'react'
import { RefreshCw, ExternalLink, AlertCircle } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'

interface SlidesViewerProps {
  tab: WorkspaceTab
}

export function SlidesViewer({ tab }: SlidesViewerProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const url = tab.url || (tab.data?.presentationId
    ? `https://docs.google.com/presentation/d/${tab.data.presentationId}/edit`
    : null)

  const handleLoad = () => {
    setIsLoading(false)
    setError(null)
  }

  const handleError = () => {
    setIsLoading(false)
    setError('Не удалось загрузить презентацию')
  }

  const handleRefresh = () => {
    setIsLoading(true)
    setError(null)
    const iframe = document.getElementById(`slides-iframe-${tab.id}`) as HTMLIFrameElement
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
          <p className="text-slate-600 dark:text-slate-400">URL презентации не указан</p>
        </div>
      </div>
    )
  }

  // Use edit mode URL for editing capabilities
  const editUrl = url?.replace('/preview', '/edit') || url

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900" style={{ height: '100%', width: '100%' }}>
      {/* Content - iframe занимает всю область */}
      <div className="flex-1 relative" style={{ flex: '1 1 auto', minHeight: 0, width: '100%', height: '100%' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-slate-900 z-10">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-600 dark:text-slate-400">Загрузка презентации...</p>
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
        {editUrl && (
          <iframe
            id={`slides-iframe-${tab.id}`}
            src={editUrl}
            className="w-full h-full border-0"
            style={{ width: '100%', height: '100%', border: 'none' }}
            onLoad={handleLoad}
            onError={handleError}
            title={tab.title}
            allow="fullscreen"
          />
        )}
      </div>
    </div>
  )
}

