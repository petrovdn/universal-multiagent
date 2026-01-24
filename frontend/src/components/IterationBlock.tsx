import React, { useState, useEffect, useRef } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { IterationBlock as IterationBlockType, Operation } from '../store/chatStore'

interface IterationBlockProps {
  iteration: IterationBlockType
  operation?: Operation           // Связанная операция (для стриминга данных)
  onToggleThinkingCollapse: () => void
  onToggleOperationCollapse?: () => void
  className?: string
}

export function IterationBlock({
  iteration,
  operation,
  onToggleThinkingCollapse,
  onToggleOperationCollapse,
  className = ''
}: IterationBlockProps) {
  const { thinking, summary, action } = iteration
  
  // Refs для автоскролла
  const thinkingContentRef = useRef<HTMLDivElement>(null)
  const operationContentRef = useRef<HTMLDivElement>(null)
  
  // Обратный отсчёт времени во время думания
  // CRITICAL: Use thinking.startedAt from store to preserve time across tab switches
  const [elapsedSeconds, setElapsedSeconds] = useState(() => {
    // Initialize from store if available (for persisted time)
    if (thinking.startedAt) {
      return Math.floor((Date.now() - thinking.startedAt) / 1000)
    }
    return 0
  })
  
  useEffect(() => {
    if (thinking.isStreaming) {
      // Use thinking.startedAt from store if available, otherwise use current time
      const startTime = thinking.startedAt || Date.now()
      
      const interval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000)
        setElapsedSeconds(elapsed)
      }, 1000)
      return () => clearInterval(interval)
    } else {
      // When streaming stops, use elapsedSeconds from store if available
      if (thinking.elapsedSeconds !== undefined) {
        setElapsedSeconds(thinking.elapsedSeconds)
      }
    }
  }, [thinking.isStreaming, thinking.startedAt, thinking.elapsedSeconds])
  
  // Форматирование времени думания
  const formatDuration = (sec: number) => {
    if (sec < 1) return '<1с'
    return `${Math.round(sec)}с`
  }
  
  // Время для отображения: during streaming use elapsedSeconds, after completion use thinking.elapsedSeconds
  const displayTime = thinking.isStreaming 
    ? elapsedSeconds 
    : (thinking.elapsedSeconds !== undefined ? thinking.elapsedSeconds : 0)
  
  // Упрощенная логика: "Думаю" во время streaming, "Думал" после завершения
  const getThinkingLabel = (): string => {
    // Во время streaming - "Думаю", после завершения - "Думал"
    return thinking.isStreaming ? 'Думаю' : 'Думал'
  }
  
  // Получение результата после завершения
  const getResultLabel = (): string | null => {
    if (!thinking.result) return null
    
    const { type, count } = thinking.result
    
    // Не показываем результат если count === 0 (нет реальных tool calls)
    if (count === 0) return null
    
    // Функция склонения
    const pluralize = (n: number, one: string, few: string, many: string): string => {
      const mod10 = n % 10
      const mod100 = n % 100
      if (mod100 >= 11 && mod100 <= 19) return many
      if (mod10 === 1) return one
      if (mod10 >= 2 && mod10 <= 4) return few
      return many
    }
    
    const resultLabels: Record<string, (n: number) => string> = {
      sources: (n) => `Проверил ${n} ${pluralize(n, 'источник', 'источника', 'источников')}`,
      files: (n) => `Изучил ${n} ${pluralize(n, 'файл', 'файла', 'файлов')}`,
      tools: (n) => `Использовал ${n} ${pluralize(n, 'инструмент', 'инструмента', 'инструментов')}`,
      searches: (n) => `Выполнил ${n} ${pluralize(n, 'поиск', 'поиска', 'поисков')}`,
      operations: (n) => `Выполнил ${n} ${pluralize(n, 'операцию', 'операции', 'операций')}`,
    }
    
    return resultLabels[type]?.(count) || null
  }

  // Автоскролл thinking content при стриминге
  useEffect(() => {
    if (thinking.isStreaming && thinkingContentRef.current) {
      thinkingContentRef.current.scrollTop = thinkingContentRef.current.scrollHeight
    }
  }, [thinking.content, thinking.isStreaming])

  // Автоскролл operation content при стриминге
  useEffect(() => {
    if (operation?.status === 'streaming' && operationContentRef.current) {
      operationContentRef.current.scrollTop = operationContentRef.current.scrollHeight
    }
  }, [operation?.data, operation?.status])

  // Формируем текст заголовка
  // КРИТИЧНО: При закрытии (isCollapsed) всегда показываем "Думал", а не результат инструмента
  const headerLabel = thinking.isCollapsed
    ? getThinkingLabel() // При закрытии всегда "Думал"
    : thinking.isStreaming 
      ? `${getThinkingLabel()} (${formatDuration(displayTime)})`
      : (getResultLabel() || getThinkingLabel())

  return (
    <div className={`iteration-block ${className}`}>
      {/* Think секция */}
      <div className={`iteration-think ${thinking.isStreaming ? 'iteration-think-streaming' : ''}`}>
        <div 
          className="iteration-think-header"
          onClick={onToggleThinkingCollapse}
        >
          <span className="iteration-think-label">
            {headerLabel}
          </span>
          {thinking.isStreaming && (
            <span className="iteration-think-dots">
              <span className="dot-1">.</span>
              <span className="dot-2">.</span>
              <span className="dot-3">.</span>
            </span>
          )}
          <span className="iteration-chevron-right">
            {thinking.isCollapsed ? (
              <ChevronRight size={14} />
            ) : (
              <ChevronDown size={14} />
            )}
          </span>
        </div>
        
        {!thinking.isCollapsed && thinking.content && (
          <div className="iteration-think-content" ref={thinkingContentRef}>
            <pre>{thinking.content.trimStart()}</pre>
          </div>
        )}
      </div>

      {/* Summary секция (план после думания) - без стрелки, она в тексте */}
      {summary && (
        <div className="iteration-summary">
          <span className="iteration-summary-text">{summary}</span>
        </div>
      )}

      {/* Act секция (действие) - на одной строке */}
      {action && (
        <div className="iteration-action">
          <div className="iteration-action-header">
            <span className={`iteration-action-title ${action.status === 'pending' ? 'pending' : ''}`}>
              {action.title}
            </span>
            {action.status === 'pending' && (
              <span className="iteration-action-dots">
                <span className="dot-1">.</span>
                <span className="dot-2">.</span>
                <span className="dot-3">.</span>
              </span>
            )}
            {action.status === 'done' && (
              <span className="iteration-action-done">Выполнено</span>
            )}
          </div>
        </div>
      )}

      {/* Связанная операция (окно со стримингом данных) */}
      {operation && operation.data.length > 0 && (
        <div className="iteration-operation">
          <div 
            className="iteration-operation-header"
            onClick={onToggleOperationCollapse}
            style={{ cursor: 'pointer' }}
          >
            <span className="iteration-chevron">
              {operation.isCollapsed ? '▶' : '▼'}
            </span>
            <span className="iteration-operation-title">{operation.streamingTitle}</span>
            {operation.status === 'streaming' && (
              <span className="iteration-operation-streaming">🔄</span>
            )}
          </div>
          
          {!operation.isCollapsed && (
            <div className="iteration-operation-content" ref={operationContentRef}>
              {operation.data.join('\n')}
              {operation.status === 'streaming' && (
                <span className="text-streaming-cursor">▊</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
