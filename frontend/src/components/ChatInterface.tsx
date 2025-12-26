import React, { useState, useEffect, useRef } from 'react'
import { Send, Loader2, Sparkles, Plus, Paperclip, Zap, ChevronDown, Brain } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'
import { useModelStore } from '../store/modelStore'
import { wsClient } from '../services/websocket'
import { sendMessage, createSession, updateSettings, setSessionModel } from '../services/api'
import { MessageBubble } from './MessageBubble'
import { ThinkingBlock } from './ThinkingBlock'
import { Header } from './Header'

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [thinkingDuration, setThinkingDuration] = useState(0)
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false)
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [lastUserQuery, setLastUserQuery] = useState<string | null>(null) // Сохраняем последний запрос пользователя
  const [shouldScrollToNew, setShouldScrollToNew] = useState(false) // Флаг для скролла к новому сообщению
  const currentInteractionRef = useRef<HTMLDivElement>(null) // Реф для начала текущего взаимодействия
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const thinkingIntervalRef = useRef<number | null>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const modeDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true) // Флаг для автоскролла вниз
  const isUserScrollingRef = useRef(false) // Флаг, что пользователь скроллит вручную
  
  const {
    currentSession,
    isAgentTyping,
    reasoningSteps,
    reasoningStartTime,
    streamingMessages,
    setCurrentSession,
    startNewSession,
    addMessage,
    getDisplayMessages,
    setAgentTyping,
    getReasoningDuration,
    clearReasoningSteps,
  } = useChatStore()
  
  const { executionMode, setExecutionMode } = useSettingsStore()
  const { models, selectedModel, setSelectedModel, fetchModels, isLoading: isLoadingModels, error: modelsError } = useModelStore()
  
  const messages = getDisplayMessages()
  
  // Находим индекс последнего сообщения пользователя в общем массиве
  const lastUserIndexInMessages = messages.map(m => m.role).lastIndexOf('user');

  // Показываем блок ризонинга, если агент что-то делает (печатает или есть шаги), 
  // но только до момента появления основного текста ответа на ТЕКУЩИЙ запрос.
  const isAssistantThinking = isAgentTyping || reasoningSteps.length > 0
  
  // Проверяем, есть ли ответ ассистента после последнего вопроса (включая streaming)
  const assistantResponseToLastUser = lastUserIndexInMessages !== -1 
    ? messages.slice(lastUserIndexInMessages + 1).find(m => m.role === 'assistant')
    : null
  
  // Проверяем наличие streaming сообщений ассистента С НЕПУСТЫМ контентом
  const streamingAssistantMessages = Object.values(streamingMessages).filter(m => m.role === 'assistant')
  const hasStreamingAssistantWithContent = streamingAssistantMessages.some(m => m.content && m.content.trim().length > 0)
  
  // Считаем, что ассистент начал отвечать ТОЛЬКО если есть реальный текст:
  // 1. Есть сообщение ассистента после последнего вопроса с непустым контентом
  // 2. ИЛИ есть streaming сообщение ассистента с непустым контентом
  const hasAssistantStarted = 
    (assistantResponseToLastUser && assistantResponseToLastUser.content.trim().length > 0) || 
    hasStreamingAssistantWithContent
  
  const showThinking = isAssistantThinking && !hasAssistantStarted

  // Get common message references
  const lastUserMessage = messages.filter(m => m.role === 'user').slice(-1)[0]
  const lastAssistantMessage = messages.filter(m => m.role === 'assistant').slice(-1)[0]
  const hasStreamingAnswer = Object.values(streamingMessages).some(m => m.role === 'assistant')

  // Update thinking duration every second when reasoning is active
  useEffect(() => {
    if (reasoningStartTime || (isAgentTyping && reasoningSteps.length > 0)) {
      const updateDuration = () => {
        const duration = getReasoningDuration()
        setThinkingDuration(duration)
      }
      
      updateDuration()
      thinkingIntervalRef.current = window.setInterval(updateDuration, 1000)
      
      return () => {
        if (thinkingIntervalRef.current) {
          window.clearInterval(thinkingIntervalRef.current)
        }
      }
    } else {
      setThinkingDuration(0)
      if (thinkingIntervalRef.current) {
        window.clearInterval(thinkingIntervalRef.current)
      }
    }
  }, [reasoningStartTime, isAgentTyping, reasoningSteps.length, getReasoningDuration])

  // Обработчик скролла больше не нужен - в Perplexity-style нет автоскролла

  // Скролл к последнему сообщению пользователя (Perplexity style) - КРИТИЧНО для правильного поведения
  useEffect(() => {
    if (shouldScrollToNew && currentInteractionRef.current && messagesContainerRef.current) {
      console.log('[ChatInterface] Attempting to scroll to new user message')
      
      // Используем requestAnimationFrame для гарантии, что браузер отрендерил изменения
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (currentInteractionRef.current && messagesContainerRef.current) {
            console.log('[ChatInterface] Scrolling to new message')
            
            // Прокручиваем контейнер так, чтобы элемент был в самом верху
            const container = messagesContainerRef.current
            const element = currentInteractionRef.current
            const offsetTop = element.offsetTop - 52 // 52px = высота Header
            
            container.scrollTo({
              top: offsetTop,
              behavior: 'smooth'
            })
            
            setShouldScrollToNew(false)
            
            // КРИТИЧНО: Отключаем автоскролл вниз (как в Perplexity)
            // Страница должна оставаться на месте во время генерации ответа
            shouldAutoScrollRef.current = false
            isUserScrollingRef.current = true
            
            console.log('[ChatInterface] Auto-scroll disabled after scrolling to question')
          }
        })
      })
    }
  }, [shouldScrollToNew, messages.length])

  // УБИРАЕМ автоскролл вниз - в Perplexity-style страница не скроллится во время генерации
  // Контент просто заполняет страницу сверху вниз, но страница остается на месте
  // useEffect для автоскролла удален - не нужен для Perplexity-style поведения

  useEffect(() => {
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px'
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200)
      textareaRef.current.style.height = `${newHeight}px`
    }
  }, [input])

  // Clear session on first page load (when browser is opened)
  useEffect(() => {
    const isFirstLoad = !sessionStorage.getItem('chat-initialized')
    
    if (isFirstLoad) {
      // Mark as initialized for this browser session
      sessionStorage.setItem('chat-initialized', 'true')
      
      // Clear old session and messages on first load
      console.log('[ChatInterface] First page load - clearing old session')
      startNewSession()
      wsClient.disconnect()
    }
  }, []) // Run only once on mount

  useEffect(() => {
    // Connect WebSocket when session is available
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

    // Сохраняем последний запрос пользователя, чтобы блок оставался видимым
    setLastUserQuery(userMessage)

    // Активируем скролл к новому сообщению пользователя (чтобы вопрос был сверху)
    setShouldScrollToNew(true)

    // Clear previous reasoning steps
    clearReasoningSteps()
    
    // Сразу помечаем, что агент начал работу, чтобы появился блок ризонинга
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
        
        // Use REST API as fallback
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
    // Disconnect WebSocket
    wsClient.disconnect()
    
    // Clear chat and start new session
    startNewSession()
    
    // Reset input and thinking state
    setInput('')
    setThinkingDuration(0)
    setLastUserQuery(null) // Очищаем сохраненный запрос
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
        // Revert selection on error
        const previousModel = models.find(m => m.id !== modelId && m.id === selectedModel) || models[0]
        if (previousModel) {
          setSelectedModel(previousModel.id)
        }
      }
    }
  }

  // Generate dialog title from first user message
  const getDialogTitle = () => {
    const firstUserMessage = messages.find(m => m.role === 'user')
    if (firstUserMessage) {
      const title = firstUserMessage.content.substring(0, 60)
      return title.length < firstUserMessage.content.length ? title + '...' : title
    }
    return 'New Chat'
  }

  // Format reasoning steps for display
  const getReasoningText = () => {
    const text = reasoningSteps.map(step => {
      let displayContent = step.content
      try {
        const parsed = JSON.parse(step.content)
        if (parsed && typeof parsed === 'object' && parsed.message) {
          displayContent = parsed.message
        }
      } catch {
        // Not JSON, use as is
      }
      return displayContent
    }).join(' ')
    
    console.log('[ChatInterface] Formatting reasoning text, steps count:', reasoningSteps.length, 'text length:', text.length)
    return text
  }

  // Debug logging
  console.log('[ChatInterface] State:', {
    messagesCount: messages.length,
    messages: messages.map(m => ({ role: m.role, contentLength: m.content?.length })),
    streamingMessagesCount: Object.keys(streamingMessages).length,
    streamingMessages: Object.entries(streamingMessages).map(([id, m]) => ({ id, role: m.role, contentLength: m.content?.length })),
    lastUserIndexInMessages,
    assistantResponseToLastUser: assistantResponseToLastUser?.content?.substring(0, 30),
    hasStreamingAssistantWithContent,
    hasAssistantStarted,
    showThinking,
    reasoningStepsCount: reasoningSteps.length,
    isAgentTyping,
  })

  return (
    <div className="chat-container">
      {/* Header - Settings (Настройки) */}
      <Header />

      {/* Messages Container - scrollable */}
      <div className="messages-container" ref={messagesContainerRef}>
        {/* Render all messages in history */}
        {messages.map((message, index) => {
          const isLastUserMessage = index === lastUserIndexInMessages;
          
          if (message.role === 'user') {
            return (
              <div 
                key={index} 
                ref={isLastUserMessage ? currentInteractionRef : null}
                className="user-query-flow-block"
              >
                <span className="user-query-text">{message.content}</span>
              </div>
            )
          }
          
          if (message.role === 'assistant') {
            console.log('[ChatInterface] Rendering assistant message, index:', index, 'content length:', message.content?.length)
            return (
              <div key={index} className="assistant-message-wrapper">
                <MessageBubble message={message} />
              </div>
            )
          }
          
          return null
        })}

        {/* Thinking Block - показываем после последнего сообщения пользователя, если ассистент думает */}
        {showThinking && (
          <ThinkingBlock 
            thinking={getReasoningText() || 'Анализирую запрос...'}
            duration={thinkingDuration}
          />
        )}

        {/* Welcome screen - компактный (Perplexity style) */}
        {messages.length === 0 && (
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

        {/* Typing Indicator - показываем только если нет ответа и идет обработка */}
        {(isAssistantThinking && !hasAssistantStarted && messages.length > 0) && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <div className="typing-dot" style={{ animationDelay: '0s' }} />
              <div className="typing-dot" style={{ animationDelay: '0.2s' }} />
              <div className="typing-dot" style={{ animationDelay: '0.4s' }} />
            </div>
          </div>
        )}
        
        {/* Spacer для возможности скролла любого сообщения к верху (как в Perplexity) */}
        <div className="scroll-spacer" />
      </div>

      {/* Input Area - fixed bottom */}
      <div className="input-area">
        <div className="input-fade"></div>
        
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="input-form">
          <div className="input-wrapper">
            {/* Left Side: Mode Selector + Model Selector + Icons */}
            <div className="input-left-section">
              {/* Execution Mode Selector - Dropdown (как в Cursor) */}
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
              
              {/* Model Selector - Dropdown (как в Cursor) */}
              <div className="relative" ref={modelDropdownRef}>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    console.log('[ChatInterface] Model selector clicked, current state:', { isModelDropdownOpen, modelsCount: models.length })
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
