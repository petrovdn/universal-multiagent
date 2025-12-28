import React from 'react'
import { CheckCircle, XCircle, FileText } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { wsClient } from '../services/websocket'

export function PlanBlock() {
  const { workflowPlan, setAwaitingConfirmation } = useChatStore()

  if (!workflowPlan) {
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

  return (
    <div className="plan-block">
      <div className="plan-header">
        <FileText className="plan-icon" />
        <span className="plan-title">План выполнения</span>
      </div>
      
      <div className="plan-content">
        <div className="plan-description">
          {workflowPlan.plan}
        </div>
        
        {workflowPlan.steps.length > 0 && (
          <div className="plan-steps">
            <div className="plan-steps-title">Шаги выполнения:</div>
            <ol className="plan-steps-list">
              {workflowPlan.steps.map((step, index) => (
                <li key={index} className="plan-step-item">
                  {step}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {workflowPlan.awaitingConfirmation && (
        <div className="plan-actions">
          <button
            onClick={handleApprove}
            className="plan-button plan-button-approve"
          >
            <CheckCircle className="button-icon" />
            <span>Подтвердить</span>
          </button>
          <button
            onClick={handleReject}
            className="plan-button plan-button-reject"
          >
            <XCircle className="button-icon" />
            <span>Отклонить</span>
          </button>
        </div>
      )}
    </div>
  )
}

