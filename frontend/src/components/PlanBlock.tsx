import React, { useEffect } from 'react'
import { CheckCircle, XCircle, FileText } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { wsClient } from '../services/websocket'
import { ReasoningBlock } from './ReasoningBlock'

interface PlanBlockProps {
  workflowId: string
}

export function PlanBlock({ workflowId }: PlanBlockProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan
  const setAwaitingConfirmation = useChatStore((state) => state.setAwaitingConfirmation)
  const activeWorkflowId = useChatStore((state) => state.activeWorkflowId)

  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'PlanBlock.tsx:render',message:'PlanBlock render',data:{workflowId,activeWorkflowId,hasWorkflow:!!workflow,hasPlan:!!workflowPlan,allWorkflowIds:Object.keys(useChatStore.getState().workflows)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'RENDER'})}).catch(()=>{});
  }, [workflowId, workflow, workflowPlan, activeWorkflowId])
  // #endregion

  // Only show component when there's actual data to display
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

  const handleApprove = () => {
    if (workflowPlan.confirmationId) {
      wsClient.approvePlan(workflowPlan.confirmationId)
      setAwaitingConfirmation(false)
    }
  }

  const handleReject = () => {
    if (workflowPlan.confirmationId) {
      wsClient.rejectPlan(workflowPlan.confirmationId)
      setAwaitingConfirmation(false)
    }
  }

  // Removed useEffect logging to prevent infinite loops

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
