import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

// Legacy reasoning step structure (used by UI components)
export interface ReasoningStep {
  type: 'thought' | 'tool_call' | 'tool_result' | 'decision' | string
  content: string
  data?: any
  timestamp?: string
}

// Reasoning block structure
export interface ReasoningBlock {
  id: string
  content: string
  isStreaming: boolean
  timestamp: string
}

// Answer block structure
export interface AnswerBlock {
  id: string
  content: string
  isStreaming: boolean
  timestamp: string
}

// Debug chunk structure for debug mode
export type DebugChunkType = 'thinking' | 'message_chunk' | 'tool_call' | 'tool_result' | 'error' | 'message_start' | 'message_complete'

export interface DebugChunk {
  id: string
  type: DebugChunkType
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

// Extended message structure for assistant messages with reasoning
export interface AssistantMessage {
  id: string
  role: 'assistant'
  timestamp: string
  reasoningBlocks: ReasoningBlock[]
  answerBlocks: AnswerBlock[]
  debugChunks?: DebugChunk[] // For debug mode
  toolCalls?: any[]
  isComplete: boolean
}

// Workflow plan structure
export interface WorkflowPlan {
  plan: string
  steps: string[]
  confirmationId: string | null
  awaitingConfirmation: boolean
  planThinking: string // Reasoning/thinking during plan generation
  planThinkingIsStreaming: boolean // Whether plan thinking is currently streaming
}

// Workflow step structure
export interface WorkflowStep {
  stepNumber: number
  title: string
  status: 'pending' | 'in_progress' | 'completed'
  thinking: string
  response: string
}

interface ChatState {
  messages: Message[]
  assistantMessages: Record<string, AssistantMessage> // message_id -> AssistantMessage
  currentSession: string | null
  isConnected: boolean
  isAgentTyping: boolean
  
  // Workflow state - stored per user message (keyed by message timestamp)
  workflows: Record<string, {
    plan: WorkflowPlan
    steps: Record<number, WorkflowStep> // step_number -> WorkflowStep
    currentStep: number | null
    finalResult: string | null
  }>
  activeWorkflowId: string | null // timestamp of the active (currently streaming) workflow
  
  // Legacy support (will be removed)
  streamingMessages: Record<string, Message>
  reasoningSteps: ReasoningStep[] // Legacy
  reasoningStartTime: number | null // Legacy
  
  addMessage: (message: Message) => void
  clearChat: () => void
  startNewSession: () => void
  setCurrentSession: (sessionId: string) => void
  setConnectionStatus: (connected: boolean) => void
  setAgentTyping: (typing: boolean) => void
  
  // New methods for reasoning/answer blocks
  startReasoningBlock: (messageId: string, blockId: string) => void
  updateReasoningBlock: (messageId: string, blockId: string, content: string) => void
  completeReasoningBlock: (messageId: string, blockId: string) => void
  
  startAnswerBlock: (messageId: string, blockId: string) => void
  updateAnswerBlock: (messageId: string, blockId: string, content: string) => void
  completeAnswerBlock: (messageId: string, blockId: string) => void
  
  // Debug mode methods
  addDebugChunk: (messageId: string, chunkType: DebugChunkType, content: string, metadata?: Record<string, any>) => void
  
  completeMessage: (messageId: string) => void
  
  // Workflow methods
  setActiveWorkflow: (workflowId: string) => void // Set/create active workflow
  getWorkflow: (workflowId: string) => { plan: WorkflowPlan | null, steps: Record<number, WorkflowStep>, currentStep: number | null } | null // Get workflow by ID
  setWorkflowPlan: (plan: string, steps: string[], confirmationId: string | null) => void // Works on active workflow
  updatePlanThinking: (content: string) => void // Works on active workflow
  setAwaitingConfirmation: (awaiting: boolean) => void // Works on active workflow
  startWorkflowStep: (stepNumber: number, title: string) => void // Works on active workflow
  updateStepThinking: (stepNumber: number, content: string) => void // Works on active workflow
  updateStepResponse: (stepNumber: number, content: string) => void // Works on active workflow
  completeWorkflowStep: (stepNumber: number) => void // Works on active workflow
  completeWorkflow: () => void // Works on active workflow
  setWorkflowFinalResult: (workflowId: string, finalResult: string) => void // Set final result for a workflow
  clearWorkflow: () => void // Clear all workflows (for testing/reset)
  
  // Legacy methods (for compatibility during transition)
  startStreamingMessage: (messageId: string, message: Message) => void
  updateStreamingMessage: (messageId: string, content: string) => void
  completeStreamingMessage: (messageId: string, content: string) => void
  getDisplayMessages: () => Message[]
  addReasoningStep: (step: any) => void // Legacy
  clearReasoningSteps: () => void // Legacy
  setReasoningStartTime: (time: number | null) => void // Legacy
  getReasoningDuration: () => number // Legacy
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      assistantMessages: {},
      currentSession: null,
      isConnected: false,
      isAgentTyping: false,
      workflows: {},
      activeWorkflowId: null,
      streamingMessages: {},
      reasoningSteps: [],
      reasoningStartTime: null,
      
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
        })),
      
      clearChat: () =>
        set({
          messages: [],
          assistantMessages: {},
          streamingMessages: {},
          reasoningSteps: [],
          reasoningStartTime: null,
          workflows: {},
          activeWorkflowId: null,
        }),
      
      startNewSession: () =>
        set({
          messages: [],
          assistantMessages: {},
          streamingMessages: {},
          currentSession: null,
          isAgentTyping: false,
          reasoningSteps: [],
          reasoningStartTime: null,
          workflows: {},
          activeWorkflowId: null,
        }),
      
      setCurrentSession: (sessionId) =>
        set({ currentSession: sessionId }),
      
      setConnectionStatus: (connected) =>
        set({ isConnected: connected }),
      
      setAgentTyping: (typing) =>
        set({ isAgentTyping: typing }),
      
      // Start a new reasoning block
      startReasoningBlock: (messageId: string, blockId: string) =>
        set((state) => {
          const existing = state.assistantMessages[messageId]
          
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:startReasoningBlock',message:'startReasoningBlock called - NOT creating message yet',data:{messageId,blockId,hasExisting:!!existing,existingReasoningBlocksCount:existing?.reasoningBlocks.length||0,existingAnswerBlocksCount:existing?.answerBlocks.length||0,willCreateInUpdate:!existing},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
          // #endregion
          
          // CRITICAL FIX: Don't create assistant message with empty block
          // Message will be created in updateReasoningBlock when content is available
          // This prevents empty blocks from being rendered
          if (existing) {
            // If message exists, we still need to add the block, but only if it doesn't exist
            const blockExists = existing.reasoningBlocks.some(b => b.id === blockId)
            if (blockExists) {
              return state // Block already exists, no change needed
            }
            const newBlock: ReasoningBlock = {
              id: blockId,
              content: '',
              isStreaming: true,
              timestamp: new Date().toISOString(),
            }
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  ...existing,
                  reasoningBlocks: [...existing.reasoningBlocks, newBlock],
                },
              },
            }
          } else {
            // Message doesn't exist - don't create it yet, wait for updateReasoningBlock
            // This prevents empty blocks from appearing in the UI
            return state
          }
        }),
      
      // Update reasoning block content (replace)
      updateReasoningBlock: (messageId: string, blockId: string, content: string) =>
        set((state) => {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateReasoningBlock-entry',message:'updateReasoningBlock called',data:{messageId,blockId,contentLength:content.length,hasMessage:!!state.assistantMessages[messageId],reasoningBlocksCount:state.assistantMessages[messageId]?.reasoningBlocks.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B,E'})}).catch(()=>{});
          // #endregion
          const message = state.assistantMessages[messageId]
          
          // CRITICAL FIX: Create message here if it doesn't exist and we have content
          // This ensures messages are only created when there's actual content to display
          if (!message) {
            // Only create message if we have content (non-empty)
            if (content && content.trim().length > 0) {
              const newBlock: ReasoningBlock = {
                id: blockId,
                content,
                isStreaming: true,
                timestamp: new Date().toISOString(),
              }
              const newMessage = {
                id: messageId,
                role: 'assistant' as const,
                timestamp: new Date().toISOString(),
                reasoningBlocks: [newBlock],
                answerBlocks: [],
                debugChunks: [],
                isComplete: false,
              }
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:createAssistantMessage-in-update',message:'Creating new assistantMessage in updateReasoningBlock with content',data:{messageId,reasoningBlocksCount:newMessage.reasoningBlocks.length,answerBlocksCount:newMessage.answerBlocks.length,firstReasoningBlockContentLength:newBlock.content.length,assistantMessagesCount:Object.keys(state.assistantMessages).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,C'})}).catch(()=>{});
              // #endregion
              return {
                assistantMessages: {
                  ...state.assistantMessages,
                  [messageId]: newMessage,
                },
              }
            } else {
              // No content yet, don't create message - wait for next update
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateReasoningBlock-no-message-no-content',message:'Message not found and no content yet - skipping',data:{messageId,contentLength:content.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
              // #endregion
              return state
            }
          }
          
          // Message exists - update the block
          const blockExists = message.reasoningBlocks.some(b => b.id === blockId)
          let updatedBlocks: ReasoningBlock[]
          
          if (blockExists) {
            // Block exists, update it
            updatedBlocks = message.reasoningBlocks.map((block) =>
              block.id === blockId
                ? { ...block, content, isStreaming: true }
                : block
            )
          } else {
            // Block doesn't exist, create it (this can happen if startReasoningBlock was skipped)
            const newBlock: ReasoningBlock = {
              id: blockId,
              content,
              isStreaming: true,
              timestamp: new Date().toISOString(),
            }
            updatedBlocks = [...message.reasoningBlocks, newBlock]
          }
          
          // #region agent log
          const foundBlock = updatedBlocks.find(b => b.id === blockId)
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateReasoningBlock-after-update',message:'After reasoning block update',data:{messageId,blockId,foundBlock:!!foundBlock,updatedContentLength:foundBlock?.content.length||0,updatedIsStreaming:foundBlock?.isStreaming,updatedBlocksCount:updatedBlocks.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
          // #endregion
          
          return {
            assistantMessages: {
              ...state.assistantMessages,
              [messageId]: {
                ...message,
                reasoningBlocks: updatedBlocks,
              },
            },
          }
        }),
      
      // Complete reasoning block
      completeReasoningBlock: (messageId: string, blockId: string) =>
        set((state) => {
          const message = state.assistantMessages[messageId]
          if (!message) return state
          
          const updatedBlocks = message.reasoningBlocks.map((block) =>
            block.id === blockId ? { ...block, isStreaming: false } : block
          )
          
          return {
            assistantMessages: {
              ...state.assistantMessages,
              [messageId]: {
                ...message,
                reasoningBlocks: updatedBlocks,
              },
            },
          }
        }),
      
      // Start a new answer block
      startAnswerBlock: (messageId: string, blockId: string) =>
        set((state) => {
          const existing = state.assistantMessages[messageId]
          
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:startAnswerBlock',message:'startAnswerBlock called - NOT creating message yet',data:{messageId,blockId,hasExisting:!!existing,existingReasoningBlocksCount:existing?.reasoningBlocks.length||0,existingAnswerBlocksCount:existing?.answerBlocks.length||0,willCreateInUpdate:!existing},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
          // #endregion
          
          // CRITICAL FIX: Don't create assistant message with empty block
          // Message will be created in updateAnswerBlock when content is available
          // This prevents empty blocks from being rendered
          if (existing) {
            // If message exists, we still need to add the block, but only if it doesn't exist
            const blockExists = existing.answerBlocks.some(b => b.id === blockId)
            if (blockExists) {
              return state // Block already exists, no change needed
            }
            const newBlock: AnswerBlock = {
              id: blockId,
              content: '',
              isStreaming: true,
              timestamp: new Date().toISOString(),
            }
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  ...existing,
                  answerBlocks: [...existing.answerBlocks, newBlock],
                },
              },
            }
          } else {
            // Message doesn't exist - don't create it yet, wait for updateAnswerBlock
            // This prevents empty blocks from appearing in the UI
            return state
          }
        }),
      
      // Update answer block content (replace)
      updateAnswerBlock: (messageId: string, blockId: string, content: string) =>
        set((state) => {
          const message = state.assistantMessages[messageId]
          
          // CRITICAL FIX: Create message here if it doesn't exist and we have content
          // This ensures messages are only created when there's actual content to display
          if (!message) {
            // Only create message if we have content (non-empty)
            if (content && content.trim().length > 0) {
              const newBlock: AnswerBlock = {
                id: blockId,
                content,
                isStreaming: true,
                timestamp: new Date().toISOString(),
              }
              const newMessage = {
                id: messageId,
                role: 'assistant' as const,
                timestamp: new Date().toISOString(),
                reasoningBlocks: [],
                answerBlocks: [newBlock],
                debugChunks: [],
                isComplete: false,
              }
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:createAssistantMessage-in-update-answer',message:'Creating new assistantMessage in updateAnswerBlock with content',data:{messageId,reasoningBlocksCount:newMessage.reasoningBlocks.length,answerBlocksCount:newMessage.answerBlocks.length,firstAnswerBlockContentLength:newBlock.content.length,assistantMessagesCount:Object.keys(state.assistantMessages).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,C'})}).catch(()=>{});
              // #endregion
              return {
                assistantMessages: {
                  ...state.assistantMessages,
                  [messageId]: newMessage,
                },
              }
            } else {
              // No content yet, don't create message - wait for next update
              // #region agent log
              fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateAnswerBlock-no-message-no-content',message:'Message not found and no content yet - skipping',data:{messageId,contentLength:content.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
              // #endregion
              return state
            }
          }
          
          // Message exists - update the block
          const blockExists = message.answerBlocks.some(b => b.id === blockId)
          let updatedBlocks: AnswerBlock[]
          
          if (blockExists) {
            // Block exists, update it
            updatedBlocks = message.answerBlocks.map((block) =>
              block.id === blockId
                ? { ...block, content, isStreaming: true }
                : block
            )
          } else {
            // Block doesn't exist, create it (this can happen if startAnswerBlock was skipped)
            const newBlock: AnswerBlock = {
              id: blockId,
              content,
              isStreaming: true,
              timestamp: new Date().toISOString(),
            }
            updatedBlocks = [...message.answerBlocks, newBlock]
          }
          
          return {
            assistantMessages: {
              ...state.assistantMessages,
              [messageId]: {
                ...message,
                answerBlocks: updatedBlocks,
              },
            },
          }
        }),
      
      // Complete answer block
      completeAnswerBlock: (messageId: string, blockId: string) =>
        set((state) => {
          const message = state.assistantMessages[messageId]
          if (!message) return state
          
          const updatedBlocks = message.answerBlocks.map((block) =>
            block.id === blockId ? { ...block, isStreaming: false } : block
          )
          
          return {
            assistantMessages: {
              ...state.assistantMessages,
              [messageId]: {
                ...message,
                answerBlocks: updatedBlocks,
              },
            },
          }
        }),
      
      // Add debug chunk (for debug mode)
      addDebugChunk: (messageId: string, chunkType: DebugChunkType, content: string, metadata?: Record<string, any>) =>
        set((state) => {
          const existing = state.assistantMessages[messageId]
          const chunkId = `debug-${Date.now()}-${Math.random()}`
          const newChunk: DebugChunk = {
            id: chunkId,
            type: chunkType,
            content: content,
            timestamp: new Date().toISOString(),
            metadata: metadata,
          }
          
          if (existing) {
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  ...existing,
                  debugChunks: [...(existing.debugChunks || []), newChunk],
                },
              },
            }
          } else {
            // CRITICAL FIX: Don't create assistant message with only debug chunks and no content blocks
            // Debug chunks are only shown in debug mode, and we don't want empty messages in normal mode
            // Only create message if we have actual content (reasoning or answer blocks will be added later)
            // For now, skip creating message - it will be created when reasoning/answer blocks are added
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:addDebugChunk-skip-create',message:'Skipping assistant message creation from addDebugChunk - will create when content blocks arrive',data:{messageId,chunkType:chunkType,chunkContent:content.substring(0,50),assistantMessagesCount:Object.keys(state.assistantMessages).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
            // #endregion
            return state
          }
        }),
      
      // Complete entire message (move to regular messages)
      completeMessage: (messageId: string) =>
        set((state) => {
          const assistantMsg = state.assistantMessages[messageId]
          if (!assistantMsg) return state
          
          // Combine all answer blocks into final content
          const finalContent = assistantMsg.answerBlocks
            .map((block) => block.content)
            .join('\n\n')
            .trim()
          
          if (finalContent) {
            const finalMessage: Message = {
              role: 'assistant',
              content: finalContent,
              timestamp: assistantMsg.timestamp,
              metadata: {
                reasoningBlocks: assistantMsg.reasoningBlocks,
                toolCalls: assistantMsg.toolCalls,
              },
            }
            
            const newAssistantMessages = { ...state.assistantMessages }
            delete newAssistantMessages[messageId]
            
            return {
              messages: [...state.messages, finalMessage],
              assistantMessages: newAssistantMessages,
            }
          }
          
          return state
        }),
      
      // Legacy methods (for compatibility)
      startStreamingMessage: (messageId: string, message: Message) =>
        set((state) => ({
          streamingMessages: {
            ...state.streamingMessages,
            [messageId]: message,
          },
        })),
      
      updateStreamingMessage: (messageId: string, content: string) =>
        set((state) => {
          const streamingMsg = state.streamingMessages[messageId]
          if (streamingMsg) {
            return {
              streamingMessages: {
                ...state.streamingMessages,
                [messageId]: {
                  ...streamingMsg,
                  content: content,
                },
              },
            }
          }
          return state
        }),
      
      completeStreamingMessage: (messageId: string, content: string) =>
        set((state) => {
          const streamingMsg = state.streamingMessages[messageId]
          if (streamingMsg) {
            const finalMessage: Message = {
              ...streamingMsg,
              content: content,
              timestamp: new Date().toISOString(),
            }
            
            const newStreamingMessages = { ...state.streamingMessages }
            delete newStreamingMessages[messageId]
            
            return {
              messages: [...state.messages, finalMessage],
              streamingMessages: newStreamingMessages,
            }
          }
          return state
        }),
      
      getDisplayMessages: () => {
        const state = get()
        const streamingArray = Object.values(state.streamingMessages)
        return [...state.messages, ...streamingArray]
      },
      
      // Legacy reasoning methods
      addReasoningStep: (step: any) =>
        set((state) => {
          const startTime = state.reasoningStartTime || Date.now()
          return {
            reasoningSteps: [...state.reasoningSteps, step],
            reasoningStartTime: startTime,
          }
        }),
      
      clearReasoningSteps: () =>
        set({ reasoningSteps: [], reasoningStartTime: null }),
      
      setReasoningStartTime: (time) =>
        set({ reasoningStartTime: time }),
      
      getReasoningDuration: () => {
        const state = get()
        if (!state.reasoningStartTime) return 0
        return Math.floor((Date.now() - state.reasoningStartTime) / 1000)
      },
      
      // Workflow methods
      setActiveWorkflow: (workflowId: string) =>
        set((state) => {
          // Create workflow if it doesn't exist
          if (!state.workflows[workflowId]) {
            return {
              workflows: {
                ...state.workflows,
                [workflowId]: {
                  plan: {
                    plan: '',
                    steps: [],
                    confirmationId: null,
                    awaitingConfirmation: false,
                    planThinking: '',
                    planThinkingIsStreaming: false,
                  },
                  steps: {},
                  currentStep: null,
                  finalResult: null,
                },
              },
              activeWorkflowId: workflowId,
            }
          }
          // Just set as active if it exists
          return {
            activeWorkflowId: workflowId,
          }
        }),
      
      getWorkflow: (workflowId: string) => {
        const state = get()
        const workflow = state.workflows[workflowId]
        if (!workflow) return null
        return {
          plan: workflow.plan,
          steps: workflow.steps,
          currentStep: workflow.currentStep,
        }
      },
      
      setWorkflowPlan: (plan: string, steps: string[], confirmationId: string | null) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:setWorkflowPlan-entry',message:'setWorkflowPlan called',data:{planLength:plan.length,stepsCount:steps.length,confirmationId},timestamp:Date.now(),sessionId:'debug-session',runId:'verify',hypothesisId:'STORE'})}).catch(()=>{});
        // #endregion
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) {
            console.warn('[chatStore] setWorkflowPlan called but no activeWorkflowId')
            return state
          }
          const workflow = state.workflows[activeId]
          if (!workflow) {
            console.warn('[chatStore] setWorkflowPlan called but workflow not found:', activeId)
            return state
          }
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                plan: {
                  plan,
                  steps,
                  confirmationId,
                  awaitingConfirmation: false,
                  planThinking: workflow.plan.planThinking, // Preserve existing thinking
                  planThinkingIsStreaming: false, // Plan generation is complete, stop streaming
                },
                steps: {}, // Reset steps when new plan is set
                currentStep: null,
              },
            },
          }
        })
        // #region agent log
        const state = get()
        const activeId = state.activeWorkflowId
        const workflow = activeId ? state.workflows[activeId] : null
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:setWorkflowPlan-after',message:'After setWorkflowPlan',data:{activeWorkflowId:activeId,hasWorkflow:!!workflow,planLength:workflow?.plan.plan.length||0,stepsCount:workflow?.plan.steps.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'verify',hypothesisId:'STORE'})}).catch(()=>{});
        // #endregion
      },
      
      setAwaitingConfirmation: (awaiting: boolean) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow) return state
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                plan: {
                  ...workflow.plan,
                  awaitingConfirmation: awaiting,
                },
              },
            },
          }
        }),
      
      updatePlanThinking: (content: string) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) {
            console.warn('[chatStore] updatePlanThinking called but no activeWorkflowId')
            return state
          }
          const workflow = state.workflows[activeId]
          if (!workflow) {
            console.warn('[chatStore] updatePlanThinking called but workflow not found:', activeId)
            return state
          }
          // Accumulate content for streaming chunks (server sends incremental chunks)
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                plan: {
                  ...workflow.plan,
                  planThinking: workflow.plan.planThinking + content,
                  planThinkingIsStreaming: true, // Mark as streaming when content is added
                },
              },
            },
          }
        }),
      
      startWorkflowStep: (stepNumber: number, title: string) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) {
            console.warn('[chatStore] startWorkflowStep called but no activeWorkflowId')
            return state
          }
          const workflow = state.workflows[activeId]
          if (!workflow) {
            console.warn('[chatStore] startWorkflowStep called but workflow not found:', activeId)
            return state
          }
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:startWorkflowStep-entry',message:'startWorkflowStep called',data:{stepNumber,title,activeWorkflowId:activeId,hasWorkflow:!!workflow,existingStepsCount:Object.keys(workflow.steps).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'STEP'})}).catch(()=>{});
          // #endregion
          const newSteps = { ...workflow.steps }
          newSteps[stepNumber] = {
            stepNumber,
            title,
            status: 'in_progress',
            thinking: '',
            response: '',
          }
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:startWorkflowStep-after',message:'After startWorkflowStep update',data:{stepNumber,newStepsCount:Object.keys(newSteps).length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'STEP'})}).catch(()=>{});
          // #endregion
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                steps: newSteps,
                currentStep: stepNumber,
              },
            },
          }
        }),
      
      updateStepThinking: (stepNumber: number, content: string) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow) return state
          const step = workflow.steps[stepNumber]
          if (!step) return state
          
          // Append content for streaming chunks (server sends incremental chunks)
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                steps: {
                  ...workflow.steps,
                  [stepNumber]: {
                    ...step,
                    thinking: step.thinking + content,
                  },
                },
              },
            },
          }
        }),
      
      updateStepResponse: (stepNumber: number, content: string) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow) return state
          const step = workflow.steps[stepNumber]
          if (!step) return state
          
          // Append content for streaming chunks (server sends incremental chunks)
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                steps: {
                  ...workflow.steps,
                  [stepNumber]: {
                    ...step,
                    response: step.response + content,
                  },
                },
              },
            },
          }
        }),
      
      completeWorkflowStep: (stepNumber: number) =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow) return state
          const step = workflow.steps[stepNumber]
          if (!step) return state
          
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                steps: {
                  ...workflow.steps,
                  [stepNumber]: {
                    ...step,
                    status: 'completed',
                  },
                },
                currentStep: workflow.currentStep === stepNumber ? null : workflow.currentStep,
              },
            },
          }
        }),
      
      completeWorkflow: () =>
        set((state) => {
          const activeId = state.activeWorkflowId
          if (!activeId) return state
          const workflow = state.workflows[activeId]
          if (!workflow) return state
          
          // Mark all steps as completed and clear active workflow
          const completedSteps = Object.fromEntries(
            Object.entries(workflow.steps).map(([key, step]) => [
              key,
              { ...step, status: 'completed' as const }
            ])
          )
          
          return {
            workflows: {
              ...state.workflows,
              [activeId]: {
                ...workflow,
                steps: completedSteps,
                currentStep: null,
              },
            },
            // Don't clear activeWorkflowId - keep it so workflow remains visible
            // It will be replaced when a new workflow starts
          }
        }),
      
      setWorkflowFinalResult: (workflowId: string, finalResult: string) =>
        set((state) => {
          const workflow = state.workflows[workflowId]
          if (!workflow) return state
          
          return {
            workflows: {
              ...state.workflows,
              [workflowId]: {
                ...workflow,
                finalResult: finalResult,
              },
            },
          }
        }),
      
      clearWorkflow: () =>
        set({
          workflows: {},
          activeWorkflowId: null,
        }),
    }),
    {
      name: 'chat-storage',
      version: 5, // Increment version for new structure
      migrate: (persistedState: any, version: number) => {
        if (version < 5) {
          return {
            messages: [],
            assistantMessages: {},
            currentSession: null,
            isConnected: false,
            isAgentTyping: false,
            streamingMessages: {},
            reasoningSteps: [],
            reasoningStartTime: null,
          }
        }
        return persistedState
      },
      partialize: (state) => ({
        // Don't persist messages - always start with empty chat
        currentSession: state.currentSession,
        // Don't persist workflows - always start with clean state
        // Don't persist assistantMessages or streamingMessages - they're temporary
      }),
    }
  )
)
