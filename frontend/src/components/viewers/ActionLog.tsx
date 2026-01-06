import React, { useState } from 'react'
import { ChevronDown, ChevronUp, History, X } from 'lucide-react'
import { CheckCircle, Plus, Edit, Eye } from 'lucide-react'

interface Action {
  action: 'create' | 'append' | 'update' | 'read'
  description: string
  timestamp: number
}

interface ActionLogProps {
  actions: Action[]
  onClear?: () => void
}

const actionIcons = {
  create: CheckCircle,
  append: Plus,
  update: Edit,
  read: Eye,
}

const actionLabels = {
  create: 'Создано',
  append: 'Добавлено',
  update: 'Обновлено',
  read: 'Прочитано',
}

export function ActionLog({ actions, onClear }: ActionLogProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (actions.length === 0) {
    return null
  }

  // Show last 10 actions
  const displayActions = actions.slice(-10).reverse()

  return (
    <div className="absolute bottom-4 right-4 z-20">
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-slate-600 dark:text-slate-400" />
            <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              История действий ({actions.length})
            </span>
          </div>
          <div className="flex items-center gap-2">
            {onClear && actions.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onClear()
                }}
                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
                title="Очистить историю"
              >
                <X className="w-4 h-4 text-slate-600 dark:text-slate-400" />
              </button>
            )}
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-slate-600 dark:text-slate-400" />
            ) : (
              <ChevronUp className="w-4 h-4 text-slate-600 dark:text-slate-400" />
            )}
          </div>
        </div>

        {/* Actions List */}
        {isExpanded && (
          <div className="max-h-[400px] overflow-y-auto">
            {displayActions.map((action, index) => {
              const Icon = actionIcons[action.action] || CheckCircle
              const time = new Date(action.timestamp).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
              })

              return (
                <div
                  key={index}
                  className="px-4 py-2 border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <Icon className="w-4 h-4 text-slate-500 dark:text-slate-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                          {actionLabels[action.action]}
                        </span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          {time}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        {action.description}
                      </p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}





