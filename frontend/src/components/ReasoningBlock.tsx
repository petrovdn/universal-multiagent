import React, { useRef, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Brain, ChevronDown, ChevronUp } from 'lucide-react'
import { ReasoningBlock as ReasoningBlockType, AnswerBlock as AnswerBlockType } from '../store/chatStore'

interface ReasoningBlockProps {
  block: ReasoningBlockType
  isVisible: boolean
  shouldAutoCollapse?: boolean // Автоматически сворачивать, если есть answer
  answerBlock?: AnswerBlockType | null // Состояние answer блока для правильного сворачивания
}

export function ReasoningBlock({ block, isVisible, shouldAutoCollapse = false, answerBlock = null }: ReasoningBlockProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // CRITICAL: For ReAct blocks, always start expanded
  const isReActBlock = block.content && (
    block.content.includes('ReAct') || 
    block.content.includes('Итерация') || 
    block.content.includes('🔄') ||
    block.content.includes('react-reasoning')
  )
  
  // Start expanded for ReAct blocks, collapsed for others
  const [isCollapsed, setIsCollapsed] = useState(!isReActBlock)
  const [wasStreaming, setWasStreaming] = useState(block.isStreaming)
  const [hasEverStreamed, setHasEverStreamed] = useState(block.isStreaming)// CRITICAL: Новый reasoning блок должен всегда начинаться развернутым
  // Если блок только что начал стримиться (переход с false на true), разворачиваем его
  useEffect(() => {
    if (block.isStreaming && !hasEverStreamed) {
      // Блок только что начал стримиться - разворачиваем его
      setIsCollapsed(false)
      setHasEverStreamed(true)} else if (block.isStreaming) {
      setHasEverStreamed(true)
    }
  }, [block.isStreaming, block.id, hasEverStreamed])

  // Автоматически сворачивать после завершения стриминга
  // Логика: сворачиваем когда reasoning завершен (isStreaming = false)
  // Если есть answer в паре (shouldAutoCollapse = true), сворачиваем сразу
  // Иначе сворачиваем всегда после завершения стриминга
  // BUT: For ReAct mode, don't auto-collapse reasoning blocks (they contain the full reasoning trail)
  useEffect(() => {
    if (wasStreaming && !block.isStreaming) {
      // Стриминг завершен - сворачиваем блок
      // BUT: Don't auto-collapse if this is a ReAct reasoning block (contains "ReAct" or "Итерация" in content)
      const isReActBlock = block.content && (
        block.content.includes('ReAct') || 
        block.content.includes('Итерация') || 
        block.content.includes('🔄') ||
        block.content.includes('react-reasoning')
      )
      
      if (isReActBlock) {
        // ReAct reasoning blocks should stay expanded to show the full reasoning trail
        console.log('[ReasoningBlock] ReAct block detected, keeping expanded', { blockId: block.id })
        setIsCollapsed(false)
      } else if (shouldAutoCollapse) {
        // Если есть answer в паре, проверяем, что answer блок существует
        if (answerBlock !== null) {
          setIsCollapsed(true)
        }
      } else {
        // Нет answer в паре - сворачиваем всегда после завершения стриминга
        setIsCollapsed(true)
      }
    }
    setWasStreaming(block.isStreaming)
  }, [block.isStreaming, shouldAutoCollapse, wasStreaming, answerBlock, block.id, block.content])

  // Разворачивать автоматически при начале стриминга reasoning (для уже существующих блоков)
  useEffect(() => {
    if (block.isStreaming && isCollapsed && hasEverStreamed) {
      // Блок возобновил стриминг - разворачиваем его
      setIsCollapsed(false)}
  }, [block.isStreaming, isCollapsed, hasEverStreamed, block.id])

  // Auto-scroll to bottom when content updates (scroll inside contentRef, not containerRef)
  // Note: Content is always rendered (even when collapsed) to preserve all streaming content
  useEffect(() => {
    if (contentRef.current && block.isStreaming && !isCollapsed) {
      // contentRef is the scrollable element with overflow-y: auto
      const scrollableElement = contentRef.current
      // Always scroll to bottom when streaming (show latest content)
      scrollableElement.scrollTop = scrollableElement.scrollHeight
    }
  }, [block.content, block.isStreaming, isCollapsed])

  if (!isVisible) {
    console.log('[ReasoningBlock] Not visible, returning null', { blockId: block.id })
    return null
  }

  console.log('[ReasoningBlock] Rendering', {
    blockId: block.id,
    contentLength: block.content?.length || 0,
    isStreaming: block.isStreaming,
    isCollapsed,
    hasContent: !!(block.content && block.content.trim().length > 0),
    isReActBlock,
    contentPreview: block.content?.substring(0, 200)
  })

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }
  
  // Check if element is in DOM after render
  useEffect(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      const isVisible = rect.width > 0 && rect.height > 0
      const parent = containerRef.current.parentElement
      const parentRect = parent?.getBoundingClientRect()
      const grandParent = parent?.parentElement
      const grandParentRect = grandParent?.getBoundingClientRect()
      
      console.log('[ReasoningBlock] DOM check', {
        blockId: block.id,
        isInDOM: !!containerRef.current,
        width: rect.width,
        height: rect.height,
        isVisible,
        computedDisplay: window.getComputedStyle(containerRef.current).display,
        computedVisibility: window.getComputedStyle(containerRef.current).visibility,
        parentClassName: parent?.className,
        parentWidth: parentRect?.width,
        parentHeight: parentRect?.height,
        grandParentClassName: grandParent?.className,
        grandParentWidth: grandParentRect?.width,
        grandParentHeight: grandParentRect?.height
      })
    }
  }, [block.id, block.content, isCollapsed])
  
  return (
    <div
      ref={containerRef}
      className={`reasoning-block reasoning-block-visible ${isCollapsed ? 'reasoning-block-collapsed' : ''} ${block.isStreaming ? 'reasoning-block-streaming' : ''}`}
      data-block-id={block.id}
      data-is-collapsed={isCollapsed}
      data-is-streaming={block.isStreaming}
    >
      <div 
        className="reasoning-block-header"
        onClick={toggleCollapse}
        style={{ cursor: 'pointer' }}
      >
        <Brain className="reasoning-block-icon" />
        <span className="reasoning-block-title">думаю...</span>
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
        {block.content && block.content.trim().length > 0 ? (
          <div className="prose max-w-none prose-sm">
            {(() => {
              try {
                return (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {block.content}
                  </ReactMarkdown>
                )
              } catch (error) {
                console.error('[ReasoningBlock] ReactMarkdown error:', error, { blockId: block.id, contentPreview: block.content.substring(0, 200) })
                // Fallback to plain text if markdown fails
                return <div style={{ whiteSpace: 'pre-wrap' }}>{block.content}</div>
              }
            })()}
          </div>
        ) : (
          block.isStreaming ? 'Анализирую запрос...' : ''
        )}
      </div>
    </div>
  )
}
