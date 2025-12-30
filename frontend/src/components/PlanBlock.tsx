import React, { useEffect, useState } from 'react'
import { CheckCircle, XCircle, FileText } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { approvePlan, rejectPlan } from '../services/api'
import { ReasoningBlock } from './ReasoningBlock'
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
    <div style={{ padding: '15px', margin: '10px', background: '#d1ecf1', border: '2px solid #0c5460', borderRadius: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
        <FileText style={{ width: '20px', height: '20px', color: '#0c5460' }} />
        <strong style={{ color: '#0c5460', fontSize: '14px' }}>План</strong>
      </div>
      
      {/* Show thinking/reasoning during plan generation - show immediately when streaming starts */}
      {(workflowPlan.planThinking || workflowPlan.planThinkingIsStreaming) && (
        <div style={{ marginBottom: '15px' }}>
          <ReasoningBlock
            block={{
              id: 'plan-thinking',
              content: workflowPlan.planThinking || (workflowPlan.planThinkingIsStreaming ? 'Анализирую запрос...' : ''),
              isStreaming: workflowPlan.planThinkingIsStreaming,
              timestamp: new Date().toISOString(),
            }}
            isVisible={true}
          />
        </div>
      )}
      
      {workflowPlan.plan && workflowPlan.plan.trim() && (
        <div style={{ marginBottom: '15px', padding: '10px', background: '#fff', borderRadius: '4px', border: '1px solid #bee5eb' }}>
          <div style={{ fontSize: '14px', color: '#0c5460', fontWeight: 'bold', marginBottom: '8px' }}>План:</div>
          <div style={{ fontSize: '14px', color: '#333', whiteSpace: 'pre-wrap' }}>{workflowPlan.plan}</div>
        </div>
      )}

      {workflowPlan.steps && workflowPlan.steps.length > 0 && (
        <div style={{ marginBottom: '15px' }}>
          <div style={{ fontSize: '14px', color: '#0c5460', fontWeight: 'bold', marginBottom: '8px' }}>Шаги:</div>
          <ol style={{ paddingLeft: '20px', margin: 0 }}>
            {workflowPlan.steps.map((step, index) => (
              <li key={index} style={{ fontSize: '14px', color: '#333', marginBottom: '5px' }}>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      {workflowPlan.awaitingConfirmation && (
        <div style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
          <button
            onClick={() => setIsEditingPlan(true)}
            style={{
              padding: '8px 16px',
              background: '#17a2b8',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Редактировать план
          </button>
          <button
            onClick={handleApprove}
            style={{
              padding: '10px 20px',
              background: '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            <CheckCircle style={{ width: '16px', height: '16px', display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
            Approve
          </button>
          <button
            onClick={handleReject}
            style={{
              padding: '10px 20px',
              background: '#dc3545',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            <XCircle style={{ width: '16px', height: '16px', display: 'inline', marginRight: '5px', verticalAlign: 'middle' }} />
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
