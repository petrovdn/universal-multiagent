import React, { useMemo } from 'react'
import { AssistantMessage, DebugChunkType, useChatStore } from '../store/chatStore'
import { ReasoningBlock } from './ReasoningBlock'
import { AnswerBlock } from './AnswerBlock'
import { PlanBlock } from './PlanBlock'
import { StepProgress } from './StepProgress'
import { useSettingsStore } from '../store/settingsStore'

interface ChatMessageProps {
  message: AssistantMessage
}

// Colors for different chunk types in debug mode
const getChunkColor = (type: DebugChunkType): string => {
  switch (type) {
    case 'thinking':
      return '#22c55e' // green
    case 'message_chunk':
      return '#000000' // black
    case 'tool_call':
      return '#3b82f6' // blue
    case 'tool_result':
      return '#2563eb' // darker blue
    case 'error':
      return '#ef4444' // red
    case 'message_start':
      return '#6b7280' // gray
    case 'message_complete':
      return '#6b7280' // gray
    default:
      return '#000000' // black
  }
}

const getChunkTypeLabel = (type: DebugChunkType): string => {
  switch (type) {
    case 'thinking':
      return 'Ризонинг'
    case 'message_chunk':
      return 'Ответ'
    case 'tool_call':
      return 'Вызов инструмента'
    case 'tool_result':
      return 'Результат инструмента'
    case 'error':
      return 'Ошибка'
    case 'message_start':
      return 'Начало сообщения'
    case 'message_complete':
      return 'Завершение сообщения'
    default:
      return type
  }
}

// Тип для reasoning-answer пары (подход B как в Cursor)
type ReasoningAnswerPair = {
  reasoning: { blockId: string; index: number } | null
  answer: { blockId: string; index: number } | null
  timestamp: number
  pairIndex: number
}

export function ChatMessage({ message }: ChatMessageProps) {
  const { debugMode } = useSettingsStore()
  // Note: workflowPlan is no longer used here as workflows are now per user message
  
  // В отладочном режиме показываем все чанки последовательно
  if (debugMode && message.debugChunks && message.debugChunks.length > 0) {
    return (
      <div className="chat-message debug-mode">
        {message.debugChunks.map((chunk) => (
          <div
            key={chunk.id}
            className="debug-chunk"
            style={{
              color: getChunkColor(chunk.type),
              borderLeft: `3px solid ${getChunkColor(chunk.type)}`,
              padding: '8px 12px',
              marginBottom: '4px',
              backgroundColor: 'rgba(0, 0, 0, 0.02)',
              borderRadius: '4px',
            }}
          >
            <div
              style={{
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginBottom: '4px',
                opacity: 0.7,
              }}
            >
              {getChunkTypeLabel(chunk.type)}
            </div>
            <div
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontSize: '14px',
              }}
            >
              {chunk.content}
            </div>
            {chunk.metadata && Object.keys(chunk.metadata).length > 0 && (
              <details style={{ marginTop: '8px', fontSize: '12px', opacity: 0.6 }}>
                <summary style={{ cursor: 'pointer' }}>Метаданные</summary>
                <pre style={{ marginTop: '4px', overflow: 'auto', maxHeight: '200px' }}>
                  {JSON.stringify(chunk.metadata, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    )
  }
  

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
    <div className="chat-message">
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
              
              // CRITICAL FIX: Don't render if no content AND not streaming (prevents empty blocks)
              if (!shouldRender) {
                return null
              }
              
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
