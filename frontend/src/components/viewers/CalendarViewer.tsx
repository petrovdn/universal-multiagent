import React, { useState } from 'react'
import { RefreshCw, ExternalLink, AlertCircle, Calendar as CalendarIcon } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import type { CalendarData } from '../../types/workspace'

interface CalendarViewerProps {
  tab: WorkspaceTab
}

export function CalendarViewer({ tab }: CalendarViewerProps) {
  const [isLoading, setIsLoading] = useState(false)
  const calendarData = tab.data as CalendarData | undefined

  const calendarId = calendarData?.calendarId || 'primary'
  const iframeUrl = `https://calendar.google.com/calendar/embed?src=${calendarId}&ctz=Europe/Moscow`

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <CalendarIcon className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {tab.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsLoading(true)}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Обновить"
          >
            <RefreshCw className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </button>
          <button
            onClick={() => window.open(`https://calendar.google.com/calendar/r?cid=${calendarId}`, '_blank')}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Открыть в Google Calendar"
          >
            <ExternalLink className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </button>
        </div>
      </div>

      {/* Iframe */}
      <div className="flex-1 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50 dark:bg-slate-950 z-10">
            <RefreshCw className="w-8 h-8 text-slate-400 animate-spin" />
          </div>
        )}
        <iframe
          src={iframeUrl}
          className="w-full h-full border-0"
          onLoad={() => setIsLoading(false)}
          title={tab.title}
        />
      </div>
    </div>
  )
}

