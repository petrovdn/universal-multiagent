import React from 'react'
import { FileText, Brain, ExternalLink } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useWorkspaceStore } from '../store/workspaceStore'
import { CollapsibleBlock } from './CollapsibleBlock'

interface PlanBlockProps {
  workflowId: string
}

export function PlanBlock({ workflowId }: PlanBlockProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan
  const workspaceStore = useWorkspaceStore()
  
  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'PlanBlock.tsx:render',message:'PlanBlock rendered',data:{workflowId:workflowId,hasWorkflow:!!workflow,hasPlan:!!workflowPlan,hasPlanText:!!workflowPlan?.plan,planTextLength:workflowPlan?.plan?.length||0,hasSteps:!!workflowPlan?.steps,stepsCount:workflowPlan?.steps?.length||0,awaitingConfirmation:workflowPlan?.awaitingConfirmation},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H6'})}).catch(()=>{});
  }, [workflowId, workflowPlan]);
  // #endregion
  
  // Find plan tab for this workflow
  const planTab = workspaceStore.tabs.find(
    t => t.type === 'plan' && t.data?.workflowId === workflowId
  )
  
  const handleOpenInEditor = () => {
    if (planTab) {
      workspaceStore.setActiveTab(planTab.id)
    } else {
      // If tab doesn't exist, create it
      workspaceStore.addTab({
        type: 'plan',
        title: 'План выполнения',
        data: {
          planText: workflowPlan?.plan || '',
          confirmationId: workflowPlan?.confirmationId || null,
          workflowId: workflowId,
          isAwaitingConfirmation: workflowPlan?.awaitingConfirmation || false,
        },
        closeable: true,
      })
    }
  }
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

  return (
    <>
      {/* Внешний контейнер "План" */}
      {(workflowPlan.plan && workflowPlan.plan.trim()) || (workflowPlan.planThinking || workflowPlan.planThinkingIsStreaming) ? (
        <>
          {/* Блок ризонинга - независимое сворачивание */}
          {(workflowPlan.planThinking || workflowPlan.planThinkingIsStreaming) && (
            <CollapsibleBlock
              title="Составляю план..."
              icon={<Brain className="reasoning-block-icon" />}
              isStreaming={workflowPlan.planThinkingIsStreaming}
              isCollapsed={!workflowPlan.planThinkingIsStreaming}
              autoCollapse={true}
              className="plan-reasoning-block"
              ref={(el) => {              }}
            >
              <div style={{ 
                // Убираем fontSize - используем CSS из .reasoning-block-content (10px)
                lineHeight: '1.6', 
                color: '#666',
                whiteSpace: 'pre-wrap',
                maxHeight: '200px', // Уменьшена высота в 2 раза (примерно)
                overflowY: 'auto'
              }}>
                {workflowPlan.planThinking || (workflowPlan.planThinkingIsStreaming ? 'Анализирую запрос...' : '')}
              </div>
            </CollapsibleBlock>
          )}
          
          {/* Блок пунктов плана - независимое сворачивание, не сворачивается автоматически */}
          {workflowPlan.plan && workflowPlan.plan.trim() && (
            <>
              <CollapsibleBlock
                title="План"
                icon={<FileText className="reasoning-block-icon" />}
                isStreaming={false}
                isCollapsed={false}
                autoCollapse={false}
                className="plan-content-block"
              >
                {/* Прогресс выполнения шагов */}
                {workflowPlan.stepPlanProgress && (
                  <div className="step-plan-progress mb-3 p-2 bg-gray-50 dark:bg-gray-800/50 rounded" style={{ marginBottom: '12px' }}>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                      Шаг {workflowPlan.stepPlanProgress.currentStep} из {workflowPlan.stepPlanProgress.totalSteps}
                      {' '}(Выполнено: {workflowPlan.stepPlanProgress.completedSteps})
                    </div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      Текущий шаг: {workflowPlan.stepPlanProgress.currentStepTitle}
                    </div>
                    {workflowPlan.stepPlanProgress.remainingSteps.length > 0 && (
                      <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                        Осталось: {workflowPlan.stepPlanProgress.remainingSteps.join(', ')}
                      </div>
                    )}
                  </div>
                )}
                
                {workflowPlan.steps && workflowPlan.steps.length > 0 && (
                  <ol className="plan-steps-list">
                    {workflowPlan.steps.map((step, index) => {
                      const stepNumber = index + 1
                      const stepData = workflow?.steps[stepNumber]
                      const isCompleted = stepData?.status === 'completed'
                      const isInProgress = stepData?.status === 'in_progress'
                      
                      return (
                        <li 
                          key={index}
                          className={`plan-step-item ${isCompleted ? 'completed' : ''} ${isInProgress ? 'active' : ''}`}
                        >
                          {step}
                        </li>
                      )
                    })}
                  </ol>
                )}
              </CollapsibleBlock>

              {/* Статус и кнопка открытия в редакторе */}
              {workflowPlan.awaitingConfirmation && (
                <div style={{ display: 'flex', gap: '10px', marginTop: '12px', maxWidth: '900px', width: '100%', marginLeft: 'auto', marginRight: 'auto', padding: '12px 0', background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-secondary)' }}>
                  <div style={{ flex: '1', display: 'flex', alignItems: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
                    План создан. Ожидает подтверждения.
                  </div>
                  <button
                    onClick={handleOpenInEditor}
                    className="plan-button"
                    style={{
                      background: '#17a2b8',
                      color: 'white',
                      flex: '0 0 auto',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '8px 16px'
                    }}
                  >
                    <ExternalLink style={{ width: '16px', height: '16px' }} />
                    Открыть в редакторе
                  </button>
                </div>
              )}
            </>
          )}
        </>
      ) : null}
    </>
  )
}
