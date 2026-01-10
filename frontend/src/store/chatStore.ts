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

// Extended message structure for assistant messages with reasoning
export interface AssistantMessage {
  id: string
  role: 'assistant'
  timestamp: string
  reasoningBlocks: ReasoningBlock[]
  answerBlocks: AnswerBlock[]
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

// File preview data structure
export interface FilePreviewData {
  type: 'sheets' | 'docs' | 'slides' | 'code' | 'email' | 'chart'
  title: string
  subtitle?: string
  fileId: string
  fileUrl?: string
  previewData: {
    rows?: string[][]
    text?: string
    thumbnailUrl?: string
    presentationId?: string
    code?: string
    language?: string
    subject?: string
    body?: string
    chartType?: string
    series?: any[]
  }
}

// Workflow step structure
export interface WorkflowStep {
  stepNumber: number
  title: string
  status: 'pending' | 'in_progress' | 'completed'
  thinking: string
  response: string
  filePreview?: FilePreviewData
}

// ActionMessage - для отображения действий агента (Cursor-style)
export interface ActionMessageData {
  id: string
  icon: 'search' | 'file' | 'api' | 'email' | 'calendar' | 'process' | 'tool'
  status: 'pending' | 'in_progress' | 'success' | 'error' | 'alternative'
  title: string
  description?: string
  details?: string
  error?: string
  alternativeUsed?: string
  timestamp: string
}

// QuestionMessage - для уточняющих вопросов (Plan mode)
export interface QuestionMessageData {
  id: string
  text: string
  items: Array<{
    id: string
    type: 'radio' | 'checkbox' | 'text'
    label: string
    options?: string[]
    value?: string | string[]
  }>
  isAnswered: boolean
  timestamp: string
}

// ResultSummary - итоговый результат с метриками
export interface ResultSummary {
  completedTasks: string[]
  failedTasks: Array<{ task: string; error: string }>
  alternativesUsed: string[]
  duration?: number
  tokensUsed?: number
}

// ThinkingBlock - блок мышления (как в Cursor IDE)
export interface ThinkingBlock {
  id: string
  status: 'started' | 'streaming' | 'completed' | 'error'
  content: string              // Accumulated text
  elapsedSeconds: number
  startedAt: number            // timestamp
  completedAt?: number         // timestamp
  isCollapsed: boolean
  isPinned: boolean
  stepHistory: Array<{        // История шагов для отображения
    type: 'analyzing' | 'searching' | 'executing' | 'observing' | 'success' | 'error'
    text: string
    timestamp: number
  }>
}

// IntentBlock - блок намерения (Cursor-style: заголовок + сворачиваемые детали)
export type IntentDetailType = 'search' | 'read' | 'execute' | 'analyze' | 'write'

export interface IntentDetail {
  type: IntentDetailType
  description: string
  timestamp: number
}

// Operation - операция со стримингом данных
export type OperationType = 'read' | 'search' | 'write' | 'create' | 'update'
export type FileType = 'sheets' | 'docs' | 'slides' | 'calendar' | 'gmail' | 'drive'

export interface Operation {
  id: string
  intentId?: string
  title: string              // "Записываем послесловие"
  streamingTitle: string     // "Сказка.docx"
  operationType: OperationType
  status: 'pending' | 'streaming' | 'completed'
  summary?: string           // "Записано 324 символа"
  data: string[]             // Данные стриминга
  isCollapsed: boolean
  // Для автооткрытия в панели
  fileId?: string
  fileUrl?: string
  fileType?: FileType
}

// Фаза выполнения intent
export type IntentPhase = 'planning' | 'executing' | 'completed'

export interface IntentBlock {
  id: string
  intent: string                    // "Создание встречи с bsn@lad24.ru"
  status: 'started' | 'streaming' | 'completed'
  phase: IntentPhase                // Текущая фаза: planning -> executing -> completed
  details: IntentDetail[]           // Список деталей выполнения (фаза executing) - устаревший формат
  operations: Record<string, Operation> // operation_id -> Operation (новый формат)
  thinkingText?: string             // Streaming thinking text (фаза planning)
  summary?: string                  // "Найдено 5 встреч" - показывается в свёрнутом виде
  isCollapsed: boolean
  planningCollapsed: boolean        // Свёрнута ли секция "Планирую"
  executingCollapsed: boolean       // Свёрнута ли секция "Выполняю"
  // Прогресс (из SmartProgress)
  progressPercent: number           // 0-100
  elapsedSec: number
  estimatedSec: number
  startedAt: number
  completedAt?: number
}

interface ChatState {
  messages: Message[]
  assistantMessages: Record<string, AssistantMessage> // message_id -> AssistantMessage
  currentSession: string | null
  isConnected: boolean
  isAgentTyping: boolean
  showThinkingIndicator: boolean // Показывать "Думаю..." перед первым intent
  
  // SmartProgress state - контекстные progress-сообщения
  smartProgress: {
    isActive: boolean
    message: string
    elapsedSec: number
    estimatedSec: number
    progressPercent: number
  } | null
  
  // Workflow state - stored per user message (keyed by message timestamp)
  workflows: Record<string, {
    plan: WorkflowPlan
    steps: Record<number, WorkflowStep> // step_number -> WorkflowStep
    currentStep: number | null
    finalResult: string | null
  }>
  activeWorkflowId: string | null // timestamp of the active (currently streaming) workflow
  
  // User assistance request state
  userAssistanceRequest: {
    assistance_id: string
    question: string
    options: Array<{ id: string; label: string; description?: string; data?: any }>
    context?: any
  } | null
  
  // Action messages - действия агента (Cursor-style)
  actionMessages: Record<string, ActionMessageData[]> // workflowId -> ActionMessageData[]
  
  // Question messages - уточняющие вопросы (Plan mode)
  questionMessages: Record<string, QuestionMessageData[]> // workflowId -> QuestionMessageData[]
  
  // Result summaries - итоговые результаты
  resultSummaries: Record<string, ResultSummary> // workflowId -> ResultSummary
  
  // Current action indicator - для динамического отображения текущего действия
  currentAction: { tool: string; description: string } | null
  
  // Thinking blocks - блоки мышления (как в Cursor IDE)
  thinkingBlocks: Record<string, ThinkingBlock> // thinking_id -> ThinkingBlock
  activeThinkingId: string | null // Текущий активный thinking блок
  
  // Intent blocks - блоки намерений (Cursor-style: заголовок + детали)
  intentBlocks: Record<string, IntentBlock[]> // workflowId -> IntentBlock[]
  activeIntentId: string | null // Текущий активный intent блок
  
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
  setShowThinkingIndicator: (show: boolean) => void
  
  // SmartProgress methods
  startSmartProgress: (estimatedSec: number, goal: string) => void
  updateSmartProgress: (message: string, elapsedSec: number, estimatedSec: number, progressPercent: number) => void
  stopSmartProgress: () => void
  
  // New methods for reasoning/answer blocks
  startReasoningBlock: (messageId: string, blockId: string) => void
  updateReasoningBlock: (messageId: string, blockId: string, content: string) => void
  completeReasoningBlock: (messageId: string, blockId: string) => void
  
  startAnswerBlock: (messageId: string, blockId: string) => void
  updateAnswerBlock: (messageId: string, blockId: string, content: string) => void
  completeAnswerBlock: (messageId: string, blockId: string) => void
  
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
  setStepFilePreview: (stepNumber: number, filePreview: FilePreviewData) => void // Works on active workflow
  completeWorkflowStep: (stepNumber: number) => void // Works on active workflow
  completeWorkflow: () => void // Works on active workflow
  setWorkflowFinalResult: (workflowId: string, finalResult: string) => void // Set final result for a workflow
  updateWorkflowFinalResult: (workflowId: string, content: string) => void // Update final result content (for streaming)
  clearWorkflow: () => void // Clear all workflows (for testing/reset)
  
  // User assistance methods
  setUserAssistanceRequest: (request: {
    assistance_id: string
    question: string
    options: Array<{ id: string; label: string; description?: string; data?: any }>
    context?: any
  } | null) => void
  clearUserAssistanceRequest: () => void
  
  // Action message methods
  addAction: (workflowId: string, action: ActionMessageData) => void
  updateAction: (workflowId: string, actionId: string, updates: Partial<ActionMessageData>) => void
  clearActions: (workflowId: string) => void
  
  // Question message methods
  addQuestion: (workflowId: string, question: QuestionMessageData) => void
  updateQuestionAnswer: (workflowId: string, questionId: string, answers: Record<string, string | string[]>) => void
  clearQuestions: (workflowId: string) => void
  
  // Result summary methods
  setResultSummary: (workflowId: string, summary: ResultSummary) => void
  updateResultSummary: (workflowId: string, updates: Partial<ResultSummary>) => void
  clearResultSummary: (workflowId: string) => void
  
  // Current action methods
  setCurrentAction: (action: { tool: string; description: string } | null) => void
  clearCurrentAction: () => void
  
  // Thinking block methods
  startThinking: (thinkingId: string) => void
  appendThinkingChunk: (thinkingId: string, chunk: string, elapsedSeconds: number, stepType?: 'analyzing' | 'searching' | 'executing' | 'observing' | 'success' | 'error') => void
  completeThinking: (thinkingId: string, autoCollapse: boolean) => void
  toggleThinkingCollapse: (thinkingId: string) => void
  toggleThinkingPin: (thinkingId: string) => void
  setActiveThinking: (thinkingId: string | null) => void
  
  // Intent block methods (Cursor-style)
  startIntent: (workflowId: string, intentId: string, intentText: string) => void
  addIntentDetail: (workflowId: string, intentId: string, detail: IntentDetail) => void
  clearIntentThinking: (workflowId: string, intentId: string) => void
  appendIntentThinking: (workflowId: string, intentId: string, text: string) => void
  setIntentPhase: (workflowId: string, intentId: string, phase: IntentPhase) => void
  setIntentProgress: (workflowId: string, intentId: string, percent: number, elapsed: number, estimated: number) => void
  toggleIntentPhase: (workflowId: string, intentId: string, phase: 'planning' | 'executing') => void
  completeIntent: (workflowId: string, intentId: string, autoCollapse: boolean, summary?: string) => void
  toggleIntentCollapse: (workflowId: string, intentId: string) => void
  collapseIntent: (workflowId: string, intentId: string) => void
  collapseAllIntents: (workflowId: string) => void
  clearIntents: (workflowId: string) => void
  setActiveIntent: (intentId: string | null) => void
  
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
      showThinkingIndicator: false,
      smartProgress: null,
      workflows: {},
      activeWorkflowId: null,
      userAssistanceRequest: null,
      actionMessages: {},
      questionMessages: {},
      resultSummaries: {},
      currentAction: null,
      thinkingBlocks: {},
      activeThinkingId: null,
      intentBlocks: {},
      activeIntentId: null,
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
          actionMessages: {},
          questionMessages: {},
          resultSummaries: {},
          currentAction: null,
          thinkingBlocks: {},
          activeThinkingId: null,
          intentBlocks: {},
          activeIntentId: null,
          showThinkingIndicator: false,
        }),
      
      startNewSession: () =>
        set({
          messages: [],
          assistantMessages: {},
          streamingMessages: {},
          currentSession: null,
          isAgentTyping: false,
          showThinkingIndicator: false,
          smartProgress: null,
          reasoningSteps: [],
          reasoningStartTime: null,
          workflows: {},
          activeWorkflowId: null,
          actionMessages: {},
          questionMessages: {},
          resultSummaries: {},
          currentAction: null,
          thinkingBlocks: {},
          activeThinkingId: null,
          intentBlocks: {},
          activeIntentId: null,
        }),
      
      setCurrentSession: (sessionId) =>
        set({ currentSession: sessionId }),
      
      setConnectionStatus: (connected) =>
        set({ isConnected: connected }),
      
      setAgentTyping: (typing) => {
        // При завершении (typing=false) также скрываем индикатор "Думаю..."
        if (!typing) {
          set({ isAgentTyping: typing, showThinkingIndicator: false })
        } else {
          set({ isAgentTyping: typing })
        }
      },
      
      setShowThinkingIndicator: (show) => {
        set({ showThinkingIndicator: show })
      },
      
      // SmartProgress methods
      startSmartProgress: (estimatedSec: number, goal: string) => {
        set({
          smartProgress: {
            isActive: true,
            message: 'Анализирую задачу...',
            elapsedSec: 0,
            estimatedSec: estimatedSec,
            progressPercent: 0
          }
        })
      },
      
      updateSmartProgress: (message: string, elapsedSec: number, estimatedSec: number, progressPercent: number) => {
        set((state) => {
          if (state.smartProgress) {
            return {
              smartProgress: {
                ...state.smartProgress,
                message,
                elapsedSec,
                estimatedSec,
                progressPercent
              }
            }
          }
          return state
        })
      },
      
      stopSmartProgress: () => {
        set({ smartProgress: null })
      },
      
      // Start a new reasoning block
      startReasoningBlock: (messageId: string, blockId: string) =>
        set((state) => {
          const existing = state.assistantMessages[messageId]// CRITICAL FIX: Don't create assistant message with empty block
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
        set((state) => {const message = state.assistantMessages[messageId]
          
          // CRITICAL FIX: Create message here if it doesn't exist and we have content
          // This ensures messages are only created when there's actual content to display
          if (!message) {
            // Only create message if we have content (non-empty)
            if (content && content.trim().length > 0) {
              console.log('[chatStore] updateReasoningBlock: Creating new assistant message', { messageId, blockId, contentLength: content.length, contentPreview: content.substring(0, 100) })
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
                isComplete: false,
              }
              console.log('[chatStore] updateReasoningBlock: New message created', { messageId, reasoningBlocksCount: newMessage.reasoningBlocks.length })
              return {
                assistantMessages: {
                  ...state.assistantMessages,
                  [messageId]: newMessage,
                },
              }
            } else {
              // No content yet, don't create message - wait for next update
              console.log('[chatStore] updateReasoningBlock: No content, not creating message yet', { messageId, blockId, contentLength: content?.length })
              return state
            }
          }
          
          // Message exists - update the block
          const blockExists = message.reasoningBlocks.some(b => b.id === blockId)
          let updatedBlocks: ReasoningBlock[]
          
          if (blockExists) {
            // Block exists, update it
            console.log('[chatStore] updateReasoningBlock: Updating existing block', { messageId, blockId, contentLength: content.length })
            updatedBlocks = message.reasoningBlocks.map((block) =>
              block.id === blockId
                ? { ...block, content, isStreaming: true }
                : block
            )
          } else {
            // Block doesn't exist, create it (this can happen if startReasoningBlock was skipped)
            console.log('[chatStore] updateReasoningBlock: Creating new block in existing message', { messageId, blockId, contentLength: content.length })
            const newBlock: ReasoningBlock = {
              id: blockId,
              content,
              isStreaming: true,
              timestamp: new Date().toISOString(),
            }
            updatedBlocks = [...message.reasoningBlocks, newBlock]
          }
          
          console.log('[chatStore] updateReasoningBlock: Final state', { messageId, blocksCount: updatedBlocks.length, totalContentLength: updatedBlocks.reduce((sum, b) => sum + (b.content?.length || 0), 0) })
          
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
          const existing = state.assistantMessages[messageId]// CRITICAL FIX: Don't create assistant message with empty block
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
                isComplete: false,
              }
              return {
                assistantMessages: {
                  ...state.assistantMessages,
                  [messageId]: newMessage,
                },
              }
            } else {
              // No content yet, don't create message - wait for next update
              console.log('[chatStore] updateAnswerBlock: No content, not creating message yet', { messageId, blockId, contentLength: content?.length })
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
      
      setWorkflowPlan: (plan: string, steps: string[], confirmationId: string | null) => {set((state) => {
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
        })},
      
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
          }const newSteps = { ...workflow.steps }
          newSteps[stepNumber] = {
            stepNumber,
            title,
            status: 'in_progress',
            thinking: '',
            response: '',
          }
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
      
      setStepFilePreview: (stepNumber: number, filePreview: FilePreviewData) =>
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
                    filePreview,
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
      
      updateWorkflowFinalResult: (workflowId: string, content: string) =>
        set((state) => {
          const workflow = state.workflows[workflowId]
          if (!workflow) return state
          
          return {
            workflows: {
              ...state.workflows,
              [workflowId]: {
                ...workflow,
                finalResult: content,
              },
            },
          }
        }),
      
      clearWorkflow: () =>
        set({
          workflows: {},
          activeWorkflowId: null,
        }),
      
      // Action message methods
      addAction: (workflowId: string, action: ActionMessageData) =>
        set((state) => {
          const existingActions = state.actionMessages[workflowId] || []
          return {
            actionMessages: {
              ...state.actionMessages,
              [workflowId]: [...existingActions, action],
            },
          }
        }),
      
      updateAction: (workflowId: string, actionId: string, updates: Partial<ActionMessageData>) =>
        set((state) => {
          const existingActions = state.actionMessages[workflowId] || []
          const updatedActions = existingActions.map(action =>
            action.id === actionId ? { ...action, ...updates } : action
          )
          return {
            actionMessages: {
              ...state.actionMessages,
              [workflowId]: updatedActions,
            },
          }
        }),
      
      clearActions: (workflowId: string) =>
        set((state) => {
          const newActionMessages = { ...state.actionMessages }
          delete newActionMessages[workflowId]
          return {
            actionMessages: newActionMessages,
          }
        }),
      
      // Question message methods
      addQuestion: (workflowId: string, question: QuestionMessageData) =>
        set((state) => {
          const existingQuestions = state.questionMessages[workflowId] || []
          return {
            questionMessages: {
              ...state.questionMessages,
              [workflowId]: [...existingQuestions, question],
            },
          }
        }),
      
      updateQuestionAnswer: (workflowId: string, questionId: string, answers: Record<string, string | string[]>) =>
        set((state) => {
          const existingQuestions = state.questionMessages[workflowId] || []
          const updatedQuestions = existingQuestions.map(question => {
            if (question.id === questionId) {
              const updatedItems = question.items.map(item => {
                const answerValue = answers[item.id]
                if (answerValue !== undefined) {
                  return {
                    ...item,
                    value: item.type === 'checkbox' 
                      ? (Array.isArray(answerValue) ? answerValue : [answerValue as string])
                      : answerValue as string,
                  }
                }
                return item
              })
              return {
                ...question,
                items: updatedItems,
                isAnswered: true,
              }
            }
            return question
          })
          return {
            questionMessages: {
              ...state.questionMessages,
              [workflowId]: updatedQuestions,
            },
          }
        }),
      
      clearQuestions: (workflowId: string) =>
        set((state) => {
          const newQuestionMessages = { ...state.questionMessages }
          delete newQuestionMessages[workflowId]
          return {
            questionMessages: newQuestionMessages,
          }
        }),
      
      // Result summary methods
      setResultSummary: (workflowId: string, summary: ResultSummary) =>
        set((state) => ({
          resultSummaries: {
            ...state.resultSummaries,
            [workflowId]: summary,
          },
        })),
      
      updateResultSummary: (workflowId: string, updates: Partial<ResultSummary>) =>
        set((state) => {
          const existingSummary = state.resultSummaries[workflowId]
          return {
            resultSummaries: {
              ...state.resultSummaries,
              [workflowId]: existingSummary
                ? { ...existingSummary, ...updates }
                : {
                    completedTasks: [],
                    failedTasks: [],
                    alternativesUsed: [],
                    ...updates,
                  },
            },
          }
        }),
      
      clearResultSummary: (workflowId: string) =>
        set((state) => {
          const newResultSummaries = { ...state.resultSummaries }
          delete newResultSummaries[workflowId]
          return {
            resultSummaries: newResultSummaries,
          }
        }),
      
      // Current action methods
      setCurrentAction: (action) => {
        set({
          currentAction: action,
        })
      },
      
      clearCurrentAction: () => {
        set({
          currentAction: null,
        })
      },
      
      // Thinking block methods
      startThinking: (thinkingId: string) =>
        set((state) => {
          // По умолчанию не закреплён (проверка будет в компоненте при необходимости)
          // НЕ устанавливаем activeThinkingId сразу - это будет сделано через таймер через 2 секунды
          return {
            thinkingBlocks: {
              ...state.thinkingBlocks,
              [thinkingId]: {
                id: thinkingId,
                status: 'started',
                content: '',
                elapsedSeconds: 0,
                startedAt: Date.now(),
                isCollapsed: false, // Начинаем развёрнутым, auto-collapse при завершении
                isPinned: false, // Будет синхронизировано с settingsStore при необходимости
                stepHistory: [],
              },
            },
            // НЕ устанавливаем activeThinkingId здесь - только через setActiveThinking после задержки
          }
        }),
      
      appendThinkingChunk: (thinkingId: string, chunk: string, elapsedSeconds: number, stepType?: 'analyzing' | 'searching' | 'executing' | 'observing' | 'success' | 'error') =>
        set((state) => {
          const existingBlock = state.thinkingBlocks[thinkingId]
          if (!existingBlock) {
            // Если блока нет, создаём его (fallback - не должно происходить, если startThinking был вызван)
            // НЕ устанавливаем activeThinkingId - только через таймер
            const newBlock: ThinkingBlock = {
              id: thinkingId,
              status: 'streaming',
              content: chunk,
              elapsedSeconds,
              startedAt: Date.now(),
              isCollapsed: false,
              isPinned: false,
              stepHistory: stepType ? [{ type: stepType, text: chunk, timestamp: Date.now() }] : [],
            }
            return {
              thinkingBlocks: {
                ...state.thinkingBlocks,
                [thinkingId]: newBlock,
              },
              // НЕ устанавливаем activeThinkingId здесь - только через setActiveThinking после задержки
            }
          }
          
          return {
            thinkingBlocks: {
              ...state.thinkingBlocks,
              [thinkingId]: {
                ...existingBlock,
                status: 'streaming',
                content: existingBlock.content + chunk,
                elapsedSeconds,
                stepHistory: stepType
                  ? [...existingBlock.stepHistory, { type: stepType, text: chunk, timestamp: Date.now() }]
                  : existingBlock.stepHistory,
              },
            },
          }
        }),
      
      completeThinking: (thinkingId: string, autoCollapse: boolean) =>
        set((state) => {
          const existingBlock = state.thinkingBlocks[thinkingId]
          if (!existingBlock) return state
          
          // Auto-collapse если не закреплён
          const shouldCollapse = autoCollapse && !existingBlock.isPinned
          
          const newActiveThinkingId = state.activeThinkingId === thinkingId ? null : state.activeThinkingId
          return {
            thinkingBlocks: {
              ...state.thinkingBlocks,
              [thinkingId]: {
                ...existingBlock,
                status: 'completed',
                completedAt: Date.now(),
                isCollapsed: shouldCollapse ? true : existingBlock.isCollapsed,
              },
            },
            activeThinkingId: newActiveThinkingId,
          }
        }),
      
      toggleThinkingCollapse: (thinkingId: string) =>
        set((state) => {
          const existingBlock = state.thinkingBlocks[thinkingId]
          if (!existingBlock) return state
          
          return {
            thinkingBlocks: {
              ...state.thinkingBlocks,
              [thinkingId]: {
                ...existingBlock,
                isCollapsed: !existingBlock.isCollapsed,
              },
            },
          }
        }),
      
      toggleThinkingPin: (thinkingId: string) =>
        set((state) => {
          const existingBlock = state.thinkingBlocks[thinkingId]
          if (!existingBlock) return state
          
          const newPinnedState = !existingBlock.isPinned
          
          return {
            thinkingBlocks: {
              ...state.thinkingBlocks,
              [thinkingId]: {
                ...existingBlock,
                isPinned: newPinnedState,
                // Если закрепляем, разворачиваем
                isCollapsed: newPinnedState ? false : existingBlock.isCollapsed,
              },
            },
          }
        }),
      
      setActiveThinking: (thinkingId: string | null) => {
        set({
          activeThinkingId: thinkingId,
        })
      },
      
      // Intent block methods (Cursor-style)
      startIntent: (workflowId: string, intentId: string, intentText: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const newIntent: IntentBlock = {
            id: intentId,
            intent: intentText,
            status: 'started',
            phase: 'planning',  // Начинаем с фазы планирования
            details: [],
            operations: {},
            isCollapsed: false,
            planningCollapsed: false,
            executingCollapsed: false,
            progressPercent: 0,
            elapsedSec: 0,
            estimatedSec: 10, // default estimate
            startedAt: Date.now(),
          }
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: [...existingIntents, newIntent],
            },
            activeIntentId: intentId,
          }
        }),
      
      addIntentDetail: (workflowId: string, intentId: string, detail: IntentDetail) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                status: 'streaming' as const,
                details: [...intent.details, detail],
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      clearIntentThinking: (workflowId: string, intentId: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                thinkingText: '', // Clear thinking text for new iteration
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),

      appendIntentThinking: (workflowId: string, intentId: string, text: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                status: 'streaming' as const,
                thinkingText: (intent.thinkingText || '') + text,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      setIntentPhase: (workflowId: string, intentId: string, phase: IntentPhase) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                phase,
                // Автосворачиваем planning при переходе в executing
                planningCollapsed: phase === 'executing' || phase === 'completed' ? true : intent.planningCollapsed,
                // Автосворачиваем executing при завершении
                executingCollapsed: phase === 'completed' ? true : intent.executingCollapsed,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      setIntentProgress: (workflowId: string, intentId: string, percent: number, elapsed: number, estimated: number) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                progressPercent: percent,
                elapsedSec: elapsed,
                estimatedSec: estimated,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      toggleIntentPhase: (workflowId: string, intentId: string, phase: 'planning' | 'executing') =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                planningCollapsed: phase === 'planning' ? !intent.planningCollapsed : intent.planningCollapsed,
                executingCollapsed: phase === 'executing' ? !intent.executingCollapsed : intent.executingCollapsed,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      completeIntent: (workflowId: string, intentId: string, autoCollapse: boolean, summary?: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                status: 'completed' as const,
                phase: 'completed' as IntentPhase,
                completedAt: Date.now(),
                isCollapsed: autoCollapse,
                planningCollapsed: true,
                executingCollapsed: true,
                summary: summary || intent.summary,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
            activeIntentId: state.activeIntentId === intentId ? null : state.activeIntentId,
          }
        }),
      
      toggleIntentCollapse: (workflowId: string, intentId: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                isCollapsed: !intent.isCollapsed,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      collapseIntent: (workflowId: string, intentId: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              return {
                ...intent,
                isCollapsed: true,
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      collapseAllIntents: (workflowId: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => ({
            ...intent,
            isCollapsed: true,
            status: 'completed' as const,  // Also mark as completed to stop animations
            completedAt: intent.completedAt || Date.now(),
          }))
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      clearIntents: (workflowId: string) =>
        set((state) => {
          const newIntentBlocks = { ...state.intentBlocks }
          delete newIntentBlocks[workflowId]
          return {
            intentBlocks: newIntentBlocks,
          }
        }),
      
      setActiveIntent: (intentId: string | null) =>
        set({
          activeIntentId: intentId,
        }),
      
      // Operation methods (новые операции со стримингом)
      startOperation: (
        workflowId: string,
        operationId: string,
        intentId: string,
        title: string,
        streamingTitle: string,
        operationType: OperationType,
        fileId?: string,
        fileUrl?: string,
        fileType?: FileType
      ) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId) {
              const newOperation: Operation = {
                id: operationId,
                intentId: intentId,
                title: title,
                streamingTitle: streamingTitle,
                operationType: operationType,
                status: 'pending',
                data: [],
                isCollapsed: false,
                fileId: fileId,
                fileUrl: fileUrl,
                fileType: fileType,
              }
              return {
                ...intent,
                operations: {
                  ...intent.operations,
                  [operationId]: newOperation,
                },
                details: [], // Очищаем старые details при создании операции, чтобы избежать дублирования
                phase: 'executing', // Переключаем на фазу выполнения
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      addOperationData: (workflowId: string, intentId: string, operationId: string, data: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId && intent.operations[operationId]) {
              const operation = intent.operations[operationId]
              return {
                ...intent,
                operations: {
                  ...intent.operations,
                  [operationId]: {
                    ...operation,
                    status: 'streaming',
                    data: [...operation.data, data],
                  },
                },
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      completeOperation: (workflowId: string, intentId: string, operationId: string, summary: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId && intent.operations[operationId]) {
              const operation = intent.operations[operationId]
              return {
                ...intent,
                operations: {
                  ...intent.operations,
                  [operationId]: {
                    ...operation,
                    status: 'completed',
                    summary: summary,
                  },
                },
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      toggleOperationCollapse: (workflowId: string, intentId: string, operationId: string) =>
        set((state) => {
          const existingIntents = state.intentBlocks[workflowId] || []
          const updatedIntents = existingIntents.map(intent => {
            if (intent.id === intentId && intent.operations[operationId]) {
              const operation = intent.operations[operationId]
              return {
                ...intent,
                operations: {
                  ...intent.operations,
                  [operationId]: {
                    ...operation,
                    isCollapsed: !operation.isCollapsed,
                  },
                },
              }
            }
            return intent
          })
          return {
            intentBlocks: {
              ...state.intentBlocks,
              [workflowId]: updatedIntents,
            },
          }
        }),
      
      setUserAssistanceRequest: (request) =>
        set({
          userAssistanceRequest: request,
        }),
      
      clearUserAssistanceRequest: () =>
        set({
          userAssistanceRequest: null,
        }),
    }),
    {
      name: 'chat-storage',
      version: 6, // Increment version for new action/question/result message types
      migrate: (persistedState: any, version: number) => {
        if (version < 6) {
          return {
            messages: [],
            assistantMessages: {},
            currentSession: null,
            isConnected: false,
            isAgentTyping: false,
            streamingMessages: {},
            reasoningSteps: [],
            reasoningStartTime: null,
            actionMessages: {},
            questionMessages: {},
            resultSummaries: {},
            currentAction: null,
          }
        }
        return persistedState
      },
      partialize: (state) => ({
        // Don't persist messages - always start with empty chat
        currentSession: state.currentSession,
        // Don't persist workflows - always start with clean state
        // Don't persist assistantMessages or streamingMessages - they're temporary
        // Don't persist actionMessages, questionMessages, resultSummaries - they're temporary
      }),
    }
  )
)
