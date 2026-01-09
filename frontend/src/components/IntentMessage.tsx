import React, { useMemo, useRef, useEffect } from 'react'
import { ChevronDown, ChevronRight, Search, FileText, Play, Brain, Pencil, Check } from 'lucide-react'
import { IntentBlock, IntentDetailType } from '../store/chatStore'
import { CircularProgress } from './CircularProgress'

interface IntentMessageProps {
  block: IntentBlock
  onToggleCollapse: () => void
  onTogglePlanningCollapse?: () => void
  onToggleExecutingCollapse?: () => void
}

export function IntentMessage({ 
  block, 
  onToggleCollapse,
  onTogglePlanningCollapse,
  onToggleExecutingCollapse 
}: IntentMessageProps) {
  
  const getIcon = (type: IntentDetailType) => {
    switch (type) {
      case 'search': return <Search size={12} className="intent-detail-icon" />
      case 'read': return <FileText size={12} className="intent-detail-icon" />
      case 'execute': return <Play size={12} className="intent-detail-icon" />
      case 'write': return <Pencil size={12} className="intent-detail-icon" />
      case 'analyze': return <Check size={12} className="intent-detail-icon intent-detail-icon-success" />
      default: return <Brain size={12} className="intent-detail-icon" />
    }
  }

  const isPlanning = block.phase === 'planning'
  const isExecuting = block.phase === 'executing'
  const isCompleted = block.phase === 'completed'
  const hasThinkingText = !!block.thinkingText
  const hasDetails = block.details.length > 0

  // Auto-scroll для streaming thinking
  const thinkingRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (thinkingRef.current && hasThinkingText && isPlanning) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight
    }
  }, [block.thinkingText, hasThinkingText, isPlanning])

  // Auto-scroll для details
  const detailsRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (detailsRef.current && hasDetails && isExecuting) {
      detailsRef.current.scrollTop = detailsRef.current.scrollHeight
    }
  }, [block.details.length, hasDetails, isExecuting])

  // Показывать секцию "Планирую" если есть thinking или в фазе planning
  const showPlanningSection = hasThinkingText || isPlanning
  // Показывать секцию "Выполняю" если есть details или в фазе executing/completed
  const showExecutingSection = hasDetails || isExecuting || isCompleted

  return (
    <div className={`intent-message ${isCompleted ? 'intent-message-completed' : ''}`}>
      {/* Заголовок intent */}
      <div className="intent-header">
        <span className="intent-text">{block.intent}</span>
      </div>
      
      {/* Фаза 1: Планирую */}
      {showPlanningSection && (
        <div className={`intent-phase-section ${block.planningCollapsed ? 'collapsed' : ''}`}>
          <div 
            className="intent-phase-header"
            onClick={onTogglePlanningCollapse}
          >
            <CircularProgress 
              percent={isPlanning ? block.progressPercent : 100} 
              size={14}
              strokeWidth={2}
              className="intent-phase-progress"
            />
            {block.planningCollapsed ? (
              <ChevronRight size={14} className="intent-chevron" />
            ) : (
              <ChevronDown size={14} className="intent-chevron" />
            )}
            <span className="intent-phase-title">
              {block.planningCollapsed ? 'Анализ проведён' : 'Планирую'}
            </span>
          </div>
          
          {!block.planningCollapsed && hasThinkingText && (
            <div ref={thinkingRef} className="intent-phase-content">
              <div className="intent-thinking-text">
                {block.thinkingText}
                {isPlanning && <span className="intent-thinking-cursor" />}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Фаза 2: Выполняю */}
      {showExecutingSection && (
        <div className={`intent-phase-section ${block.executingCollapsed ? 'collapsed' : ''}`}>
          <div 
            className="intent-phase-header"
            onClick={onToggleExecutingCollapse}
          >
            <CircularProgress 
              percent={isExecuting ? block.progressPercent : (isCompleted ? 100 : 0)} 
              size={14}
              strokeWidth={2}
              className="intent-phase-progress"
            />
            {block.executingCollapsed ? (
              <ChevronRight size={14} className="intent-chevron" />
            ) : (
              <ChevronDown size={14} className="intent-chevron" />
            )}
            <span className="intent-phase-title">
              {block.executingCollapsed ? 'Выполнено' : 'Выполняю'}
            </span>
          </div>
          
          {!block.executingCollapsed && hasDetails && (
            <div ref={detailsRef} className="intent-phase-content">
              {block.details.map((detail, i) => (
                <div key={i} className="intent-detail-item">
                  {getIcon(detail.type)}
                  <span className="intent-detail-text">{detail.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
