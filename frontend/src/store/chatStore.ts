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
  
  // Workflow state
  workflowPlan: WorkflowPlan | null
  workflowSteps: Record<number, WorkflowStep> // step_number -> WorkflowStep
  currentWorkflowStep: number | null
  
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
  setWorkflowPlan: (plan: string, steps: string[], confirmationId: string | null) => void
  updatePlanThinking: (content: string) => void
  setAwaitingConfirmation: (awaiting: boolean) => void
  startWorkflowStep: (stepNumber: number, title: string) => void
  updateStepThinking: (stepNumber: number, content: string) => void
  updateStepResponse: (stepNumber: number, content: string) => void
  completeWorkflowStep: (stepNumber: number) => void
  completeWorkflow: () => void
  clearWorkflow: () => void
  
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
      workflowPlan: null,
      workflowSteps: {},
      currentWorkflowStep: null,
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
          workflowPlan: null,
          workflowSteps: {},
          currentWorkflowStep: null,
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
          workflowPlan: null,
          workflowSteps: {},
          currentWorkflowStep: null,
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
          const newBlock: ReasoningBlock = {
            id: blockId,
            content: '',
            isStreaming: true,
            timestamp: new Date().toISOString(),
          }
          
          if (existing) {
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
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  id: messageId,
                  role: 'assistant',
                  timestamp: new Date().toISOString(),
                  reasoningBlocks: [newBlock],
                  answerBlocks: [],
                  debugChunks: [],
                  isComplete: false,
                },
              },
            }
          }
        }),
      
      // Update reasoning block content (replace)
      updateReasoningBlock: (messageId: string, blockId: string, content: string) =>
        set((state) => {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateReasoningBlock-entry',message:'updateReasoningBlock called',data:{messageId,blockId,contentLength:content.length,hasMessage:!!state.assistantMessages[messageId],reasoningBlocksCount:state.assistantMessages[messageId]?.reasoningBlocks.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B,E'})}).catch(()=>{});
          // #endregion
          const message = state.assistantMessages[messageId]
          if (!message) {
            // #region agent log
            fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:updateReasoningBlock-no-message',message:'Message not found in assistantMessages',data:{messageId,allMessageIds:Object.keys(state.assistantMessages)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
            // #endregion
            return state
          }
          
          const updatedBlocks = message.reasoningBlocks.map((block) =>
            block.id === blockId
              ? { ...block, content, isStreaming: true }
              : block
          )
          
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
          const newBlock: AnswerBlock = {
            id: blockId,
            content: '',
            isStreaming: true,
            timestamp: new Date().toISOString(),
          }
          
          if (existing) {
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
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  id: messageId,
                  role: 'assistant',
                  timestamp: new Date().toISOString(),
                  reasoningBlocks: [],
                  answerBlocks: [newBlock],
                  debugChunks: [],
                  isComplete: false,
                },
              },
            }
          }
        }),
      
      // Update answer block content (replace)
      updateAnswerBlock: (messageId: string, blockId: string, content: string) =>
        set((state) => {
          const message = state.assistantMessages[messageId]
          if (!message) return state
          
          const updatedBlocks = message.answerBlocks.map((block) =>
            block.id === blockId
              ? { ...block, content, isStreaming: true }
              : block
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
            return {
              assistantMessages: {
                ...state.assistantMessages,
                [messageId]: {
                  id: messageId,
                  role: 'assistant',
                  timestamp: new Date().toISOString(),
                  reasoningBlocks: [],
                  answerBlocks: [],
                  debugChunks: [newChunk],
                  isComplete: false,
                },
              },
            }
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
      setWorkflowPlan: (plan: string, steps: string[], confirmationId: string | null) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:setWorkflowPlan-entry',message:'setWorkflowPlan called',data:{planLength:plan.length,stepsCount:steps.length,confirmationId},timestamp:Date.now(),sessionId:'debug-session',runId:'verify',hypothesisId:'STORE'})}).catch(()=>{});
        // #endregion
        set((state) => ({
          workflowPlan: {
            plan,
            steps,
            confirmationId,
            awaitingConfirmation: false,
            planThinking: state.workflowPlan?.planThinking || '', // Preserve existing thinking if any
            planThinkingIsStreaming: false, // Plan generation is complete, stop streaming
          },
          workflowSteps: {},
          currentWorkflowStep: null,
        }))
        // #region agent log
        const state = get()
        fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'chatStore.ts:setWorkflowPlan-after',message:'After setWorkflowPlan',data:{hasWorkflowPlan:!!state.workflowPlan,planLength:state.workflowPlan?.plan.length||0,stepsCount:state.workflowPlan?.steps.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'verify',hypothesisId:'STORE'})}).catch(()=>{});
        // #endregion
      },
      
      setAwaitingConfirmation: (awaiting: boolean) =>
        set((state) => ({
          workflowPlan: state.workflowPlan
            ? { ...state.workflowPlan, awaitingConfirmation: awaiting }
            : null,
        })),
      
      updatePlanThinking: (content: string) =>
        set((state) => {
          // If workflowPlan doesn't exist yet, initialize it
          if (!state.workflowPlan) {
            return {
              workflowPlan: {
                plan: '',
                steps: [],
                confirmationId: null,
                awaitingConfirmation: false,
                planThinking: content,
                planThinkingIsStreaming: true,
              },
            }
          }
          // Otherwise, update existing plan thinking
          return {
            workflowPlan: {
              ...state.workflowPlan,
              planThinking: state.workflowPlan.planThinking + content,
              planThinkingIsStreaming: true, // Mark as streaming when content is added
            },
          }
        }),
      
      startWorkflowStep: (stepNumber: number, title: string) =>
        set((state) => {
          const newSteps = { ...state.workflowSteps }
          newSteps[stepNumber] = {
            stepNumber,
            title,
            status: 'in_progress',
            thinking: '',
            response: '',
          }
          return {
            workflowSteps: newSteps,
            currentWorkflowStep: stepNumber,
          }
        }),
      
      updateStepThinking: (stepNumber: number, content: string) =>
        set((state) => {
          const step = state.workflowSteps[stepNumber]
          if (!step) return state
          
          return {
            workflowSteps: {
              ...state.workflowSteps,
              [stepNumber]: {
                ...step,
                thinking: step.thinking + content, // Append for streaming
              },
            },
          }
        }),
      
      updateStepResponse: (stepNumber: number, content: string) =>
        set((state) => {
          const step = state.workflowSteps[stepNumber]
          if (!step) return state
          
          return {
            workflowSteps: {
              ...state.workflowSteps,
              [stepNumber]: {
                ...step,
                response: step.response + content, // Append for streaming
              },
            },
          }
        }),
      
      completeWorkflowStep: (stepNumber: number) =>
        set((state) => {
          const step = state.workflowSteps[stepNumber]
          if (!step) return state
          
          return {
            workflowSteps: {
              ...state.workflowSteps,
              [stepNumber]: {
                ...step,
                status: 'completed',
              },
            },
            currentWorkflowStep: state.currentWorkflowStep === stepNumber ? null : state.currentWorkflowStep,
          }
        }),
      
      completeWorkflow: () =>
        set((state) => ({
          ...state, // Preserve all state fields including workflowPlan
          // Don't clear workflowPlan - keep it visible so user can see what was completed
          // Only clear active step tracking
          currentWorkflowStep: null,
          // Mark all steps as completed if they exist
          workflowSteps: Object.fromEntries(
            Object.entries(state.workflowSteps).map(([key, step]) => [
              key,
              { ...step, status: 'completed' as const }
            ])
          ),
        })),
      
      clearWorkflow: () =>
        set({
          workflowPlan: null,
          workflowSteps: {},
          currentWorkflowStep: null,
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
        messages: state.messages,
        currentSession: state.currentSession,
        workflowPlan: state.workflowPlan, // Persist workflow plan for debugging
        // Don't persist assistantMessages or streamingMessages - they're temporary
      }),
    }
  )
)
