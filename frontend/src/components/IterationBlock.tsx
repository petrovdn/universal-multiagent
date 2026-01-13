import React, { useState, useEffect, useRef } from 'react'
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
  
  // Время для отображения: во время стриминга - обратный отсчёт, после - финальное время
  const displayTime = thinking.isStreaming ? elapsedSeconds : thinking.durationSec

  return (
    <div className={`iteration-block ${className}`}>
      {/* Think секция */}
      <div className="iteration-think">
        <div 
          className="iteration-think-header"
          onClick={onToggleThinkingCollapse}
          style={{ cursor: 'pointer' }}
        >
          <span className="iteration-chevron">
            {thinking.isCollapsed ? '▶' : '▼'}
          </span>
          <span className="iteration-think-icon">💭</span>
          <span className="iteration-think-label">
            Думаю{displayTime > 0 && ` (${formatDuration(displayTime)})`}
          </span>
          {thinking.isStreaming && (
            <span className="iteration-think-dots">
              <span className="dot-1">.</span>
              <span className="dot-2">.</span>
              <span className="dot-3">.</span>
            </span>
          )}
        </div>
        
        {!thinking.isCollapsed && thinking.content && (
          <div className="iteration-think-content">
            <pre>{thinking.content}</pre>
            {thinking.isStreaming && (
              <span className="text-streaming-cursor">▊</span>
            )}
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
            <div className="iteration-operation-content">
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
