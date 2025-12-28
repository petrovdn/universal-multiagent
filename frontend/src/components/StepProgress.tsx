import React from 'react'
import { CheckCircle, Circle, Loader2 } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { ReasoningBlock } from './ReasoningBlock'
import { AnswerBlock } from './AnswerBlock'

export function StepProgress() {
  const { workflowPlan, workflowSteps, currentWorkflowStep } = useChatStore()

  if (!workflowPlan || !workflowPlan.steps || workflowPlan.steps.length === 0) {
    return null
  }

  const stepsArray = workflowPlan.steps.map((stepTitle, index) => {
    const stepNumber = index + 1
    const stepData = workflowSteps[stepNumber]
    return {
      stepNumber,
      title: stepTitle,
      data: stepData,
    }
  })

  if (stepsArray.length === 0) {
    return null
  }

  return (
    <div className="step-progress">
      <div className="step-progress-header">
        <span className="step-progress-title">Выполнение шагов</span>
      </div>
      
      <div className="step-progress-list">
        {stepsArray.map((step) => {
          const status = step.data?.status || 'pending'
          const isActive = step.stepNumber === currentWorkflowStep
          
          return (
            <div
              key={step.stepNumber}
              className={`step-progress-item step-progress-item-${status} ${isActive ? 'step-progress-item-active' : ''}`}
            >
              <div className="step-progress-item-header">
                <div className="step-progress-item-number">
                  {status === 'completed' ? (
                    <CheckCircle className="step-icon step-icon-completed" />
                  ) : status === 'in_progress' ? (
                    <Loader2 className="step-icon step-icon-progress" />
                  ) : (
                    <Circle className="step-icon step-icon-pending" />
                  )}
                </div>
                <div className="step-progress-item-title">
                  <span className="step-number">Шаг {step.stepNumber}</span>
                  <span className="step-title">{step.title}</span>
                </div>
              </div>

              {/* Show thinking and response for active step */}
              {isActive && step.data && (
                <div className="step-progress-item-content">
                  {/* Thinking block */}
                  {step.data.thinking && (
                    <div className="step-thinking-block">
                      <ReasoningBlock
                        block={{
                          id: `step-${step.stepNumber}-thinking`,
                          content: step.data.thinking,
                          isStreaming: status === 'in_progress',
                          timestamp: new Date().toISOString(),
                        }}
                        isVisible={true}
                        shouldAutoCollapse={false}
                      />
                    </div>
                  )}

                  {/* Response block */}
                  {step.data.response && (
                    <div className="step-response-block">
                      <AnswerBlock
                        block={{
                          id: `step-${step.stepNumber}-response`,
                          content: step.data.response,
                          isStreaming: status === 'in_progress',
                          timestamp: new Date().toISOString(),
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Show completed response for completed steps */}
              {status === 'completed' && step.data?.response && !isActive && (
                <div className="step-progress-item-content">
                  <div className="step-response-block">
                    <AnswerBlock
                      block={{
                        id: `step-${step.stepNumber}-response`,
                        content: step.data.response,
                        isStreaming: false,
                        timestamp: new Date().toISOString(),
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

