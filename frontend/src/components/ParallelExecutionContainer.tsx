import React, { useState } from 'react'
import { ParallelBranch, IterationBlock, Operation, useChatStore } from '../store/chatStore'
import { IterationBlock as IterationBlockComponent } from './IterationBlock'

interface ParallelExecutionContainerProps {
  branches: ParallelBranch[]
  workflowId: string
  intentId: string
  operations: Record<string, Operation>
}

export function ParallelExecutionContainer({
  branches,
  workflowId,
  intentId,
  operations,
}: ParallelExecutionContainerProps) {
  const [activeTab, setActiveTab] = useState<string | null>(
    branches.length > 0 ? branches[0].branchId : null
  )
  
  if (!branches || branches.length === 0) {
    return null
  }
  
  const activeBranch = branches.find(b => b.branchId === activeTab) || branches[0]
  
  const formatDuration = (sec?: number) => {
    if (!sec) return ''
    return `${sec.toFixed(1)}с`
  }
  
  return (
    <div className="parallel-execution-container">
      <div className="parallel-execution-header">
        <span className="parallel-icon">⚡</span>
        <span>Параллельное выполнение</span>
        <span className="parallel-stats">({branches.length} {branches.length === 1 ? 'ветка' : 'веток'})</span>
      </div>
      
      {/* Branch Tabs */}
      <div className="branch-tabs">
        {branches.map(branch => {
          const statusIcon = branch.status === 'completed' ? '✓' : 
                             branch.status === 'failed' ? '❌' : 
                             '⏳'
          const statusColor = branch.status === 'completed' ? '#4CAF50' : 
                              branch.status === 'failed' ? '#f44336' : 
                              '#2196F3'
          
          return (
            <div
              key={branch.branchId}
              className={`branch-tab ${activeTab === branch.branchId ? 'active' : ''}`}
              onClick={() => setActiveTab(branch.branchId)}
              style={{
                borderColor: activeTab === branch.branchId ? statusColor : undefined,
              }}
            >
              <span className="tab-status" style={{ color: statusColor }}>
                {statusIcon}
              </span>
              <span>{branch.description}</span>
              <span className="tab-meta">
                ({branch.iterations.length} {branch.iterations.length === 1 ? 'шаг' : 'шагов'}
                {branch.durationSec && `, ${formatDuration(branch.durationSec)}`})
              </span>
            </div>
          )
        })}
      </div>
      
      {/* Tab Content */}
      <div className="tab-content">
        {activeBranch.iterations.map((iteration, idx) => {
          const linkedOperation = iteration.operationId 
            ? operations[iteration.operationId]
            : undefined
          
          return (
            <IterationBlockComponent
              key={iteration.id || `${activeBranch.branchId}-iter-${iteration.iterationNumber}`}
              iteration={iteration}
              operation={linkedOperation}
              onToggleThinkingCollapse={() => {
                // Toggle thinking collapse для итерации в ветке
                useChatStore.setState((state) => {
                  const existingIntents = state.intentBlocks[workflowId] || []
                  const updatedIntents = existingIntents.map(intent => {
                    if (intent.id === intentId && intent.parallelBranches) {
                      const updatedBranches = intent.parallelBranches.map(branch => {
                        if (branch.branchId === activeBranch.branchId) {
                          const updatedIterations = branch.iterations.map(iter => {
                            if (iter.id === iteration.id || iter.iterationNumber === iteration.iterationNumber) {
                              const newCollapsedState = !iter.thinking.isCollapsed
                              console.log(`[ParallelExecutionContainer] Toggling thinking collapse for iteration ${iter.iterationNumber}: ${iter.thinking.isCollapsed} -> ${newCollapsedState}`)
                              return {
                                ...iter,
                                thinking: {
                                  ...iter.thinking,
                                  isCollapsed: newCollapsedState,
                                },
                              }
                            }
                            return iter
                          })
                          return {
                            ...branch,
                            iterations: updatedIterations,
                          }
                        }
                        return branch
                      })
                      return { ...intent, parallelBranches: updatedBranches }
                    }
                    return intent
                  })
                  return {
                    intentBlocks: {
                      ...state.intentBlocks,
                      [workflowId]: updatedIntents,
                    },
                  }
                })
              }}
              onToggleOperationCollapse={linkedOperation ? () => {
                useChatStore.getState().toggleOperationCollapse(workflowId, intentId, linkedOperation.id)
              } : undefined}
            />
          )
        })}
        
        {/* Branch-level error */}
        {activeBranch.error && (
          <div className="branch-error-message">
            <span className="error-icon">⚠️</span>
            <strong>Критическая ошибка:</strong> {activeBranch.error}
          </div>
        )}
        
        {/* Branch result summary - shown when branch completed */}
        {activeBranch.status === 'completed' && activeBranch.resultSummary && (
          <div className="branch-result-summary">
            <div className="result-content">{activeBranch.resultSummary}</div>
          </div>
        )}
      </div>
    </div>
  )
}
