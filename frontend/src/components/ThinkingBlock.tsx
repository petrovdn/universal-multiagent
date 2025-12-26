import React from 'react'
import { Brain } from 'lucide-react'
import { useChatStore, ReasoningStep } from '../store/chatStore'

interface ThinkingBlockProps {
  thinking: string
  duration?: number // В секундах
  className?: string
}

export function ThinkingBlock({ thinking, duration = 2.5, className = '' }: ThinkingBlockProps) {
  const { reasoningSteps } = useChatStore()
  
  if (!thinking || thinking.trim() === '') {
    return null
  }

  // Show steps separately if we have multiple steps
  const hasMultipleSteps = reasoningSteps.length > 1

  // If we have steps, always show them separately
  // Otherwise, show the thinking text (which might contain step markers)
  const shouldShowSteps = hasMultipleSteps && reasoningSteps.length > 0

  return (
    <div className={`thinking-block-always-open ${className}`}>
      <div className="thinking-header-static">
        <Brain className="thinking-icon" />
        <span className="thinking-title">
          Думаю {duration.toFixed(1)}с
        </span>
      </div>
      <div className="thinking-content-static">
        {shouldShowSteps ? (
          <div className="reasoning-steps-container">
            {reasoningSteps.map((step, index) => (
              <React.Fragment key={`${step.type}-${index}-${step.timestamp}`}>
                <ReasoningStepItem step={step} />
                {index < reasoningSteps.length - 1 && (
                  <div className="reasoning-step-divider" />
                )}
              </React.Fragment>
            ))}
          </div>
        ) : (
          <div className="thinking-text-content">{thinking}</div>
        )}
      </div>
    </div>
  )
}

function ReasoningStepItem({ step }: { step: ReasoningStep }) {
  const formatStepContent = (step: ReasoningStep): string => {
    let content = step.content
    
    // For tool results, make them more compact
    if (step.type === 'tool_result') {
      // Remove "Результат: " prefix if present
      if (content.startsWith('Результат: ')) {
        content = content.substring(11)
      }
      
      // If content is JSON, try to format it nicely
      try {
        const parsed = JSON.parse(content)
        if (typeof parsed === 'object') {
          // For objects, show a compact summary
          const keys = Object.keys(parsed)
          if (keys.length > 0) {
            return `Получен результат (${keys.length} ${keys.length === 1 ? 'поле' : 'полей'}): ${keys.slice(0, 3).join(', ')}${keys.length > 3 ? '...' : ''}`
          }
        }
      } catch {
        // Not JSON, use as is but truncate if too long
        if (content.length > 500) {
          content = content.substring(0, 500) + '... (показаны первые 500 символов)'
        }
      }
    }
    
    // For tool calls, keep them compact
    if (step.type === 'tool_call') {
      if (content.length > 300) {
        content = content.substring(0, 300) + '...'
      }
    }
    
    return content
  }

  const getStepIcon = () => {
    switch (step.type) {
      case 'tool_call':
        return '🔧'
      case 'tool_result':
        return '✓'
      case 'decision':
        return '💭'
      default:
        return '🧠'
    }
  }

  return (
    <div className={`reasoning-step-item reasoning-step-${step.type}`}>
      <div className="reasoning-step-header">
        <span className="reasoning-step-icon">{getStepIcon()}</span>
        <span className="reasoning-step-type">
          {step.type === 'tool_call' ? 'Вызов инструмента' :
           step.type === 'tool_result' ? 'Результат' :
           step.type === 'decision' ? 'Решение' : 'Размышление'}
        </span>
      </div>
      <div className="reasoning-step-content">
        {formatStepContent(step)}
      </div>
    </div>
  )
}
