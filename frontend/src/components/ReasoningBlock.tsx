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
  const [hasEverStreamed, setHasEverStreamed] = useState(block.isStreaming)

  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReasoningBlock.tsx:render',message:'ReasoningBlock render',data:{blockId:block.id,isStreaming:block.isStreaming,isCollapsed,shouldAutoCollapse,hasAnswerBlock:!!answerBlock,contentLength:block.content.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'A,B'})}).catch(()=>{});
  }, [block.id, block.isStreaming, isCollapsed, shouldAutoCollapse, !!answerBlock, block.content.length]);
  // #endregion

  // CRITICAL: Новый reasoning блок должен всегда начинаться развернутым
  // Если блок только что начал стримиться (переход с false на true), разворачиваем его
  useEffect(() => {
    if (block.isStreaming && !hasEverStreamed) {
      // Блок только что начал стримиться - разворачиваем его
      setIsCollapsed(false)
      setHasEverStreamed(true)
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReasoningBlock.tsx:auto-expand-new',message:'Auto-expanding new reasoning block',data:{blockId:block.id},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
    } else if (block.isStreaming) {
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
        setIsCollapsed(true)
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReasoningBlock.tsx:auto-collapse',message:'Auto-collapsing reasoning block',data:{blockId:block.id,hasAnswerBlock:!!answerBlock},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
      }
    }
    setWasStreaming(block.isStreaming)
  }, [block.isStreaming, shouldAutoCollapse, wasStreaming, answerBlock])

  // Разворачивать автоматически при начале стриминга reasoning (для уже существующих блоков)
  useEffect(() => {
    if (block.isStreaming && isCollapsed && hasEverStreamed) {
      // Блок возобновил стриминг - разворачиваем его
      setIsCollapsed(false)
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ReasoningBlock.tsx:auto-expand-resume',message:'Auto-expanding resumed reasoning block',data:{blockId:block.id},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
    }
  }, [block.isStreaming, isCollapsed, hasEverStreamed, block.id])

  // Auto-scroll to bottom when content updates (only if already at bottom and not collapsed)
  useEffect(() => {
    if (contentRef.current && block.isStreaming && !isCollapsed) {
      const container = containerRef.current
      if (container) {
        const isNearBottom =
          container.scrollHeight - container.scrollTop - container.clientHeight < 50
        if (isNearBottom) {
          container.scrollTop = container.scrollHeight
        }
      }
    }
  }, [block.content, block.isStreaming, isCollapsed])

  if (!isVisible) return null

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed)
  }

  return (
    <div
      ref={containerRef}
      className={`reasoning-block reasoning-block-visible ${isCollapsed ? 'reasoning-block-collapsed' : ''}`}
    >
      <div 
        className="reasoning-block-header"
        onClick={toggleCollapse}
        style={{ cursor: 'pointer' }}
      >
        <Brain className="reasoning-block-icon" />
        <span className="reasoning-block-title">Размышление</span>
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
