import React, { useEffect } from 'react'
import { CheckCircle, XCircle, FileText } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { wsClient } from '../services/websocket'
import { ReasoningBlock } from './ReasoningBlock'

export function PlanBlock() {
  // Simple selector - Zustand should handle reactivity automatically
  const workflowPlan = useChatStore((state) => state.workflowPlan)
  const setAwaitingConfirmation = useChatStore((state) => state.setAwaitingConfirmation)

  // Removed useEffect logging to prevent infinite loops

  // DEBUG MODE: Always show something, even if no plan
  if (!workflowPlan) {
    return (
      <div style={{ padding: '15px', margin: '10px', background: '#fff3cd', border: '2px solid #ffc107', borderRadius: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
          <FileText style={{ width: '20px', height: '20px', color: '#856404' }} />
          <strong style={{ color: '#856404', fontSize: '16px' }}>PlanBlock: Waiting for plan...</strong>
        </div>
        <div style={{ color: '#856404', fontSize: '14px' }}>No workflow plan set yet</div>
      </div>
    )
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
      
      {(workflowPlan.plan && workflowPlan.plan.trim()) ? (
        <div style={{ marginBottom: '15px', padding: '10px', background: '#fff', borderRadius: '4px', border: '1px solid #bee5eb' }}>
          <div style={{ fontSize: '14px', color: '#0c5460', fontWeight: 'bold', marginBottom: '8px' }}>План:</div>
          <div style={{ fontSize: '14px', color: '#333', whiteSpace: 'pre-wrap' }}>{workflowPlan.plan}</div>
        </div>
      ) : (
        <div style={{ marginBottom: '15px', padding: '10px', background: '#fff3cd', borderRadius: '4px', border: '1px solid #ffc107' }}>
          <div style={{ fontSize: '14px', color: '#856404', fontStyle: 'italic' }}>План еще не сгенерирован...</div>
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
