import React, { useState } from 'react'
import { ChevronRight, ChevronDown, Wrench, CheckCircle, XCircle, Brain } from 'lucide-react'
import { useChatStore, ReasoningStep } from '../store/chatStore'

export function ReasoningPanel() {
  const [isOpen, setIsOpen] = useState(true)
  const { reasoningSteps, clearReasoningSteps } = useChatStore()

  const getStepIcon = (type: ReasoningStep['type']) => {
    switch (type) {
      case 'thought':
        return <Brain className="h-4 w-4 text-blue-500" />
      case 'tool_call':
        return <Wrench className="h-4 w-4 text-yellow-500" />
      case 'tool_result':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'decision':
        return <XCircle className="h-4 w-4 text-purple-500" />
      default:
        return null
    }
  }

  return (
    <div className="w-80 border-l border-slate-200/50 dark:border-slate-700/50 bg-white/60 dark:bg-slate-800/60 backdrop-blur-sm flex flex-col">
      <div
        className="p-5 border-b border-slate-200/50 dark:border-slate-700/50 cursor-pointer flex items-center justify-between hover:bg-slate-50/50 dark:hover:bg-slate-700/30 transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <h2 className="font-light text-slate-800 dark:text-slate-100 text-lg tracking-wide">
          Рассуждения агента
        </h2>
        <div className="flex items-center space-x-2">
          {reasoningSteps.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                clearReasoningSteps()
              }}
              className="text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
            >
              Очистить
            </button>
          )}
          {isOpen ? (
            <ChevronDown className="h-5 w-5 text-slate-500" />
          ) : (
            <ChevronRight className="h-5 w-5 text-slate-500" />
          )}
        </div>
      </div>

      {isOpen && (
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {reasoningSteps.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 text-center mt-4">
              Пока нет шагов рассуждения. Здесь будут отображаться мысли агента.
            </p>
          ) : (
            reasoningSteps.map((step, index) => (
              <div
                key={index}
                className="border border-slate-200/50 dark:border-slate-700/50 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-900/50 shadow-sm"
              >
                <div className="flex items-start space-x-2">
                  {getStepIcon(step.type)}
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                      {step.type.replace('_', ' ').toUpperCase()}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                      {step.content}
                    </div>
                    {step.data && (
                      <details className="mt-2">
                        <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700 dark:hover:text-slate-300">
                          Детали
                        </summary>
                        <pre className="text-xs mt-2 p-2 bg-slate-100/50 dark:bg-slate-800/50 rounded overflow-auto">
                          {JSON.stringify(step.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

