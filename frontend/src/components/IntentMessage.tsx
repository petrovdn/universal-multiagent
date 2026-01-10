import React from 'react'
import { IntentBlock } from '../store/chatStore'
import { PlanningBlock } from './PlanningBlock'

interface IntentMessageProps {
  block: IntentBlock
  stepNumber?: number // Опциональный: если undefined, не показываем номер шага
  onToggleCollapse: () => void
  onTogglePlanningCollapse?: () => void
  onToggleExecutingCollapse?: () => void
}

export function IntentMessage({ 
  block,
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

  // Показывать секцию "Планирую" если есть thinking или в фазе planning
  const showPlanningSection = hasThinkingText || isPlanning
  // Показывать секцию "Выполняю" если есть details или в фазе executing/completed
  const showExecutingSection = hasDetails || isExecuting || isCompleted
  
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
      
      {/* Фаза 2: Выполняю - лог действий */}
      {showExecutingSection && (
        <div className="execution-log" style={{ marginTop: '8px' }}>
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
                      <span className="log-text-dots" />
                    )}
                  </span>
                </div>
              </div>
            )
          })}
          {isExecuting && block.details.length === 0 && (
            <div className="execution-log-item">
              <span className="log-icon pending">○</span>
              <span className="log-text log-text-pending">
                Выполняю действия...
                <span className="log-text-dots" />
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
