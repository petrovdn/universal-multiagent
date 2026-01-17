import React from 'react'
import { IntentBlock, useChatStore } from '../store/chatStore'
import { PlanningBlock } from './PlanningBlock'
import { OperationBlock } from './OperationBlock'
import { IterationBlock } from './IterationBlock'
import { SourceCard } from './SourceCard'

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
      
      {/* Phase 2, Steps 1-2: Task decomposition visualization */}
      {block.taskDecomposition && (
        <div style={{ marginBottom: '12px', padding: '12px', backgroundColor: '#f0f7ff', borderRadius: '8px', border: '1px solid #b3d9ff' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#0066cc' }}>
            📋 План выполнения ({block.taskDecomposition.subtasks.length} подзадач)
          </div>
          
          {/* Execution groups */}
          {block.taskDecomposition.execution_groups.map((group, groupIdx) => (
            <div key={groupIdx} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                {block.taskDecomposition.group_types[groupIdx] === 'parallel' ? '⚡ Параллельно' : '→ Последовательно'}:
              </div>
              <div style={{ marginLeft: '12px' }}>
                {group.map(taskId => {
                  const subtask = block.taskDecomposition.subtasks.find(st => st.task_id === taskId)
                  if (!subtask) return null
                  return (
                    <div key={taskId} style={{ fontSize: '13px', marginBottom: '4px', padding: '4px 8px', backgroundColor: 'white', borderRadius: '4px' }}>
                      {subtask.is_synthesis ? '🔄' : '📌'} {subtask.description}
                      {subtask.dependencies.length > 0 && (
                        <span style={{ fontSize: '11px', color: '#999', marginLeft: '8px' }}>
                          (зависит от {subtask.dependencies.length})
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
      
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
          {/* Phase 1.1: Tool explanations (Cursor-style) */}
          {block.toolExplanations && block.toolExplanations.length > 0 && (
            <div style={{ marginBottom: '12px', padding: '8px 12px', backgroundColor: '#f5f5f5', borderRadius: '6px', fontSize: '14px' }}>
              {block.toolExplanations.map((explanation, idx) => (
                <div key={idx} style={{ marginBottom: idx < block.toolExplanations.length - 1 ? '6px' : '0' }}>
                  <span style={{ color: '#666', fontStyle: 'italic' }}>{explanation.explanation}</span>
                </div>
              ))}
            </div>
          )}
          
          {/* Phase 1.2: Source cards (Perplexity-style) */}
          {block.sources && block.sources.length > 0 && (
            <div style={{ marginBottom: '12px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {block.sources.map((source) => (
                <SourceCard key={source.id} source={source} />
              ))}
            </div>
          )}
          
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
