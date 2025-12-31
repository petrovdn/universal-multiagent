import React, { useRef, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface CollapsibleBlockProps {
  title: string
  icon: React.ReactNode
  isStreaming?: boolean
  isCollapsed?: boolean
  autoCollapse?: boolean // Автоматически сворачивать после стриминга
  alwaysOpen?: boolean // Блок всегда открыт (не показывает кнопку сворачивания)
  children: React.ReactNode
  className?: string
}

export function CollapsibleBlock({
  title,
  icon,
  isStreaming = false,
  isCollapsed: initialCollapsed = false,
  autoCollapse = true,
  alwaysOpen = false,
  children,
  className = '',
}: CollapsibleBlockProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed)
  const [wasStreaming, setWasStreaming] = useState(isStreaming)
  const [hasEverStreamed, setHasEverStreamed] = useState(isStreaming)

  // Если блок только что начал стримиться, разворачиваем его
  useEffect(() => {
    if (isStreaming && !hasEverStreamed) {
      setIsCollapsed(false)
      setHasEverStreamed(true)
    } else if (isStreaming) {
      setHasEverStreamed(true)
    }
  }, [isStreaming, hasEverStreamed])

  // Автоматически сворачивать после завершения стриминга (если autoCollapse = true)
  useEffect(() => {
    if (autoCollapse && wasStreaming && !isStreaming && !alwaysOpen) {
      setIsCollapsed(true)
    }
    setWasStreaming(isStreaming)
  }, [isStreaming, autoCollapse, wasStreaming, alwaysOpen])

  // Разворачивать автоматически при начале стриминга (для уже существующих блоков)
  useEffect(() => {
    if (isStreaming && isCollapsed && hasEverStreamed && !alwaysOpen) {
      setIsCollapsed(false)
    }
  }, [isStreaming, isCollapsed, hasEverStreamed, alwaysOpen])

  // Auto-scroll to bottom when content updates during streaming
  useEffect(() => {
    if (contentRef.current && isStreaming && !isCollapsed) {
      const scrollableElement = contentRef.current
      scrollableElement.scrollTop = scrollableElement.scrollHeight
    }
  }, [children, isStreaming, isCollapsed])

  const toggleCollapse = () => {
    if (!alwaysOpen) {
      setIsCollapsed(!isCollapsed)
    }
  }

  return (
    <div
      ref={containerRef}
      className={`reasoning-block reasoning-block-visible ${isCollapsed ? 'reasoning-block-collapsed' : ''} ${isStreaming ? 'reasoning-block-streaming' : ''} ${className}`}
    >
      <div
        className="reasoning-block-header"
        onClick={alwaysOpen ? undefined : toggleCollapse}
        style={{ cursor: alwaysOpen ? 'default' : 'pointer' }}
      >
        <div className="reasoning-block-icon-wrapper">
          {icon}
        </div>
        <span className="reasoning-block-title">{title}</span>
        {isStreaming && (
          <span className="reasoning-block-streaming-indicator" />
        )}
        {!alwaysOpen && (
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
        )}
      </div>
      {/* Always render content to preserve all streaming text, CSS hides it when collapsed */}
      <div ref={contentRef} className="reasoning-block-content">
        {children}
      </div>
    </div>
  )
}

