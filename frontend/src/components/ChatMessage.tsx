import React, { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Brain } from 'lucide-react'
import { AssistantMessage, useChatStore } from '../store/chatStore'
import { ReasoningBlock } from './ReasoningBlock'
import { CollapsibleBlock } from './CollapsibleBlock'
import { AnswerBlock } from './AnswerBlock'
import { PlanBlock } from './PlanBlock'
import { StepProgress } from './StepProgress'

interface ChatMessageProps {
  message: AssistantMessage
}

// Тип для reasoning-answer пары (подход B как в Cursor)
type ReasoningAnswerPair = {
  reasoning: { blockId: string; index: number } | null
  answer: { blockId: string; index: number } | null
  timestamp: number
  pairIndex: number
}

export function ChatMessage({ message }: ChatMessageProps) {
  // Note: workflowPlan is no longer used here as workflows are now per user message

  // Группируем reasoning и answer блоки в пары (подход B) - улучшенный алгоритм
  const reasoningAnswerPairs = useMemo<ReasoningAnswerPair[]>(() => {
    const reasoningTimestamps = message.reasoningBlocks.map((b, i) => ({
      index: i,
      id: b.id,
      timestamp: b.timestamp,
      timestampMs: new Date(b.timestamp).getTime(),
      isStreaming: b.isStreaming,
    }))
    const answerTimestamps = message.answerBlocks.map((b, i) => ({
      index: i,
      id: b.id,
      timestamp: b.timestamp,
      timestampMs: new Date(b.timestamp).getTime(),
      isStreaming: b.isStreaming,
    }))
    
    // Создаем массив всех элементов с их типами, timestamp и индексом для стабильной сортировки
    const allItems: Array<{
      type: 'reasoning' | 'answer'
      blockId: string
      index: number
      timestamp: number
      originalIndex: number // Для стабильной сортировки при одинаковых timestamp
    }> = []
    
    // Добавляем все reasoning блоки
    message.reasoningBlocks.forEach((block, index) => {
      allItems.push({
        type: 'reasoning',
        blockId: block.id,
        index,
        timestamp: new Date(block.timestamp).getTime(),
        originalIndex: index, // Сохраняем оригинальный индекс
      })
    })
    
    // Добавляем все answer блоки
    message.answerBlocks.forEach((block, index) => {
      allItems.push({
        type: 'answer',
        blockId: block.id,
        index,
        timestamp: new Date(block.timestamp).getTime(),
        originalIndex: index + 10000, // Смещаем индекс answer блоков для различия
      })
    })
    
    // Сортируем по timestamp, затем по originalIndex для стабильности
    allItems.sort((a, b) => {
      if (a.timestamp !== b.timestamp) {
        return a.timestamp - b.timestamp
      }
      return a.originalIndex - b.originalIndex
    })
    
    // Группируем в пары: reasoning → answer (улучшенный алгоритм)
    const pairs: ReasoningAnswerPair[] = []
    let pairIndex = 0
    const usedAnswerIndices = new Set<number>()
    
    // Проходим по всем элементам и создаем пары
    for (let i = 0; i < allItems.length; i++) {
      const item = allItems[i]
      
      if (item.type === 'reasoning') {
        // Создаем новую пару с reasoning
        const pair: ReasoningAnswerPair = {
          reasoning: { blockId: item.blockId, index: item.index },
          answer: null,
          timestamp: item.timestamp,
          pairIndex: pairIndex++,
        }
        
        // Ищем ближайший следующий answer блок (не использованный)
        // Ищем только среди следующих элементов, чтобы гарантировать правильный порядок
        // ВАЖНО: Берем первый answer блок после reasoning, даже если его timestamp меньше
        // (это может произойти из-за асинхронности создания блоков)
        for (let j = i + 1; j < allItems.length; j++) {
          const nextItem = allItems[j]
          if (nextItem.type === 'answer' && !usedAnswerIndices.has(nextItem.index)) {
            // Найден ближайший answer блок после reasoning - создаем пару
            // Не проверяем timestamp, так как порядок в allItems уже правильный
            pair.answer = { blockId: nextItem.blockId, index: nextItem.index }
            usedAnswerIndices.add(nextItem.index)
            break // Берем только первый подходящий answer
          }
        }
        
        pairs.push(pair)
      }
    }
    
    // Обрабатываем оставшиеся answer блоки (которые не были привязаны к reasoning)
    for (let i = 0; i < allItems.length; i++) {
      const item = allItems[i]
      if (item.type === 'answer' && !usedAnswerIndices.has(item.index)) {
        // Создаем пару только с answer (без reasoning)
        pairs.push({
          reasoning: null,
          answer: { blockId: item.blockId, index: item.index },
          timestamp: item.timestamp,
          pairIndex: pairIndex++,
        })
        usedAnswerIndices.add(item.index)
      }
    }
    
    // Сортируем пары по timestamp (reasoning или answer, если reasoning нет)
    // Используем вторичный ключ для стабильности
    pairs.sort((a, b) => {
      if (a.timestamp !== b.timestamp) {
        return a.timestamp - b.timestamp
      }
      // Если timestamp одинаковые, сортируем по pairIndex
      return a.pairIndex - b.pairIndex
    })
    
    return pairs
  }, [message.reasoningBlocks, message.answerBlocks])

  // Если нет пар, возвращаем null вместо пустого div
  if (reasoningAnswerPairs.length === 0) {
    console.warn('[ChatMessage] No reasoning-answer pairs, returning null', {
      messageId: message.id,
      reasoningBlocksCount: message.reasoningBlocks.length,
      answerBlocksCount: message.answerBlocks.length,
      reasoningBlocks: message.reasoningBlocks.map(b => ({ id: b.id, contentLength: b.content?.length || 0, isStreaming: b.isStreaming })),
      answerBlocks: message.answerBlocks.map(b => ({ id: b.id, contentLength: b.content?.length || 0, isStreaming: b.isStreaming }))
    })
    return null
  }

  // Проверяем, есть ли контент в парах
  const allPairsHaveContent = reasoningAnswerPairs.every(pair => {
    const hasReasoningContent = pair.reasoning ? (message.reasoningBlocks[pair.reasoning.index]?.content?.trim().length || 0) > 0 : true
    const hasAnswerContent = pair.answer ? (message.answerBlocks[pair.answer.index]?.content?.trim().length || 0) > 0 : true
    return hasReasoningContent || hasAnswerContent
  })
  
  // Если все пары пустые, не рендерим div
  if (!allPairsHaveContent) {
    return null
  }
  
  return (
    <div className="chat-message" data-message-id={message.id}>
      {reasoningAnswerPairs.map((pair) => {
        const reasoningBlock = pair.reasoning ? message.reasoningBlocks[pair.reasoning.index] : null
        const answerBlock = pair.answer ? message.answerBlocks[pair.answer.index] : null
        
        return (
          <div key={`pair-${pair.pairIndex}`} className="reasoning-answer-pair">
            {/* CRITICAL: Reasoning всегда идет ПЕРВЫМ в паре, независимо от timestamp */}
            {pair.reasoning && (() => {
              const reasoningBlock = message.reasoningBlocks[pair.reasoning.index]
              // CRITICAL FIX: Don't render ReasoningBlock if content is empty AND not streaming
              // ReasoningBlock will show "Анализирую запрос..." only if isStreaming=true, but we should
              // not render it at all if there's no content and it's not streaming
              const hasContent = reasoningBlock.content && reasoningBlock.content.trim().length > 0
              const shouldRender = hasContent || reasoningBlock.isStreaming
              
              console.log('[ChatMessage] Rendering reasoning block', {
                blockId: reasoningBlock.id,
                hasContent,
                isStreaming: reasoningBlock.isStreaming,
                shouldRender,
                contentLength: reasoningBlock.content?.length || 0,
                contentPreview: reasoningBlock.content?.substring(0, 200)
              })
              
              // CRITICAL FIX: Don't render if no content AND not streaming (prevents empty blocks)
              if (!shouldRender) {
                console.log('[ChatMessage] Skipping reasoning block - no content and not streaming', { blockId: reasoningBlock.id })
                return null
              }
              
              // Use CollapsibleBlock (same as Plan mode) instead of ReasoningBlock for better compatibility
              // Check if this is a ReAct block (contains ReAct markers)
              const isReActBlock = reasoningBlock.content && (
                reasoningBlock.content.includes('ReAct') || 
                reasoningBlock.content.includes('Итерация') || 
                reasoningBlock.content.includes('🔄') ||
                reasoningBlock.id.includes('react-reasoning')
              )
              
              // For ReAct blocks, use CollapsibleBlock (same as Plan mode)
              if (isReActBlock) {
                return (
                  <CollapsibleBlock
                    key={`reasoning-${pair.reasoning.blockId}`}
                    title="думаю..."
                    icon={<Brain className="reasoning-block-icon" />}
                    isStreaming={reasoningBlock.isStreaming}
                    isCollapsed={false} // ReAct blocks start expanded
                    autoCollapse={false} // Don't auto-collapse ReAct blocks
                    alwaysOpen={false}
                    className="react-reasoning-block"
                  >
                    <div className="prose max-w-none prose-sm">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {reasoningBlock.content || (reasoningBlock.isStreaming ? 'Анализирую запрос...' : '')}
                      </ReactMarkdown>
                    </div>
                  </CollapsibleBlock>
                )
              }
              
              // For non-ReAct blocks, use ReasoningBlock (backward compatibility)
              return (
                <ReasoningBlock
                  key={`reasoning-${pair.reasoning.blockId}`}
                  block={reasoningBlock}
                  isVisible={true}
                  shouldAutoCollapse={!!pair.answer} // Автоматически сворачивать, если есть answer
                  answerBlock={pair.answer ? message.answerBlocks[pair.answer.index] : null} // Передаем состояние answer блока
                />
              )
            })()}
            {pair.answer && (() => {
              const answerBlock = message.answerBlocks[pair.answer.index]
              const hasContent = answerBlock.content && answerBlock.content.trim().length > 0
              if (!hasContent) {
                return null
              }
              return (
                <AnswerBlock
                  key={`answer-${pair.answer.blockId}`}
                  block={answerBlock}
                />
              )
            })()}
          </div>
        )
      })}
    </div>
  )
}
