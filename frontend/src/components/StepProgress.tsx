import React, { useEffect } from 'react'
import { CheckCircle, Circle, Loader2 } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { ReasoningBlock } from './ReasoningBlock'
import { StructuredAnswer } from './StructuredAnswer'

export function StepProgress() {
  // Use separate selectors to avoid shallow comparison issues - Zustand uses Object.is() for comparison
  const workflowPlan = useChatStore((state) => state.workflowPlan)
  const workflowSteps = useChatStore((state) => state.workflowSteps)
  const currentWorkflowStep = useChatStore((state) => state.currentWorkflowStep)

  // Removed useEffect logging to prevent infinite loops

  // Only show component when there are actual steps to display
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

  // Removed useEffect logging to prevent infinite loops

  return (
    <div style={{ padding: '15px', margin: '10px', background: '#e7f3ff', border: '2px solid #004085', borderRadius: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
        <Loader2 style={{ width: '20px', height: '20px', color: '#004085' }} />
        <strong style={{ color: '#004085', fontSize: '18px' }}>Прогресс шагов</strong>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        {stepsArray.map((step) => {
          const status = step.data?.status || 'pending'
          const isActive = currentWorkflowStep === step.stepNumber

          return (
            <div
              key={step.stepNumber}
              style={{
                padding: '15px',
                background: isActive ? '#fff3cd' : status === 'completed' ? '#d4edda' : '#f8f9fa',
                border: `2px solid ${isActive ? '#ffc107' : status === 'completed' ? '#28a745' : '#dee2e6'}`,
                borderRadius: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                {status === 'completed' ? (
                  <CheckCircle style={{ width: '20px', height: '20px', color: '#28a745' }} />
                ) : isActive ? (
                  <Loader2 style={{ width: '20px', height: '20px', color: '#ffc107', animation: 'spin 1s linear infinite' }} />
                ) : (
                  <Circle style={{ width: '20px', height: '20px', color: '#6c757d' }} />
                )}
                <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#333' }}>
                  Шаг {step.stepNumber}: {step.title}
                </span>
                <span
                  style={{
                    marginLeft: 'auto',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    background: status === 'completed' ? '#28a745' : isActive ? '#ffc107' : '#6c757d',
                    color: '#fff',
                  }}
                >
                  {status}
                </span>
              </div>

              {/* Show thinking and response for active step */}
              {isActive && step.data && (
                <div style={{ marginTop: '15px' }}>
                  {/* Thinking block - using ReasoningBlock component */}
                  {step.data.thinking && (
                    <div style={{ marginBottom: '10px' }}>
                      <ReasoningBlock
                        block={{
                          id: `step-${step.stepNumber}-thinking`,
                          content: step.data.thinking,
                          isStreaming: status === 'in_progress',
                          timestamp: new Date().toISOString(),
                        }}
                        isVisible={true}
                      />
                    </div>
                  )}

                  {/* Response block - structured */}
                  {step.data.response && (
                    <div style={{ marginTop: '10px' }}>
                      <StructuredAnswer 
                        content={step.data.response} 
                        isStreaming={status === 'in_progress'}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Show completed response for completed steps */}
              {status === 'completed' && step.data?.response && !isActive && (
                <div style={{ marginTop: '10px' }}>
                  <StructuredAnswer 
                    content={step.data.response} 
                    isStreaming={false}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}