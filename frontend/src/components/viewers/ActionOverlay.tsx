import React, { useEffect, useState } from 'react'
import { CheckCircle, Plus, Edit, Eye, X } from 'lucide-react'

interface ActionOverlayProps {
  action: 'create' | 'append' | 'update' | 'read'
  description: string
  onDismiss?: () => void
}

const actionIcons = {
  create: CheckCircle,
  append: Plus,
  update: Edit,
  read: Eye,
}

const actionColors = {
  create: 'bg-green-500',
  append: 'bg-blue-500',
  update: 'bg-yellow-500',
  read: 'bg-slate-500',
}

export function ActionOverlay({ action, description, onDismiss }: ActionOverlayProps) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    // Auto-dismiss after 3 seconds
    const timer = setTimeout(() => {
      setIsVisible(false)
      setTimeout(() => {
        onDismiss?.()
      }, 300) // Wait for fade-out animation
    }, 3000)

    return () => clearTimeout(timer)
  }, [onDismiss])

  const Icon = actionIcons[action] || CheckCircle
  const colorClass = actionColors[action] || 'bg-slate-500'

  if (!isVisible) {
    return null
  }

  return (
    <div
      className="absolute top-4 right-4 z-20 transition-opacity duration-300"
      style={{ opacity: isVisible ? 1 : 0 }}
    >
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 p-4 min-w-[300px] max-w-[400px]">
        <div className="flex items-start gap-3">
          <div className={`${colorClass} rounded-full p-2 flex-shrink-0`}>
            <Icon className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {action === 'create' && 'Таблица создана'}
                {action === 'append' && 'Строки добавлены'}
                {action === 'update' && 'Ячейки обновлены'}
                {action === 'read' && 'Данные прочитаны'}
              </span>
              {onDismiss && (
                <button
                  onClick={() => {
                    setIsVisible(false)
                    setTimeout(() => onDismiss(), 300)
                  }}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {description}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

