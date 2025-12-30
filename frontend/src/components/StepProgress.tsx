import React from 'react'
import { useChatStore, WorkflowStep } from '../store/chatStore'
import { FinalResultBlock } from './FinalResultBlock'
import { ReasoningBlock } from './ReasoningBlock'
import { AttemptBlock } from './AttemptBlock'

interface StepProgressProps {
  workflowId: string
}

interface AttemptBlock {
  number: string
  title: string
  content: string
}

// Parse attempts from response text
function parseAttempts(text: string): { attempts: AttemptBlock[], remaining: string } {
  const attempts: AttemptBlock[] = []
  
  // Find all "## Попытка N:" patterns in the text
  // Pattern: ## Попытка N: [title]\n[content]
  // Content continues until next "## Попытка" or end of text
  const attemptPattern = /##\s*Попытка\s+(\d+):\s*(.+?)(?:\n|$)([\s\S]*?)(?=##\s*Попытка\s+\d+:|$)/g
  
  const attemptMatches: Array<{ match: RegExpMatchArray, start: number, end: number }> = []
  let match
  
  // Find all matches and store their positions
  while ((match = attemptPattern.exec(text)) !== null) {
    attemptMatches.push({
      match,
      start: match.index,
      end: match.index + match[0].length
    })
  }
  
  // Extract attempts from matches - only include fully formed attempts (with both title and content)
  attemptMatches.forEach(({ match }) => {
    const number = match[1]
    const title = match[2].trim()
    const content = match[3] ? match[3].trim() : ''
    
    // Only add attempt if it's fully formed: has both title and content
    // This ensures we don't show attempts that are still being streamed
    if (title && content) {
      attempts.push({
        number,
        title,
        content
      })
    }
  })
  
  // Extract remaining content (everything that's not part of attempts)
  // Build remaining text by taking parts of text that are not in attempt ranges
  let remaining = ''
  let lastEnd = 0
  
  attemptMatches.forEach(({ start, end }) => {
    // Add text before this attempt
    if (start > lastEnd) {
      const beforeText = text.substring(lastEnd, start).trim()
      if (beforeText) {
        remaining += (remaining ? '\n\n' : '') + beforeText
      }
    }
    lastEnd = end
  })
  
  // Add text after last attempt
  if (lastEnd < text.length) {
    const afterText = text.substring(lastEnd).trim()
    if (afterText) {
      remaining += (remaining ? '\n\n' : '') + afterText
    }
  }
  
  // Clean up any leftover "---" markers and extra whitespace
  remaining = remaining.replace(/---\s*\n?/g, '').trim()
  
  return { attempts, remaining }
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
              <div style={{ marginBottom: '10px' }}>
                <ReasoningBlock
                  block={{
                    id: `step-thinking-${workflowId}-${stepNumber}`,
                    content: thinking,
                    isStreaming: status === 'in_progress',
                    timestamp: new Date().toISOString(),
                  }}
                  isVisible={true}
                />
              </div>
            )}

            {/* Show response block - show immediately when streaming starts */}
            {(status === 'in_progress' || (response && response.trim())) && (() => {
              const { attempts, remaining } = parseAttempts(response || '')
              const isStepStreaming = status === 'in_progress'
              
              return (
                <div style={{ marginTop: '10px' }}>
                  <div style={{ fontSize: '12px', color: '#6c757d', marginBottom: '10px', fontWeight: 'bold' }}>
                    Результат:
                  </div>
                  
                  {/* Render attempts as collapsible blocks */}
                  {attempts.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      {attempts.map((attempt, attemptIndex) => (
                        <div key={attemptIndex} style={{ marginBottom: '8px' }}>
                          <AttemptBlock
                            id={`step-attempt-${workflowId}-${stepNumber}-${attempt.number}`}
                            number={attempt.number}
                            title={attempt.title}
                            content={attempt.content}
                            isStreaming={isStepStreaming}
                            isVisible={true}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Render remaining content (not part of attempts) - with streaming */}
                  {(remaining && remaining.trim()) || isStepStreaming ? (
                    <div
                      style={{
                        padding: '10px',
                        background: 'white',
                        borderRadius: '4px',
                        border: '1px solid #dee2e6',
                        marginTop: attempts.length > 0 ? '10px' : '0',
                      }}
                    >
                      <div style={{ fontSize: '14px', color: '#333', whiteSpace: 'pre-wrap' }}>
                        {remaining || ''}
                        {isStepStreaming && (
                          <span className="answer-block-cursor" style={{ marginLeft: '2px' }}>▊</span>
                        )}
                      </div>
                    </div>
                  ) : null}
                  
                  {/* Show placeholder when streaming but no content yet */}
                  {isStepStreaming && !response && attempts.length === 0 && (
                    <div
                      style={{
                        padding: '10px',
                        background: 'white',
                        borderRadius: '4px',
                        border: '1px solid #dee2e6',
                        fontStyle: 'italic',
                        color: '#6c757d',
                      }}
                    >
                      <span className="answer-block-cursor">▊</span> Генерация результата...
                    </div>
                  )}
                </div>
              )
            })()}

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
