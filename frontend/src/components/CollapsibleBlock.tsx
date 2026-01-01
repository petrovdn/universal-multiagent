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
      window.dispatchEvent(event)
      
      // #region agent log
      if (containerRef.current) {
        const el = containerRef.current
        const style = window.getComputedStyle(el)
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'CollapsibleBlock.tsx:43',message:'Auto-collapsing block',data:{title,className,offsetTop:el.offsetTop,offsetHeight:el.offsetHeight,getBoundingClientRect:{top:el.getBoundingClientRect().top,bottom:el.getBoundingClientRect().bottom},fontSize:style.fontSize},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'H3'})}).catch(()=>{});
      }
      // #endregion
      
      // Даем время на установку флага перед изменением состояния
      requestAnimationFrame(() => {
        setIsCollapsed(true)
      })
      
      // #region agent log
      setTimeout(() => {
        if (containerRef.current) {
          const el = containerRef.current
          const style = window.getComputedStyle(el)
          fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'CollapsibleBlock.tsx:50',message:'Block collapsed - after state change',data:{title,className,offsetTop:el.offsetTop,offsetHeight:el.offsetHeight,getBoundingClientRect:{top:el.getBoundingClientRect().top,bottom:el.getBoundingClientRect().bottom},fontSize:style.fontSize},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'H3'})}).catch(()=>{});
        }
        
        // Сигнализируем об окончании сворачивания через дополнительную задержку
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent('collapsibleBlockCollapsed', { detail: { title, className } }))
        }, 150)
      }, 100)
      // #endregion
    }
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

  // #region agent log
  useEffect(() => {
    if (containerRef.current) {
      const el = containerRef.current
      const style = window.getComputedStyle(el)
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'CollapsibleBlock.tsx:70',message:'CollapsibleBlock rendered',data:{title,className,isCollapsed,isStreaming,offsetTop:el.offsetTop,offsetHeight:el.offsetHeight,getBoundingClientRect:{top:el.getBoundingClientRect().top},fontSize:style.fontSize,computedClasses:el.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'H1'})}).catch(()=>{});
    }
  }, [isCollapsed, isStreaming, title, className])
  // #endregion
  
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



