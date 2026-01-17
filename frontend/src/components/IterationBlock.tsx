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
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const startTimeRef = useRef<number | null>(null)
  
  useEffect(() => {
    if (thinking.isStreaming) {
      if (!startTimeRef.current) {
        startTimeRef.current = Date.now()
      }
      const interval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - (startTimeRef.current || Date.now())) / 1000)
        setElapsedSeconds(elapsed)
      }, 1000)
      return () => clearInterval(interval)
    } else {
      startTimeRef.current = null
    }
  }, [thinking.isStreaming])
  
  // Форматирование времени думания
  const formatDuration = (sec: number) => {
    if (sec < 1) return '<1с'
    return `${Math.round(sec)}с`
  }
  
  // Время для отображения: только во время стриминга
  const displayTime = thinking.isStreaming ? elapsedSeconds : 0
  
  // Получение динамического текста заголовка в зависимости от контекста
  const getThinkingLabel = (): string => {
    const context = thinking.context || 'thinking'
    
    const labels: Record<string, string> = {
      planning: 'Планирую следующие шаги',
      exploring: 'Исследую',
      analyzing: 'Анализирую',
      selecting: 'Выбираю инструменты',
      verifying: 'Проверяю',
      deciding: 'Принимаю решение',
      thinking: 'Думаю',
    }
    
    return labels[context] || 'Думаю'
  }
  
  // Получение результата после завершения
  const getResultLabel = (): string | null => {
    if (!thinking.result) return null
    
    const { type, count } = thinking.result
    
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
  const headerLabel = thinking.isStreaming 
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
            <span className={`iteration-action-icon ${action.status === 'done' ? 'done' : 'pending'}`}>
              {action.status === 'done' ? '✓' : '○'}
            </span>
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
