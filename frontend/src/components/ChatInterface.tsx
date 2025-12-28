import React, { useState, useEffect, useRef } from 'react'
import { Send, Loader2, Sparkles, Plus, Paperclip, ChevronDown, Brain } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'
import { useModelStore } from '../store/modelStore'
import { wsClient } from '../services/websocket'
import { sendMessage, createSession, updateSettings, setSessionModel } from '../services/api'
import { ChatMessage } from './ChatMessage'
import { Header } from './Header'

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false)
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [shouldScrollToNew, setShouldScrollToNew] = useState(false)
  const currentInteractionRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const modeDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  
  const {
    currentSession,
    isAgentTyping,
    messages,
    assistantMessages,
    setCurrentSession,
    startNewSession,
    addMessage,
    setAgentTyping,
  } = useChatStore()
  
  const { executionMode, setExecutionMode } = useSettingsStore()
  const { models, selectedModel, setSelectedModel, fetchModels, isLoading: isLoadingModels, error: modelsError } = useModelStore()
  
  // Find last user message index
  const lastUserIndexInMessages = messages.map(m => m.role).lastIndexOf('user')
  
  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px'
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200)
      textareaRef.current.style.height = `${newHeight}px`
    }
  }, [input])
  
  // Clear session on first page load
  useEffect(() => {
    const isFirstLoad = !sessionStorage.getItem('chat-initialized')
    
    if (isFirstLoad) {
      sessionStorage.setItem('chat-initialized', 'true')
      console.log('[ChatInterface] First page load - clearing old session')
      startNewSession()
      wsClient.disconnect()
    }
  }, [])
  
  // Connect WebSocket when session is available
  useEffect(() => {
    if (currentSession) {
      wsClient.connect(currentSession)
    }
    
    return () => {
      wsClient.disconnect()
    }
  }, [currentSession])
  
  // Timeout to reset agent typing state if it gets stuck
  useEffect(() => {
    if (isAgentTyping) {
      const timeout = setTimeout(() => {
        console.warn('[ChatInterface] Agent typing timeout - resetting state')
        setAgentTyping(false)
      }, 60000) // 60 seconds timeout
      
      return () => clearTimeout(timeout)
    }
  }, [isAgentTyping, setAgentTyping])
  
  // Fetch models on mount
  useEffect(() => {
    console.log('[ChatInterface] Fetching models on mount')
    fetchModels().catch((err) => {
      console.error('[ChatInterface] Error fetching models:', err)
    })
  }, [])
  
  // Close mode and model dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(event.target as Node)) {
        setIsModeDropdownOpen(false)
      }
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target as Node)) {
        setIsModelDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  
  // Scroll to new user message
  useEffect(() => {
    if (shouldScrollToNew && currentInteractionRef.current && messagesContainerRef.current) {
      console.log('[ChatInterface] Attempting to scroll to new user message')
      
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (currentInteractionRef.current && messagesContainerRef.current) {
            console.log('[ChatInterface] Scrolling to new message')
            
            const container = messagesContainerRef.current
            const element = currentInteractionRef.current
            const offsetTop = element.offsetTop - 52
            
            container.scrollTo({
              top: offsetTop,
              behavior: 'smooth'
            })
            
            setShouldScrollToNew(false)
          }
        })
      })
    }
  }, [shouldScrollToNew, messages.length])
  
  const handleSend = async () => {
    if (!input.trim() || isSending) return

    const userMessage = input.trim()
    console.log('[ChatInterface] Sending message:', userMessage)
    console.log('[ChatInterface] Current session:', currentSession)
    console.log('[ChatInterface] WebSocket connected:', wsClient.isConnected())
    
    setInput('')
    setIsSending(true)

    // Add user message immediately to show it in UI
    addMessage({
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
    })

    // Activate scroll to new message
    setShouldScrollToNew(true)
    
    // Mark agent as typing
    setAgentTyping(true)

    try {
      // Try WebSocket first if session exists and connection is open
      if (currentSession && wsClient.isConnected()) {
        console.log('[ChatInterface] Using WebSocket to send message')
        const sent = wsClient.sendMessage(userMessage)
        if (!sent) {
          console.warn('[ChatInterface] WebSocket send failed, falling back to REST API')
          throw new Error('WebSocket send failed')
        }
      } else if (currentSession) {
        // Session exists but WebSocket not connected, try to reconnect and use REST API as fallback
        console.warn('[ChatInterface] WebSocket not connected, using REST API')
        wsClient.connect(currentSession)
        
        console.log('[ChatInterface] Sending via REST API (fallback)')
        await sendMessage({
          message: userMessage,
          session_id: currentSession,
          execution_mode: 'instant',
        })
      } else {
        // Create new session FIRST, then connect WebSocket, then send message
        console.log('[ChatInterface] Creating new session first')
        const sessionData = await createSession('instant', selectedModel || undefined)
        const newSessionId = sessionData.session_id
        console.log('[ChatInterface] New session created:', newSessionId)
        setCurrentSession(newSessionId)
        
        // Connect WebSocket BEFORE sending message
        console.log('[ChatInterface] Connecting WebSocket to new session')
        wsClient.connect(newSessionId)
        
        // Wait for WebSocket to connect (backend waits up to 5 seconds)
        let connected = false
        for (let i = 0; i < 60; i++) {
          await new Promise(resolve => setTimeout(resolve, 100))
          if (wsClient.isConnected()) {
            connected = true
            console.log('[ChatInterface] WebSocket connected after', i * 100, 'ms')
            break
          }
        }
        
        if (!connected) {
          console.warn('[ChatInterface] WebSocket did not connect within 6 seconds, proceeding anyway')
        }
        
        // Now send message via WebSocket or REST API
        if (wsClient.isConnected()) {
          console.log('[ChatInterface] Sending message via WebSocket')
          const sent = wsClient.sendMessage(userMessage)
          if (!sent) {
            console.warn('[ChatInterface] WebSocket send failed, using REST API')
            await sendMessage({
              message: userMessage,
              session_id: newSessionId,
              execution_mode: 'instant',
            })
          }
        } else {
          console.log('[ChatInterface] WebSocket not connected, using REST API')
          await sendMessage({
            message: userMessage,
            session_id: newSessionId,
            execution_mode: 'instant',
          })
        }
      }
    } catch (error: any) {
      console.error('[ChatInterface] Error sending message:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Неизвестная ошибка'
      addMessage({
        role: 'system',
        content: `Не удалось отправить сообщение: ${errorMessage}. Пожалуйста, попробуйте снова.`,
        timestamp: new Date().toISOString(),
      })
    } finally {
      setIsSending(false)
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px'
      }
    }
  }
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }
  
  const handleNewSession = () => {
    wsClient.disconnect()
    startNewSession()
    setInput('')
  }
  
  const handleExecutionModeChange = async (mode: 'instant' | 'approval') => {
    setExecutionMode(mode)
    if (currentSession) {
      await updateSettings({
        session_id: currentSession,
        execution_mode: mode,
      })
    }
  }
  
  const getModelDisplayName = (modelId: string | null): string => {
    if (!modelId) return 'Model'
    const model = models.find(m => m.id === modelId)
    return model?.name || modelId
  }
  
  const getProviderIcon = (modelId: string | null) => {
    if (!modelId) return <Sparkles className="w-3.5 h-3.5" />
    const model = models.find(m => m.id === modelId)
    if (model?.provider === 'openai') {
      return <Brain className="w-3.5 h-3.5" />
    }
    return <Sparkles className="w-3.5 h-3.5" />
  }
  
  const handleModelSelect = async (modelId: string) => {
    setSelectedModel(modelId)
    setIsModelDropdownOpen(false)
    
    if (currentSession) {
      try {
        await setSessionModel(currentSession, modelId)
      } catch (error) {
        console.error('[ChatInterface] Failed to set session model:', error)
        const previousModel = models.find(m => m.id !== modelId && m.id === selectedModel) || models[0]
        if (previousModel) {
          setSelectedModel(previousModel.id)
        }
      }
    }
  }
  
  return (
    <div className="chat-container">
      {/* Header */}
      <Header />

      {/* Messages Container */}
      <div className="messages-container" ref={messagesContainerRef}>
        {/* Render all messages */}
        {messages.map((message, index) => {
          const isLastUserMessage = index === lastUserIndexInMessages
          
          if (message.role === 'user') {
            return (
              <div 
                key={`user-${index}-${message.timestamp}`}
                ref={isLastUserMessage ? currentInteractionRef : null}
                className="user-query-flow-block"
              >
                <span className="user-query-text">{message.content}</span>
              </div>
            )
          }
          
          if (message.role === 'assistant') {
            // Check if this message has metadata with reasoning blocks
            const hasReasoningMetadata = message.metadata?.reasoningBlocks
            if (hasReasoningMetadata) {
              // This is a completed message with reasoning - render as regular message
              return (
                <div key={`assistant-${index}-${message.timestamp}`} className="assistant-message-wrapper">
                  <div className="w-full">
                    <div className="prose max-w-none 
                      prose-p:text-gray-900 
                      prose-p:leading-6 prose-p:my-3 prose-p:text-[15px]
                      prose-h1:text-gray-900 prose-h1:text-[20px] prose-h1:font-semibold prose-h1:mb-3 prose-h1:mt-6 prose-h1:first:mt-0 prose-h1:leading-tight
                      prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold prose-h2:mb-2 prose-h2:mt-5 prose-h2:leading-tight
                      prose-h3:text-gray-900 prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:leading-tight
                      prose-strong:text-gray-900 prose-strong:font-semibold
                      prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:border prose-code:border-gray-200
                      prose-pre:bg-gray-100 prose-pre:text-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:text-[13px] prose-pre:rounded-lg prose-pre:p-4
                      prose-ul:text-gray-900 prose-ul:my-3
                      prose-li:text-gray-900 prose-li:my-1.5 prose-li:text-[15px]
                      prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-700
                      prose-blockquote:text-gray-600 prose-blockquote:border-l-gray-300 prose-blockquote:pl-4 prose-blockquote:my-3
                      prose-table:w-full prose-table:border-collapse prose-table:my-4
                      prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold
                      prose-td:border prose-td:border-gray-300 prose-td:px-3 prose-td:py-2
                      prose-tr:hover:bg-gray-50">
                      {message.content}
                    </div>
                  </div>
                </div>
              )
            }
          }
          
          if (message.role === 'system') {
            return (
              <div key={`system-${index}-${message.timestamp}`} className="w-full">
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
                  <div className="text-sm text-amber-900">
                    {message.content}
                  </div>
                </div>
              </div>
            )
          }
          
          return null
        })}
        
        {/* Render streaming assistant messages */}
        {Object.values(assistantMessages).map((assistantMsg) => (
          <div key={assistantMsg.id} className="assistant-message-wrapper">
            <ChatMessage message={assistantMsg} />
          </div>
        ))}
        
        {/* Welcome screen */}
        {messages.length === 0 && Object.keys(assistantMessages).length === 0 && (
          <div className="start-dialog-container-compact">
            <div className="start-dialog-content-compact">
              <div className="start-dialog-icon-compact">
                <Sparkles className="w-8 h-8 text-[#00D9FF]" />
              </div>
              <h3 className="start-dialog-title-compact">
                Чем могу помочь?
              </h3>
            </div>
          </div>
        )}
        
        {/* Scroll spacer */}
        <div className="scroll-spacer" />
      </div>

      {/* Input Area */}
      <div className="input-area">
        <div className="input-fade"></div>
        
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="input-form">
          <div className="input-wrapper">
            {/* Left Side: Mode Selector + Model Selector + Icons */}
            <div className="input-left-section">
              {/* Execution Mode Selector */}
              <div className="relative" ref={modeDropdownRef}>
                <button
                  type="button"
                  onClick={() => setIsModeDropdownOpen(!isModeDropdownOpen)}
                  className="mode-selector-dropdown-button"
                  title={executionMode === 'instant' ? 'Мгновенное выполнение' : 'С подтверждением действий'}
                >
                  <span>{executionMode === 'instant' ? 'Агент' : 'План'}</span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isModeDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isModeDropdownOpen && (
                  <div className="mode-selector-dropdown">
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('instant')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'instant' ? 'active' : ''}`}
                    >
                      Агент
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('approval')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'approval' ? 'active' : ''}`}
                    >
                      План
                    </button>
                  </div>
                )}
              </div>
              
              {/* Model Selector */}
              <div className="relative" ref={modelDropdownRef}>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setIsModelDropdownOpen(!isModelDropdownOpen)
                  }}
                  className="model-selector-dropdown-button"
                  title={models.length === 0 ? "Загрузка моделей..." : "Выбрать модель"}
                >
                  <span className="model-icon">{getProviderIcon(selectedModel)}</span>
                  <span>{getModelDisplayName(selectedModel)}</span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isModelDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isModelDropdownOpen && (
                  <div 
                    className="model-selector-dropdown"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {isLoadingModels ? (
                      <div className="model-dropdown-item" style={{ color: 'var(--text-tertiary)', cursor: 'default' }}>
                        Загрузка моделей...
                      </div>
                    ) : modelsError ? (
                      <div className="model-dropdown-item" style={{ color: 'var(--error)', cursor: 'default' }}>
                        Ошибка: {modelsError}
                      </div>
                    ) : models.length === 0 ? (
                      <div className="model-dropdown-item" style={{ color: 'var(--text-tertiary)', cursor: 'default' }}>
                        Нет доступных моделей
                      </div>
                    ) : (
                      models.map((model) => (
                        <button
                          key={model.id}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleModelSelect(model.id)
                          }}
                          className={`model-dropdown-item ${selectedModel === model.id ? 'active' : ''}`}
                        >
                          <span className="model-icon">{getProviderIcon(model.id)}</span>
                          <div className="model-info">
                            <div className="model-name">{model.name}</div>
                            {model.supports_reasoning && (
                              <div className="model-badge">Reasoning</div>
                            )}
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* Action Icons */}
              <div className="input-icons">
                <button
                  type="button"
                  onClick={handleNewSession}
                  className="input-icon-button"
                  title="Новый диалог"
                >
                  <Plus className="w-5 h-5" />
                </button>
                <button
                  type="button"
                  className="input-icon-button"
                  title="Прикрепить файл"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Text Input */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Напишите сообщение..."
              disabled={isSending}
              rows={1}
              className="chat-input"
            />

            {/* Send Button */}
            <button
              type="submit"
              disabled={!input.trim() || isSending}
              className="send-button"
            >
              {isSending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Hint */}
          <p className="input-hint">
            <kbd>Enter</kbd> отправить • <kbd>Shift + Enter</kbd> новая строка
          </p>
        </form>
      </div>
    </div>
  )
}
