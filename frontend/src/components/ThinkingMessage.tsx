import React, { useEffect, useState, useRef } from 'react'
import { Brain, ChevronDown, ChevronUp, Pin, PinOff } from 'lucide-react'
import { ThinkingBlock } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'

interface ThinkingMessageProps {
  thinkingId: string
  block: ThinkingBlock
  onToggleCollapse: () => void
  onTogglePin: () => void
}

export function ThinkingMessage({ thinkingId, block, onToggleCollapse, onTogglePin }: ThinkingMessageProps) {
  const [localElapsedTime, setLocalElapsedTime] = useState(block.elapsedSeconds)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const { addPinnedThinkingId, removePinnedThinkingId, thinkingPreferences } = useSettingsStore()
  
  // Синхронизация pinned состояния с settingsStore
  const handleTogglePin = () => {
    if (block.isPinned) {
      removePinnedThinkingId(thinkingId)
    } else {
      addPinnedThinkingId(thinkingId)
    }
    onTogglePin()
  }
  
  // Проверка pinned при монтировании (один раз)
  useEffect(() => {
    const isPinnedInSettings = thinkingPreferences.pinnedThinkingIds.includes(thinkingId)
    if (isPinnedInSettings && !block.isPinned) {
      // Синхронизируем если в settings закреплён, а в блоке нет
      handleTogglePin()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Только при монтировании
  
  // Обновление локального таймера когда статус streaming
  useEffect(() => {
    if (block.status === 'streaming') {
      intervalRef.current = setInterval(() => {
        setLocalElapsedTime(prev => {
          // Округляем до 0.1 секунды
          return Math.round((prev + 0.1) * 10) / 10
        })
      }, 100)
      
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    } else {
      // Когда завершён, используем финальное значение из block
      setLocalElapsedTime(block.elapsedSeconds)
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [block.status, block.elapsedSeconds])
  
  // Синхронизация с серверным elapsedSeconds
  useEffect(() => {
    if (block.elapsedSeconds > localElapsedTime) {
      setLocalElapsedTime(block.elapsedSeconds)
    }
  }, [block.elapsedSeconds])
  
  // Auto-scroll при streaming
  useEffect(() => {
    if (contentRef.current && block.status === 'streaming' && !block.isCollapsed) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [block.content, block.status, block.isCollapsed])
  
  const elapsedDisplay = localElapsedTime.toFixed(1)
  
  return (
    <div 
      className={`thinking-message ${block.isCollapsed ? 'thinking-message-collapsed' : ''} ${block.isPinned ? 'thinking-message-pinned' : ''} ${block.status === 'streaming' ? 'thinking-message-streaming' : ''}`}
      data-thinking-id={thinkingId}
    >
      <div 
        className="thinking-message-header"
        onClick={onToggleCollapse}
      >
        <Brain className="thinking-message-icon" size={16} />
        <span className="thinking-message-title">Thinking</span>
        <span className="thinking-message-time">
          Thought for {elapsedDisplay} seconds
        </span>
        <div className="thinking-message-actions">
          <button
            className="thinking-message-pin-button"
            onClick={(e) => {
              e.stopPropagation()
              handleTogglePin()
            }}
            aria-label={block.isPinned ? 'Unpin' : 'Pin'}
            title={block.isPinned ? 'Unpin thinking block' : 'Pin thinking block'}
          >
            {block.isPinned ? (
              <Pin size={14} className="thinking-message-pin-icon pinned" />
            ) : (
              <PinOff size={14} className="thinking-message-pin-icon" />
            )}
          </button>
          <button
            className="thinking-message-toggle"
            onClick={(e) => {
              e.stopPropagation()
              onToggleCollapse()
            }}
            aria-label={block.isCollapsed ? 'Expand' : 'Collapse'}
          >
            {block.isCollapsed ? (
              <ChevronDown className="thinking-message-chevron" size={16} />
            ) : (
              <ChevronUp className="thinking-message-chevron" size={16} />
            )}
          </button>
        </div>
      </div>
      
      {!block.isCollapsed && (
        <div 
          ref={contentRef}
          className="thinking-message-content"
        >
          {block.content && block.content.trim().length > 0 ? (
            <div className="thinking-message-text">
              {block.content.split('\n').map((line, index) => (
                <div key={index} className="thinking-message-line">
                  {line || '\u00A0'}
                </div>
              ))}
            </div>
          ) : block.status === 'streaming' ? (
            <div className="thinking-message-placeholder">
              Анализирую запрос...
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

