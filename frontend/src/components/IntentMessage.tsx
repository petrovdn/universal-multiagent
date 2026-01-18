import React from 'react'
import { IntentBlock, useChatStore } from '../store/chatStore'
import { PlanningBlock } from './PlanningBlock'
import { OperationBlock } from './OperationBlock'
import { IterationBlock } from './IterationBlock'
import { SourceCard } from './SourceCard'
import { ParallelExecutionContainer } from './ParallelExecutionContainer'

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
  const hasParallelBranches = block.parallelBranches && block.parallelBranches.length > 0
  // #region agent log
  if (hasParallelBranches || hasIterations) {
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'IntentMessage.tsx:34',message:'IntentMessage render - flags check',data:{intentId:block.id,hasParallelBranches,hasIterations,parallelBranchesCount:block.parallelBranches?.length||0,iterationsCount:block.iterations?.length||0,phase:block.phase},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
  }
  // #endregion

  // НОВЫЙ ФОРМАТ: Если есть iterations, используем их вместо старых секций
  // Показывать секцию "Планирую" если есть thinking или в фазе planning (только если НЕТ iterations и НЕТ parallelBranches)
  const showPlanningSection = !hasIterations && !hasParallelBranches && (hasThinkingText || isPlanning)
  
  // Показывать секцию "Выполняю" если есть operations, details или в фазе executing/completed (только если НЕТ iterations и НЕТ parallelBranches)
  // ВАЖНО: Если есть операции, игнорируем старые details, чтобы избежать дублирования
  const showExecutingSection = !hasIterations && !hasParallelBranches && (hasOperations || (!hasOperations && hasDetails) || isExecuting || isCompleted)
  
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
      
      {/* Phase 2, Steps 1-2: Task decomposition visualization with parallel execution indicators */}
      {/* Скрываем при параллельном выполнении - вся информация будет в ParallelExecutionContainer */}
      {block.taskDecomposition && !hasParallelBranches && (
        <div style={{ marginBottom: '12px', padding: '12px', backgroundColor: '#f0f7ff', borderRadius: '8px', border: '1px solid #b3d9ff' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#0066cc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>📋 План выполнения</span>
            <span style={{ fontSize: '12px', fontWeight: 'normal', color: '#666' }}>
              ({block.taskDecomposition.subtasks.length} подзадач)
            </span>
            {block.taskDecomposition.execution_groups.some((_, idx) => 
              block.taskDecomposition.group_types[idx] === 'parallel'
            ) && (
              <span style={{ fontSize: '11px', padding: '2px 6px', backgroundColor: '#4CAF50', color: 'white', borderRadius: '4px', fontWeight: 'normal' }}>
                ⚡ Параллельное выполнение
              </span>
            )}
          </div>
          
          {/* Execution groups with visual indicators */}
          {block.taskDecomposition.execution_groups.map((group, groupIdx) => {
            const isParallel = block.taskDecomposition.group_types[groupIdx] === 'parallel'
            return (
              <div key={groupIdx} style={{ marginBottom: '10px', padding: '8px', backgroundColor: isParallel ? '#e8f5e9' : '#fff3e0', borderRadius: '6px', border: `1px solid ${isParallel ? '#c8e6c9' : '#ffcc80'}` }}>
                <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: isParallel ? '#2e7d32' : '#e65100', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {isParallel ? (
                    <>
                      <span>⚡ Параллельно</span>
                      <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#666' }}>
                        ({group.length} задач одновременно)
                      </span>
                    </>
                  ) : (
                    <>
                      <span>→ Последовательно</span>
                      <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#666' }}>
                        (по порядку)
                      </span>
                    </>
                  )}
                </div>
                <div style={{ marginLeft: '8px', display: 'flex', flexDirection: isParallel ? 'row' : 'column', flexWrap: isParallel ? 'wrap' : 'nowrap', gap: '4px' }}>
                  {group.map(taskId => {
                    const subtask = block.taskDecomposition.subtasks.find(st => st.task_id === taskId)
                    if (!subtask) return null
                    // Check if this subtask has a corresponding source card (to show execution status)
                    const hasSource = block.sources.some(s => s.tool_name === subtask.tool_name)
                    const sourceStatus = block.sources.find(s => s.tool_name === subtask.tool_name)?.status
                    return (
                      <div 
                        key={taskId} 
                        style={{ 
                          fontSize: '12px', 
                          marginBottom: '4px', 
                          padding: '6px 10px', 
                          backgroundColor: 'white', 
                          borderRadius: '4px',
                          border: `1px solid ${sourceStatus === 'loading' ? '#2196F3' : sourceStatus === 'completed' ? '#4CAF50' : '#e0e0e0'}`,
                          display: 'inline-block',
                          minWidth: isParallel ? '200px' : 'auto',
                          position: 'relative'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {subtask.is_synthesis ? '🔄' : '📌'}
                          <span style={{ flex: 1 }}>{subtask.description}</span>
                          {sourceStatus === 'loading' && (
                            <span style={{ fontSize: '10px', color: '#2196F3' }}>⏳</span>
                          )}
                          {sourceStatus === 'completed' && (
                            <span style={{ fontSize: '10px', color: '#4CAF50' }}>✓</span>
                          )}
                        </div>
                        {subtask.dependencies.length > 0 && (
                          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>
                            Зависит от {subtask.dependencies.length} задач
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
      
      {/* Parallel Execution Container (Variant 1: Tabs) */}
      {hasParallelBranches && (
        <div style={{ marginBottom: '12px' }}>
          <ParallelExecutionContainer
            branches={block.parallelBranches || []}
            workflowId={workflowId}
            intentId={block.id}
            operations={block.operations || {}}
          />
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
          {/* CRITICAL: Hide source cards for parallel branches - they break tab UI */}
          {block.sources && block.sources.length > 0 && !hasParallelBranches && (
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
