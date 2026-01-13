import React from 'react'
import { IntentBlock, useChatStore } from '../store/chatStore'
import { PlanningBlock } from './PlanningBlock'
import { OperationBlock } from './OperationBlock'
import { IterationBlock } from './IterationBlock'

interface IntentMessageProps {
  block: IntentBlock
  workflowId: string
  stepNumber?: number // Опциональный: если undefined, не показываем номер шага
  onToggleCollapse: () => void
  onTogglePlanningCollapse?: () => void
  onToggleExecutingCollapse?: () => void
}

export function IntentMessage({ 
  block,
  workflowId,
  stepNumber,
  onToggleCollapse,
  onTogglePlanningCollapse,
  onToggleExecutingCollapse 
}: IntentMessageProps) {
  
  const isPlanning = block.phase === 'planning'
  const isExecuting = block.phase === 'executing'
  const isCompleted = block.phase === 'completed'
  const hasThinkingText = !!block.thinkingText
  const hasDetails = block.details.length > 0
  const hasOperations = block.operations && Object.keys(block.operations).length > 0
  const hasIterations = block.iterations && block.iterations.length > 0

  // НОВЫЙ ФОРМАТ: Если есть iterations, используем их вместо старых секций
  // Показывать секцию "Планирую" если есть thinking или в фазе planning (только если НЕТ iterations)
  const showPlanningSection = !hasIterations && (hasThinkingText || isPlanning)
  // Показывать секцию "Выполняю" если есть operations, details или в фазе executing/completed (только если НЕТ iterations)
  // ВАЖНО: Если есть операции, игнорируем старые details, чтобы избежать дублирования
  const showExecutingSection = !hasIterations && (hasOperations || (!hasOperations && hasDetails) || isExecuting || isCompleted)
  
  // Вычисляем оставшееся время для таймера
  const estimatedSeconds = block.estimatedSec || 10
  const elapsedSeconds = block.elapsedSec || 0
  const remainingTime = Math.max(0, estimatedSeconds - elapsedSeconds)

  return (
    <div className={`intent-message ${isCompleted ? 'intent-message-completed' : ''}`} style={{ maxWidth: '900px', width: '100%', margin: '0 auto', padding: '0' }}>
      {/* Заголовок intent - крупный жирный */}
      <div className="step-header" style={{ marginBottom: '12px', paddingLeft: '0', paddingRight: '0' }}>
        {stepNumber !== undefined ? `Шаг ${stepNumber}: ${block.intent}` : block.intent}
      </div>
      
      {/* План итерации убран - теперь отображается внутри iterations */}
      
      {/* Фаза 1: Планирую - используем PlanningBlock */}
      {showPlanningSection && (
        <div style={{ marginBottom: '8px' }}>
          <PlanningBlock
            content={block.thinkingText || ''}
            isStreaming={isPlanning}
            estimatedSeconds={estimatedSeconds}
            initialCollapsed={block.planningCollapsed}
            onCollapseChange={(collapsed) => {
              // Только если состояние действительно изменилось
              if (onTogglePlanningCollapse && collapsed !== block.planningCollapsed) {
                onTogglePlanningCollapse()
              }
            }}
          />
        </div>
      )}
      
      {/* Фаза 2: Выполняю - операции и детали */}
      {showExecutingSection && (
        <div style={{ marginTop: '8px' }}>
          {/* Новый формат: операции со стримингом */}
          {hasOperations && (
            Object.values(block.operations).map((operation) => (
              <OperationBlock
                key={operation.id}
                operation={operation}
                onToggleCollapse={() => {
                  useChatStore.getState().toggleOperationCollapse(workflowId, block.id, operation.id)
                }}
              />
            ))
          )}
          
          {/* Старый формат: детали (fallback, если нет операций) */}
          {!hasOperations && hasDetails && (
            <div className="execution-log">
              {block.details.map((detail, i) => {
                const isLast = i === block.details.length - 1
                const isPending = isExecuting && isLast
                const isDone = !isExecuting || !isLast
                
                return (
                  <div key={i} className="execution-log-item">
                    <span className={`log-icon ${isDone ? 'done' : 'pending'}`}>
                      {isDone ? '✓' : '○'}
                    </span>
                    <div className="log-text-container">
                      <span className={`log-text-title ${isPending ? 'log-text-pending' : ''}`}>
                        {detail.description}
                        {isPending && (
                          <span className="log-text-dots">
                            <span className="log-dot-1">.</span>
                            <span className="log-dot-2">.</span>
                            <span className="log-dot-3">.</span>
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          
          {isExecuting && !hasOperations && !hasDetails && (
            <div className="execution-log-item">
              <span className="log-icon pending">○</span>
              <span className="log-text log-text-pending">
                Выполняю действия
                <span className="log-text-dots">
                  <span className="log-dot-1">.</span>
                  <span className="log-dot-2">.</span>
                  <span className="log-dot-3">.</span>
                </span>
              </span>
            </div>
          )}
        </div>
      )}
      
      {/* НОВЫЙ ФОРМАТ: Итерации ReAct цикла (Think → Summary → Act → Result) */}
      {hasIterations && (
        <div className="iterations-container" style={{ marginTop: '8px' }}>
          {block.iterations.map((iteration) => {
            // Находим связанную операцию, если есть
            const linkedOperation = iteration.operationId 
              ? block.operations[iteration.operationId]
              : undefined
              
            return (
              <IterationBlock
                key={iteration.id}
                iteration={iteration}
                operation={linkedOperation}
                onToggleThinkingCollapse={() => {
                  // Toggle thinking collapse для итерации
                  const store = useChatStore.getState()
                  const existingIntents = store.intentBlocks[workflowId] || []
                  const updatedIntents = existingIntents.map(intent => {
                    if (intent.id === block.id) {
                      const updatedIterations = intent.iterations.map(iter => {
                        if (iter.id === iteration.id) {
                          return {
                            ...iter,
                            thinking: {
                              ...iter.thinking,
                              isCollapsed: !iter.thinking.isCollapsed,
                            },
                          }
                        }
                        return iter
                      })
                      return { ...intent, iterations: updatedIterations }
                    }
                    return intent
                  })
                  useChatStore.setState({
                    intentBlocks: {
                      ...store.intentBlocks,
                      [workflowId]: updatedIntents,
                    },
                  })
                }}
                onToggleOperationCollapse={linkedOperation ? () => {
                  useChatStore.getState().toggleOperationCollapse(workflowId, block.id, linkedOperation.id)
                } : undefined}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
