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
  ref?: React.Ref<HTMLDivElement> // Добавляем ref для логирования
}

export const CollapsibleBlock = React.forwardRef<HTMLDivElement, Omit<CollapsibleBlockProps, 'ref'>>(({
  title,
  icon,
  isStreaming = false,
  isCollapsed: initialCollapsed = false,
  autoCollapse = true,
  alwaysOpen = false,
  children,
  className = '',
}, forwardedRef) => {
  const contentRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed)
  const [wasStreaming, setWasStreaming] = useState(isStreaming)
  const [hasEverStreamed, setHasEverStreamed] = useState(isStreaming)
  
  // Объединяем forwardedRef с внутренним ref
  React.useImperativeHandle(forwardedRef, () => containerRef.current as HTMLDivElement)

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
      // Сигнализируем о начале сворачивания СИНХРОННО
      const event = new CustomEvent('collapsibleBlockCollapsing', { detail: { title, className } })
      window.dispatchEvent(event)      // Даем время на установку флага перед изменением состояния
      requestAnimationFrame(() => {
        setIsCollapsed(true)
      })    }
    setWasStreaming(isStreaming)
  }, [isStreaming, autoCollapse, wasStreaming, alwaysOpen, title, className])

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
      data-collapsible-block-title={title}
      data-is-collapsed={isCollapsed}
      data-is-streaming={isStreaming}
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
})



