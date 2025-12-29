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
  const workflowPlan = useChatStore((state) => state.workflowPlan)
  
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
  
  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:render',message:'ChatMessage render',data:{messageId:message.id,reasoningBlocksCount:message.reasoningBlocks.length,answerBlocksCount:message.answerBlocks.length,hasReasoningBlocks:message.reasoningBlocks.length>0,hasAnswerBlocks:message.answerBlocks.length>0,isComplete:message.isComplete},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,C'})}).catch(()=>{});
  }, [message.id, message.reasoningBlocks.length, message.answerBlocks.length, message.isComplete]);
  // #endregion

  // Группируем reasoning и answer блоки в пары (подход B) - улучшенный алгоритм
  const reasoningAnswerPairs = useMemo<ReasoningAnswerPair[]>(() => {
    // #region agent log
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
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:grouping-start',message:'Starting block grouping',data:{messageId:message.id,reasoningBlocksCount:message.reasoningBlocks.length,answerBlocksCount:message.answerBlocks.length,reasoningTimestamps,answerTimestamps},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D,E'})}).catch(()=>{});
    // #endregion
    
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
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:pair-created',message:'Created reasoning-answer pair',data:{pairIndex:pair.pairIndex,reasoningTimestamp:item.timestamp,answerTimestamp:nextItem.timestamp,timestampDiff:nextItem.timestamp - item.timestamp},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'D'})}).catch(()=>{});
            // #endregion
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
    
    // #region agent log
    const sortedPairs = pairs.map((p, idx) => ({
      position: idx,
      pairIndex: p.pairIndex,
      timestamp: p.timestamp,
      hasReasoning: !!p.reasoning,
      hasAnswer: !!p.answer,
      reasoningId: p.reasoning?.blockId,
      answerId: p.answer?.blockId,
    }))
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:grouping-complete',message:'Block grouping complete',data:{totalPairs:pairs.length,sortedPairs},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'D,E'})}).catch(()=>{});
    // #endregion
    
    return pairs
  }, [message.reasoningBlocks, message.answerBlocks])

  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:after-grouping',message:'After reasoningAnswerPairs grouping',data:{messageId:message.id,reasoningAnswerPairsCount:reasoningAnswerPairs.length,willRenderEmptyDiv:reasoningAnswerPairs.length===0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  }, [message.id, reasoningAnswerPairs.length]);
  // #endregion

  // Если нет пар, возвращаем null вместо пустого div
  if (reasoningAnswerPairs.length === 0) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:return-null',message:'Returning null - no pairs',data:{messageId:message.id,reasoningBlocksCount:message.reasoningBlocks.length,answerBlocksCount:message.answerBlocks.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    return null
  }

  return (
    <div className="chat-message">
      {reasoningAnswerPairs.map((pair) => {
        // #region agent log
        const reasoningBlock = pair.reasoning ? message.reasoningBlocks[pair.reasoning.index] : null
        const answerBlock = pair.answer ? message.answerBlocks[pair.answer.index] : null
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:render-pair',message:'Rendering pair',data:{pairIndex:pair.pairIndex,hasReasoning:!!pair.reasoning,hasAnswer:!!pair.answer,reasoningTimestamp:reasoningBlock?.timestamp,reasoningTimestampMs:reasoningBlock ? new Date(reasoningBlock.timestamp).getTime() : null,answerTimestamp:answerBlock?.timestamp,answerTimestampMs:answerBlock ? new Date(answerBlock.timestamp).getTime() : null,reasoningIsStreaming:reasoningBlock?.isStreaming,answerIsStreaming:answerBlock?.isStreaming},timestamp:Date.now(),sessionId:'debug-session',runId:'run4',hypothesisId:'D,E'})}).catch(()=>{});
        // #endregion
        
        return (
          <div key={`pair-${pair.pairIndex}`} className="reasoning-answer-pair">
            {/* CRITICAL: Reasoning всегда идет ПЕРВЫМ в паре, независимо от timestamp */}
            {pair.reasoning && (() => {
              const reasoningBlock = message.reasoningBlocks[pair.reasoning.index]
              // Не показывать ReasoningBlock, если content пустой И плана еще нет
              // Это предотвращает показ серого блока "Анализирую запрос..." до появления плана
              const hasContent = reasoningBlock.content && reasoningBlock.content.trim().length > 0
              const hasPlan = workflowPlan && (
                workflowPlan.planThinking || 
                workflowPlan.planThinkingIsStreaming || 
                (workflowPlan.plan && workflowPlan.plan.trim()) ||
                (workflowPlan.steps && workflowPlan.steps.length > 0)
              )
              
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatMessage.tsx:should-render-reasoning',message:'Checking if should render ReasoningBlock',data:{messageId:message.id,reasoningBlockId:reasoningBlock.id,hasContent,hasPlan,contentLength:reasoningBlock.content?.length||0,isStreaming:reasoningBlock.isStreaming,willRender:hasContent||hasPlan},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
              // #endregion
              
              // Рендерим только если есть контент ИЛИ есть план
              if (!hasContent && !hasPlan) {
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
            {pair.answer && (
              <AnswerBlock
                key={`answer-${pair.answer.blockId}`}
                block={message.answerBlocks[pair.answer.index]}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
