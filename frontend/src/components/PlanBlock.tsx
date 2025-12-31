import React, { useEffect, useState } from 'react'
import { CheckCircle, XCircle, FileText, Brain } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { approvePlan, rejectPlan } from '../services/api'
import { CollapsibleBlock } from './CollapsibleBlock'
import { PlanEditor } from './PlanEditor'

interface PlanBlockProps {
  workflowId: string
}

export function PlanBlock({ workflowId }: PlanBlockProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan
  const setAwaitingConfirmation = useChatStore((state) => state.setAwaitingConfirmation)
  const activeWorkflowId = useChatStore((state) => state.activeWorkflowId)
  const currentSession = useChatStore((state) => state.currentSession)
  const [isEditingPlan, setIsEditingPlan] = useState(false)// Only show component when there's actual data to display
  if (!workflowPlan) {
    return null
  }

  // Check if there's any content to show
  const hasContent = 
    workflowPlan.planThinking || 
    workflowPlan.planThinkingIsStreaming || 
    (workflowPlan.plan && workflowPlan.plan.trim()) || 
    (workflowPlan.steps && workflowPlan.steps.length > 0) || 
    workflowPlan.awaitingConfirmation

  if (!hasContent) {
    return null
  }

  const handleApprove = async () => {
    if (workflowPlan.confirmationId && currentSession) {
      try {
        await approvePlan(currentSession, workflowPlan.confirmationId)
        setAwaitingConfirmation(false)
      } catch (error) {
        console.error('[PlanBlock] Error approving plan:', error)
        alert('Ошибка при подтверждении плана: ' + (error instanceof Error ? error.message : String(error)))
      }
    }
  }

  const handleReject = async () => {
    if (workflowPlan.confirmationId && currentSession) {
      try {
        await rejectPlan(currentSession, workflowPlan.confirmationId)
        setAwaitingConfirmation(false)
      } catch (error) {
        console.error('[PlanBlock] Error rejecting plan:', error)
        alert('Ошибка при отклонении плана: ' + (error instanceof Error ? error.message : String(error)))
      }
    }
  }

  // Removed useEffect logging to prevent infinite loops

  // If editing, show PlanEditor instead
  if (isEditingPlan && workflowPlan) {
    return (
      <PlanEditor
        workflowId={workflowId}
        initialPlan={workflowPlan}
        onClose={() => setIsEditingPlan(false)}
      />
    )
  }

  return (
    <div style={{ maxWidth: '900px', width: '100%', margin: '0 auto', marginBottom: '0' }}>
      {/* Блок ризонинга плана - первым, сразу под запросом пользователя */}
      {(workflowPlan.planThinking || workflowPlan.planThinkingIsStreaming) && (
        <CollapsibleBlock
          title="составляю план..."
          icon={<Brain className="reasoning-block-icon" />}
          isStreaming={workflowPlan.planThinkingIsStreaming}
          isCollapsed={true}
          autoCollapse={true}
          className="plan-reasoning-block"
        >
          {workflowPlan.planThinking || (workflowPlan.planThinkingIsStreaming ? 'Анализирую запрос...' : '')}
        </CollapsibleBlock>
      )}
      
      {/* Блок самого плана - сразу под ризонингом */}
      {workflowPlan.plan && workflowPlan.plan.trim() && (
        <>
          <CollapsibleBlock
            title={`План: ${workflowPlan.plan}`}
            icon={<FileText className="reasoning-block-icon" />}
            isStreaming={false}
            isCollapsed={false}
            autoCollapse={false}
            className="plan-content-block"
          >
            {workflowPlan.steps && workflowPlan.steps.length > 0 && (
              <ol style={{ paddingLeft: '24px', margin: 0, fontSize: '14px', lineHeight: '1.6', color: '#111' }}>
                {workflowPlan.steps.map((step, index) => {
                  const stepNumber = index + 1
                  const stepData = workflow?.steps[stepNumber]
                  const isCompleted = stepData?.status === 'completed'
                  
                  return (
                    <li 
                      key={index} 
                      style={{ 
                        marginBottom: '8px',
                        paddingLeft: '4px',
                        textDecoration: isCompleted ? 'line-through' : 'none'
                      }}
                    >
                      {step}
                    </li>
                  )
                })}
              </ol>
            )}
          </CollapsibleBlock>

          {/* Кнопки управления планом - под блоком плана */}
          {workflowPlan.awaitingConfirmation && (
            <div style={{ display: 'flex', gap: '10px', marginTop: '0', maxWidth: '900px', width: '100%', marginLeft: 'auto', marginRight: 'auto', padding: '12px 0', background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-secondary)' }}>
              <button
                onClick={() => setIsEditingPlan(true)}
                className="plan-button"
                style={{
                  background: '#17a2b8',
                  color: 'white',
                  flex: '0 0 auto'
                }}
              >
                Редактировать план
              </button>
              <button
                onClick={handleApprove}
                className="plan-button plan-button-approve"
              >
                <CheckCircle style={{ width: '16px', height: '16px', display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                Approve
              </button>
              <button
                onClick={handleReject}
                className="plan-button plan-button-reject"
              >
                <XCircle style={{ width: '16px', height: '16px', display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
                Reject
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
