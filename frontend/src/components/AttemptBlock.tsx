import React, { useRef, useEffect, useState } from 'react'
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react'

interface AttemptBlockProps {
  id: string
  number: string
  title: string
  content: string
  isStreaming: boolean
  isVisible: boolean
}

export function AttemptBlock({ id, number, title, content, isStreaming, isVisible }: AttemptBlockProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [wasStreaming, setWasStreaming] = useState(isStreaming)
  const [hasEverStreamed, setHasEverStreamed] = useState(isStreaming)
  const lastContentUpdateRef = useRef<number>(Date.now())
  const collapseTimeoutRef = useRef<number | null>(null)

  // CRITICAL: Новый блок попытки должен всегда начинаться развернутым
  // Если блок только что начал стримиться (переход с false на true), разворачиваем его
  useEffect(() => {
    if (isStreaming && !hasEverStreamed) {
      // Блок только что начал стримиться - разворачиваем его
      setIsCollapsed(false)
      setHasEverStreamed(true)
    } else if (isStreaming) {
      setHasEverStreamed(true)
    }
  }, [isStreaming, id, hasEverStreamed])

  // Отслеживать обновления контента
  useEffect(() => {
    lastContentUpdateRef.current = Date.now()
    // Отменяем предыдущий таймер сворачивания, если контент обновился
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current)
      collapseTimeoutRef.current = null
    }
  }, [content])

  // Автоматически сворачивать после завершения стриминга с задержкой
  // Это дает время последним чанкам контента обновиться
  useEffect(() => {
    if (wasStreaming && !isStreaming) {
      // Стриминг завершен - планируем сворачивание с задержкой
      // Это дает время последним чанкам контента обновиться перед сворачиванием
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current)
      }
      collapseTimeoutRef.current = setTimeout(() => {
        // Проверяем, что контент не обновлялся недавно (в течение последних 500ms)
        const timeSinceLastUpdate = Date.now() - lastContentUpdateRef.current
        if (timeSinceLastUpdate >= 500) {
          setIsCollapsed(true)
        } else {
          // Контент обновился недавно - переносим сворачивание еще на 500ms
          collapseTimeoutRef.current = setTimeout(() => {
            setIsCollapsed(true)
          }, 500)
        }
      }, 1000) // Задержка 1 секунда перед сворачиванием
    } else if (isStreaming) {
      // Стриминг возобновился - отменяем сворачивание
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current)
        collapseTimeoutRef.current = null
      }
    }
    setWasStreaming(isStreaming)
    
    // Cleanup timeout on unmount
    return () => {
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current)
      }
    }
  }, [isStreaming, wasStreaming, id, content])

  // Разворачивать автоматически при начале стриминга (для уже существующих блоков)
  useEffect(() => {
    if (isStreaming && isCollapsed && hasEverStreamed) {
      // Блок возобновил стриминг - разворачиваем его
      setIsCollapsed(false)
    }
  }, [isStreaming, isCollapsed, hasEverStreamed, id])

  // Auto-scroll to bottom when content updates (scroll inside contentRef, not containerRef)
  // Note: Content is always rendered (even when collapsed) to preserve all streaming content
  useEffect(() => {
    if (contentRef.current && isStreaming && !isCollapsed) {
      // contentRef is the scrollable element with overflow-y: auto
      const scrollableElement = contentRef.current
      // Always scroll to bottom when streaming (show latest content)
      scrollableElement.scrollTop = scrollableElement.scrollHeight
    }
  }, [content, isStreaming, isCollapsed])

  if (!isVisible) return null

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }

  return (
    <div
      ref={containerRef}
      className={`reasoning-block reasoning-block-visible ${isCollapsed ? 'reasoning-block-collapsed' : ''} ${isStreaming ? 'reasoning-block-streaming' : ''}`}
    >
      <div 
        className="reasoning-block-header"
        onClick={toggleCollapse}
        style={{ cursor: 'pointer' }}
      >
        <Loader2 className="reasoning-block-icon" style={{ width: '12px', height: '12px' }} />
        <span className="reasoning-block-title">Попытка {number}: {title}</span>
        {isStreaming && (
          <span className="reasoning-block-streaming-indicator" />
        )}
        <button
          className="reasoning-block-toggle"
          onClick={(e) => {
            e.stopPropagation()
            toggleCollapse()
          }}
          aria-label={isCollapsed ? 'Развернуть' : 'Свернуть'}
        >
          {isCollapsed ? (
            <ChevronDown className="reasoning-block-chevron" />
          ) : (
            <ChevronUp className="reasoning-block-chevron" />
          )}
        </button>
      </div>
      {/* Always render content to preserve all streaming text, CSS hides it when collapsed */}
      <div ref={contentRef} className="reasoning-block-content">
        {content || (isStreaming ? 'Выполнение попытки...' : '')}
      </div>
    </div>
  )
}

