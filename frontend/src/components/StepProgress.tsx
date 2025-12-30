import React from 'react'
import { useChatStore, WorkflowStep } from '../store/chatStore'
import { FinalResultBlock } from './FinalResultBlock'

interface StepProgressProps {
  workflowId: string
}

export function StepProgress({ workflowId }: StepProgressProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan

  // Only show component when there's a plan (workflow exists)
  if (!workflowPlan || !workflowPlan.steps || workflowPlan.steps.length === 0) {
    return null
  }

  const planSteps = workflowPlan.steps // Array of step titles (strings)
  const workflowSteps = workflow?.steps || {} // Record<number, WorkflowStep>

  // If we have no workflow steps yet and no final result, don't show anything
  // (plan is shown in PlanBlock, steps will appear when execution starts)
  const hasAnyStepData = Object.keys(workflowSteps).length > 0
  const hasFinalResult = workflow?.finalResult

  if (!hasAnyStepData && !hasFinalResult) {
    return null
  }

  return (
    <div style={{ margin: '10px 0' }}>
      {/* Render each step */}
      {planSteps.map((stepTitle, index) => {
        const stepNumber = index + 1
        const stepData: WorkflowStep | undefined = workflowSteps[stepNumber]

        // If step hasn't started yet, show as pending
        const status = stepData?.status || 'pending'
        const thinking = stepData?.thinking || ''
        const response = stepData?.response || ''

        return (
          <div
            key={stepNumber}
            style={{
              marginBottom: '15px',
              padding: '15px',
              background: status === 'completed' ? '#d4edda' : status === 'in_progress' ? '#fff3cd' : '#f8f9fa',
              border: `2px solid ${
                status === 'completed' ? '#28a745' : status === 'in_progress' ? '#ffc107' : '#dee2e6'
              }`,
              borderRadius: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background:
                    status === 'completed' ? '#28a745' : status === 'in_progress' ? '#ffc107' : '#6c757d',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 'bold',
                  fontSize: '12px',
                }}
              >
                {status === 'completed' ? '✓' : stepNumber}
              </div>
              <strong style={{ fontSize: '14px', color: '#333' }}>
                Шаг {stepNumber}: {stepTitle}
              </strong>
              <span
                style={{
                  marginLeft: 'auto',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  background:
                    status === 'completed'
                      ? '#28a745'
                      : status === 'in_progress'
                        ? '#ffc107'
                        : '#6c757d',
                  color: 'white',
                }}
              >
                {status === 'completed' ? 'Завершено' : status === 'in_progress' ? 'В процессе' : 'Ожидание'}
              </span>
            </div>

            {/* Show thinking if available */}
            {thinking && thinking.trim() && (
              <div
                style={{
                  marginBottom: '10px',
                  padding: '10px',
                  background: '#e7f3ff',
                  borderRadius: '4px',
                  border: '1px solid #b3d9ff',
                }}
              >
                <div style={{ fontSize: '12px', color: '#0066cc', marginBottom: '5px', fontWeight: 'bold' }}>
                  💭 Размышление:
                </div>
                <div style={{ fontSize: '14px', color: '#333', whiteSpace: 'pre-wrap' }}>{thinking}</div>
                {status === 'in_progress' && (
                  <span style={{ display: 'inline-block', marginLeft: '5px', animation: 'blink 1s infinite' }}>
                    ▊
                  </span>
                )}
              </div>
            )}

            {/* Show response if available */}
            {response && response.trim() && (
              <div
                style={{
                  padding: '10px',
                  background: 'white',
                  borderRadius: '4px',
                  border: '1px solid #dee2e6',
                  marginTop: thinking ? '10px' : '0',
                }}
              >
                <div style={{ fontSize: '12px', color: '#6c757d', marginBottom: '5px', fontWeight: 'bold' }}>
                  Результат:
                </div>
                <div style={{ fontSize: '14px', color: '#333', whiteSpace: 'pre-wrap' }}>{response}</div>
              </div>
            )}

            {/* Show placeholder when step is in progress but no content yet */}
            {status === 'in_progress' && !thinking && !response && (
              <div style={{ fontSize: '14px', color: '#6c757d', fontStyle: 'italic' }}>
                Выполнение шага...
              </div>
            )}
          </div>
        )
      })}

      {/* Show final result if available */}
      {hasFinalResult && (
        <div style={{ marginTop: '20px' }}>
          <FinalResultBlock content={workflow.finalResult!} />
        </div>
      )}
    </div>
  )
}
