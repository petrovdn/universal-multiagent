import React, { useRef, useEffect, useState } from 'react'
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
  const [isCollapsed, setIsCollapsed] = useState(false)
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

  // Автоматически сворачивать после завершения стриминга, если есть answer
  // Улучшенная логика: сворачиваем только когда:
  // 1. Reasoning завершен (isStreaming = false)
  // 2. Есть answer в паре (shouldAutoCollapse = true)
  // 3. Answer начал стримиться или уже завершен (answerBlock.isStreaming !== undefined)
  useEffect(() => {
    if (wasStreaming && !block.isStreaming && shouldAutoCollapse) {
      // Проверяем, что answer блок существует и начал стримиться или завершен
      if (answerBlock !== null) {
        // Answer блок существует - можно сворачивать
        setIsCollapsed(true)}
    }
    setWasStreaming(block.isStreaming)
  }, [block.isStreaming, shouldAutoCollapse, wasStreaming, answerBlock])

  // Разворачивать автоматически при начале стриминга reasoning (для уже существующих блоков)
  useEffect(() => {
    if (block.isStreaming && isCollapsed && hasEverStreamed) {
      // Блок возобновил стриминг - разворачиваем его
      setIsCollapsed(false)}
  }, [block.isStreaming, isCollapsed, hasEverStreamed, block.id])

  // Auto-scroll to bottom when content updates (scroll inside contentRef, not containerRef)
  useEffect(() => {
    if (contentRef.current && block.isStreaming && !isCollapsed) {
      // contentRef is the scrollable element with overflow-y: auto
      const scrollableElement = contentRef.current
      // Always scroll to bottom when streaming (show latest content)
      scrollableElement.scrollTop = scrollableElement.scrollHeight
    }
  }, [block.content, block.isStreaming, isCollapsed])

  if (!isVisible) return null

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }

  return (
    <div
      ref={containerRef}
      className={`reasoning-block reasoning-block-visible ${isCollapsed ? 'reasoning-block-collapsed' : ''} ${block.isStreaming ? 'reasoning-block-streaming' : ''}`}
    >
      <div 
        className="reasoning-block-header"
        onClick={toggleCollapse}
        style={{ cursor: 'pointer' }}
      >
        <Brain className="reasoning-block-icon" />
        <span className="reasoning-block-title">думаю...</span>
        {block.isStreaming && (
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
      {!isCollapsed && (
        <div ref={contentRef} className="reasoning-block-content">
          {block.content || (block.isStreaming ? 'Анализирую запрос...' : '')}
        </div>
      )}
    </div>
  )
}
