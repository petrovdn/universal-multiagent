import React, { useState, useEffect } from 'react'
import { CheckCircle, XCircle } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import type { PlanData } from '../../types/workspace'
import { useChatStore } from '../../store/chatStore'
import { useWorkspaceStore } from '../../store/workspaceStore'
import { approvePlan, rejectPlan, updatePlan } from '../../services/api'

interface PlanViewerProps {
  tab: WorkspaceTab
}

export function PlanViewer({ tab }: PlanViewerProps) {
  const planData = tab.data as PlanData | undefined
  
  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'PlanViewer.tsx:render',message:'PlanViewer rendered',data:{tabId:tab.id,tabType:tab.type,hasData:!!tab.data,hasPlanData:!!planData,planTextLength:planData?.planText?.length||0,hasConfirmationId:!!planData?.confirmationId,workflowId:planData?.workflowId},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H5'})}).catch(()=>{});
  }, [tab.id, planData]);
  // #endregion
  
  const currentSession = useChatStore((state) => state.currentSession)
  const updateTab = useWorkspaceStore((state) => state.updateTab)
  
  const [planText, setPlanText] = useState(planData?.planText || '')
  const [isSaving, setIsSaving] = useState(false)

  // Sync with tab data when it changes
  useEffect(() => {
    if (planData?.planText) {
      setPlanText(planData.planText)
    }
  }, [planData?.planText])

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value
    setPlanText(newText)
    
    // Update tab data in workspace store
    updateTab(tab.id, {
      data: {
        ...planData,
        planText: newText,
      } as PlanData,
    })
  }

  const handleApprove = async () => {
    if (!currentSession || !planData?.confirmationId) {
      alert('Ошибка: отсутствует session ID или confirmation ID')
      return
    }

    setIsSaving(true)
    try {
      // Always extract steps from current plan (plan might have been edited)
      // Extract only top-level numbered list items (1., 2., 3., etc.)
      const steps = extractStepsFromMarkdown(planText)
      
      // Always update plan with current text and extracted steps
      await updatePlan(currentSession, planData.confirmationId, {
        plan: planText,
        steps: steps,
      })
      
      await approvePlan(currentSession, planData.confirmationId)
    } catch (error) {
      console.error('[PlanViewer] Error approving plan:', error)
      alert('Ошибка при подтверждении плана: ' + (error instanceof Error ? error.message : String(error)))
    } finally {
      setIsSaving(false)
    }
  }

  const handleReject = async () => {
    if (!currentSession || !planData?.confirmationId) {
      alert('Ошибка: отсутствует session ID или confirmation ID')
      return
    }

    setIsSaving(true)
    try {
      await rejectPlan(currentSession, planData.confirmationId)
    } catch (error) {
      console.error('[PlanViewer] Error rejecting plan:', error)
      alert('Ошибка при отклонении плана: ' + (error instanceof Error ? error.message : String(error)))
    } finally {
      setIsSaving(false)
    }
  }

  // Extract only top-level numbered list items (one-level list)
  // Matches patterns like "1. Task", "2. Task", etc. at the start of line (no indentation)
  const extractStepsFromMarkdown = (markdown: string): string[] => {
    const steps: string[] = []
    const lines = markdown.split('\n')
    
    for (const line of lines) {
      // Match only top-level numbered lists (no leading spaces/tabs)
      // Pattern: "1. Task title" at the start of line
      const numberedMatch = line.match(/^\d+\.\s+(.+)$/)
      
      if (numberedMatch) {
        const stepTitle = numberedMatch[1].trim()
        // Only add if it's a reasonable length and not empty
        if (stepTitle && stepTitle.length < 200) {
          steps.push(stepTitle)
        }
      }
    }
    
    // If no steps found, create default
    return steps.length > 0 ? steps : ['Выполнить задачу']
  }

  if (!planData) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 dark:text-slate-400">План не загружен</p>
        </div>
      </div>
    )
  }

  return (
    <div 
      className="w-full bg-white dark:bg-slate-900"
      style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      {/* Toolbar - fixed at top */}
      <div 
        className="flex items-center justify-end px-4 py-2 border-b border-slate-200 dark:border-slate-700"
        style={{ flexShrink: 0, backgroundColor: 'inherit' }}
      >
        <div className="flex items-center gap-2">
          {planData.isAwaitingConfirmation && (
            <>
              <button
                onClick={handleApprove}
                disabled={isSaving}
                className="px-4 py-2 rounded bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white text-sm font-medium flex items-center gap-2 transition-colors"
                title="Подтвердить план"
              >
                <CheckCircle className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={handleReject}
                disabled={isSaving}
                className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white text-sm font-medium flex items-center gap-2 transition-colors"
                title="Отклонить план"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </button>
            </>
          )}
        </div>
      </div>

      {/* Simple text editor - full area with scroll */}
      <div 
        style={{ 
          flex: '1 1 auto', 
          overflow: 'hidden',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <textarea
          value={planText}
          onChange={handleTextChange}
          className="w-full h-full resize-none border-none outline-none bg-transparent text-slate-900 dark:text-slate-100 p-4"
          style={{
            fontFamily: 'system-ui, -apple-system, sans-serif',
            fontSize: '14px',
            lineHeight: '1.6',
            overflow: 'auto',
            flex: '1 1 auto',
            minHeight: 0,
          }}
          placeholder="План будет отображаться здесь..."
          spellCheck={false}
        />
      </div>
    </div>
  )
}
