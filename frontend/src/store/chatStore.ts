import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface ReasoningStep {
  type: 'thought' | 'tool_call' | 'tool_result' | 'decision'
  content: string
  timestamp: string
  data?: any
}

interface ChatState {
  messages: Message[]
  streamingMessages: Record<string, Message> // message_id -> Message
  currentSession: string | null
  isConnected: boolean
  isAgentTyping: boolean
  reasoningSteps: ReasoningStep[]
  reasoningStartTime: number | null // Timestamp when reasoning started
  addMessage: (message: Message) => void
  addReasoningStep: (step: ReasoningStep) => void
  clearChat: () => void
  startNewSession: () => void
  setCurrentSession: (sessionId: string) => void
  setConnectionStatus: (connected: boolean) => void
  setAgentTyping: (typing: boolean) => void
  clearReasoningSteps: () => void
  setReasoningStartTime: (time: number | null) => void
  getReasoningDuration: () => number // Returns duration in seconds
  startStreamingMessage: (messageId: string, message: Message) => void
  updateStreamingMessage: (messageId: string, content: string) => void
  completeStreamingMessage: (messageId: string, content: string) => void
  getDisplayMessages: () => Message[] // Returns messages + streaming messages
}

// Storage version - increment this to clear old cache
const STORAGE_VERSION = '4.0.0'

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      streamingMessages: {},
      currentSession: null,
      isConnected: false,
      isAgentTyping: false,
      reasoningSteps: [],
      reasoningStartTime: null,
      
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
        })),
      
      addReasoningStep: (step) =>
        set((state) => {
          console.log('[ChatStore] Adding reasoning step:', step.type, 'content length:', step.content?.length, 'current steps:', state.reasoningSteps.length)
          
          // Start timing if this is the first reasoning step
          const startTime = state.reasoningStartTime || Date.now()
          
          // Для шагов типа 'thought' - обновляем последний шаг, если он тоже 'thought'
          // Это предотвращает дублирование incremental updates
          if (step.type === 'thought' && state.reasoningSteps.length > 0) {
            const lastStep = state.reasoningSteps[state.reasoningSteps.length - 1]
            if (lastStep.type === 'thought') {
              console.log('[ChatStore] Updating last thought step, old length:', lastStep.content?.length, 'new length:', step.content?.length)
              // Обновляем последний шаг мысли
              const updatedSteps = [...state.reasoningSteps]
              updatedSteps[updatedSteps.length - 1] = {
                ...lastStep,
                content: step.content, // Заменяем на новый контент (он уже накопленный с бэкенда)
                timestamp: step.timestamp,
                data: step.data,
              }
              return {
                reasoningSteps: updatedSteps,
                reasoningStartTime: startTime,
              }
            }
          }
          
          // Для других типов (tool_call, tool_result) или если это первый thought - добавляем новый шаг
          console.log('[ChatStore] Adding new reasoning step')
          return {
            reasoningSteps: [...state.reasoningSteps, step],
            reasoningStartTime: startTime,
          }
        }),
      
      clearChat: () =>
        set({
          messages: [],
          reasoningSteps: [],
          streamingMessages: {},
          reasoningStartTime: null,
        }),
      
      startNewSession: () =>
        set({
          messages: [],
          reasoningSteps: [],
          streamingMessages: {},
          currentSession: null,
          isAgentTyping: false,
          reasoningStartTime: null,
        }),
      
      setCurrentSession: (sessionId) =>
        set({ currentSession: sessionId }),
      
      setConnectionStatus: (connected) =>
        set({ isConnected: connected }),
      
      setAgentTyping: (typing) => {
        set((state) => {
          // Start reasoning timer when agent starts typing
          if (typing && !state.reasoningStartTime) {
            return { isAgentTyping: typing, reasoningStartTime: Date.now() }
          }
          // Clear timer when agent stops typing
          if (!typing && state.reasoningStartTime) {
            return { isAgentTyping: typing, reasoningStartTime: null }
          }
          return { isAgentTyping: typing }
        })
      },
      
      clearReasoningSteps: () =>
        set({ reasoningSteps: [], reasoningStartTime: null }),
      
      setReasoningStartTime: (time) =>
        set({ reasoningStartTime: time }),
      
      getReasoningDuration: () => {
        const state = get()
        if (!state.reasoningStartTime) return 0
        return Math.floor((Date.now() - state.reasoningStartTime) / 1000)
      },
      
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
            // Move from streaming to regular messages
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
    }),
    {
      name: 'chat-storage',
      version: 4, // Increment to clear old cache
      migrate: (persistedState: any, version: number) => {
        // Clear old cache if version mismatch
        if (version < 4) {
          return {
            messages: [],
            currentSession: null,
            isConnected: false,
            isAgentTyping: false,
            reasoningSteps: [],
            streamingMessages: {},
          }
        }
        return persistedState
      },
      partialize: (state) => ({
        messages: state.messages,
        currentSession: state.currentSession,
        // Don't persist streamingMessages - they're temporary
      }),
    }
  )
)

