import React from 'react'
import { useChatStore } from '../store/chatStore'
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

  // Only display final result - step details are shown in PlanBlock
  if (!workflow?.finalResult) {
    return null
  }

  return <FinalResultBlock content={workflow.finalResult} />
}
