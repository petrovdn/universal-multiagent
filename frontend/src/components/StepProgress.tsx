import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Brain, Loader2 } from 'lucide-react'
import { useChatStore, WorkflowStep } from '../store/chatStore'
import { CollapsibleBlock } from './CollapsibleBlock'

interface StepProgressProps {
  workflowId: string
}

interface AttemptBlock {
  number: string
  title: string
  content: string
}

// Parse response text into action preparation and result parts
function parseStepResponse(text: string): { actionPreparation: string, result: string } {
  // Find marker "**Результат шага:**" or "**Результат:**"
  const resultMarker = /(\*\*Результат\s+шага:\*\*|\*\*Результат:\*\*)/i
  const match = text.match(resultMarker)
  
  if (match && match.index !== undefined) {
    const markerIndex = match.index
    const actionPreparation = text.substring(0, markerIndex).trim()
    const result = text.substring(markerIndex + match[0].length).trim()
    return { actionPreparation, result }
  }
  
  // If no marker found, all text is result (no action preparation shown)
  return { actionPreparation: '', result: text.trim() }
}

// Extract action description from step title for block header
function getActionDescription(stepTitle: string): string {
  // Convert step title to action description
  // "Найти файл 'Рабочая таблица'" -> "Сейчас выполняю поиск файла 'Рабочая таблица'"
  // Simple approach: prepend "Сейчас выполняю " to the step title
  return `Сейчас выполняю ${stepTitle.toLowerCase()}`
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
    <div style={{ 
      maxWidth: '900px', 
      width: '100%', 
      margin: '0 auto',
      /* Добавляем padding-top чтобы шаги не прилипали к sticky-секции */
      paddingTop: '8px'
    }}>
      {/* Render each step */}
      {planSteps.map((stepTitle, index) => {
        const stepNumber = index + 1
        const stepData: WorkflowStep | undefined = workflowSteps[stepNumber]

        // If step hasn't started yet, show as pending
        const status = stepData?.status || 'pending'
        const thinking = stepData?.thinking || ''
        const response = stepData?.response || ''
        const isStepStreaming = status === 'in_progress'
        
        // Parse response into action preparation and result
        const { actionPreparation, result } = parseStepResponse(response)

        return (
          <div key={stepNumber} style={{ marginBottom: '24px' }}>
            {/* Заголовок шага - без границ, без фона, как обычный текст */}
            <h3 style={{ 
              fontWeight: 'normal', 
              fontSize: '15px', 
              marginBottom: '8px',
              color: '#1A1A1A',
              maxWidth: '900px',
              width: '100%',
              marginLeft: 'auto',
              marginRight: 'auto',
              paddingLeft: '14px',
              paddingRight: '14px'
            }}>
              {stepTitle}{status === 'completed' ? ' (Готово)' : ''}
            </h3>

            {/* Блок ризонинга шага */}
            {thinking && thinking.trim() && (
              <CollapsibleBlock
                title="думаю..."
                icon={<Brain className="reasoning-block-icon" />}
                isStreaming={isStepStreaming}
                isCollapsed={true}
                autoCollapse={true}
              >
                {thinking}
              </CollapsibleBlock>
            )}

            {/* Блок подготовки результата (действия модели) */}
            {(actionPreparation && actionPreparation.trim()) || (isStepStreaming && !result) ? (
              <CollapsibleBlock
                title={getActionDescription(stepTitle)}
                icon={<Loader2 className="reasoning-block-icon" />}
                isStreaming={isStepStreaming}
                isCollapsed={false}
                alwaysOpen={true}
              >
                {actionPreparation || (isStepStreaming ? 'Выполняю действия...' : '')}
              </CollapsibleBlock>
            ) : null}

            {/* Результат шага - просто текст без рамок и фона, с маркдауном */}
            {result && result.trim() && (
              <div style={{ 
                maxWidth: '900px',
                width: '100%',
                marginTop: '12px',
                marginLeft: 'auto',
                marginRight: 'auto',
                paddingLeft: '14px',
                paddingRight: '14px'
              }}>
                <div className="prose max-w-none 
                  prose-p:text-gray-900 
                  prose-p:leading-6 prose-p:my-3 prose-p:text-[13px]
                  prose-h1:text-gray-900 prose-h1:text-[20px] prose-h1:font-semibold prose-h1:mb-3 prose-h1:mt-6 prose-h1:first:mt-0 prose-h1:leading-tight
                  prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold prose-h2:mb-2 prose-h2:mt-5 prose-h2:leading-tight
                  prose-h3:text-gray-900 prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:leading-tight
                  prose-strong:text-gray-900 prose-strong:font-semibold
                  prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:border prose-code:border-gray-200
                  prose-pre:bg-gray-100 prose-pre:text-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:text-[13px] prose-pre:rounded-lg prose-pre:p-4
                  prose-ul:text-gray-900 prose-ul:my-3 prose-ul:pl-8
                  prose-ol:text-gray-900 prose-ol:my-3 prose-ol:pl-8
                  prose-li:text-gray-900 prose-li:my-1.5 prose-li:text-[13px]
                  prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-700
                  prose-blockquote:text-gray-600 prose-blockquote:border-l-gray-300 prose-blockquote:pl-4 prose-blockquote:my-3
                  prose-table:w-full prose-table:border-collapse prose-table:my-4
                  prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold
                  prose-td:border prose-td:border-gray-300 prose-td:px-3 prose-td:py-2
                  prose-tr:hover:bg-gray-50">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* Show placeholder when step is in progress but no content yet */}
            {status === 'in_progress' && !thinking && !response && (
              <div style={{ fontSize: '14px', color: '#6c757d', fontStyle: 'italic', maxWidth: '900px', width: '100%', marginLeft: 'auto', marginRight: 'auto', paddingLeft: '14px', paddingRight: '14px' }}>
                Выполнение шага...
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
