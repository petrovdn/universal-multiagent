import React, { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Loader2, Sparkles, Plus, Paperclip, ChevronDown, Brain, Square } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'
import { useModelStore } from '../store/modelStore'
import { useWorkspaceStore } from '../store/workspaceStore'
import { wsClient } from '../services/websocket'
import { sendMessage, createSession, updateSettings, setSessionModel, uploadFile } from '../services/api'
import { ChatMessage } from './ChatMessage'
import { PlanBlock } from './PlanBlock'
import { StepProgress } from './StepProgress'
import { FinalResultBlock } from './FinalResultBlock'
import { UserAssistanceDialog } from './UserAssistanceDialog'
import { CollapsibleBlock } from './CollapsibleBlock'
import { ActionItem } from './ActionItem'
import { QuestionForm } from './QuestionForm'
import { ResultSummary } from './ResultSummary'

interface AttachedFile {
  id: string
  name: string
  type: string
  preview?: string
}

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false)
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [shouldScrollToNew, setShouldScrollToNew] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const currentInteractionRef = useRef<HTMLDivElement>(null)
  const lastUserMessageCountRef = useRef<number>(0)
  const isCollapsingRef = useRef<boolean>(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const modeDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const stickyPlanSectionRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const stickyResultSectionRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const stepsSectionRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const [resultTopPositions, setResultTopPositions] = useState<Record<string, number>>({})
  
  const {
    currentSession,
    isAgentTyping,
    messages,
    assistantMessages,
    setCurrentSession,
    startNewSession,
    addMessage,
    setAgentTyping,
    clearWorkflow,
    userAssistanceRequest,
    workflows,
    activeWorkflowId,
  } = useChatStore()
  
  const { executionMode, setExecutionMode } = useSettingsStore()
  const { models, selectedModel, setSelectedModel, fetchModels, isLoading: isLoadingModels, error: modelsError } = useModelStore()
  const { tabs } = useWorkspaceStore()
  
  // Find last user message index
  const lastUserIndexInMessages = messages.map(m => m.role).lastIndexOf('user')
  
  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '40px'
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
    const userMessages = messages.filter(m => m.role === 'user')
    const currentUserMessageCount = userMessages.length
    
    // Проверяем, появилось ли новое user сообщение
    const hasNewUserMessage = currentUserMessageCount > lastUserMessageCountRef.current
    
    if (!hasNewUserMessage || !currentInteractionRef.current || !messagesContainerRef.current) {
      if (hasNewUserMessage) {
        lastUserMessageCountRef.current = currentUserMessageCount
      }
      return
    }
    
    // Обновляем счетчик
    lastUserMessageCountRef.current = currentUserMessageCount
    
    console.log('[ChatInterface] Attempting to scroll to new user message')
    
    // Функция для выполнения прокрутки с повторными попытками
    const attemptScroll = (attempt: number) => {
      if (!currentInteractionRef.current || !messagesContainerRef.current) {        return
      }
      
      const container = messagesContainerRef.current
      const element = currentInteractionRef.current
      
      // Находим родительский user-interaction-container для правильного расчета позиции
      const interactionContainer = element.closest('.user-interaction-container') as HTMLElement
      
      if (!interactionContainer) {        return
      }
      
      // Используем getBoundingClientRect для получения абсолютной позиции
      const containerRect = container.getBoundingClientRect()
      const elementRect = interactionContainer.getBoundingClientRect()
      
      // Вычисляем позицию прокрутки: позиция элемента относительно контейнера + текущая прокрутка
      const scrollTop = container.scrollTop + (elementRect.top - containerRect.top) - 52 // 52px для header
      
      // Проверяем, что элемент имеет правильную позицию (не 0 или отрицательную)
      if ((elementRect.top - containerRect.top) <= 0 && attempt < 5) {        // Элемент еще не готов, пробуем еще раз
        setTimeout(() => attemptScroll(attempt + 1), 100)
        return
      }
      
      console.log('[ChatInterface] Scrolling to new message')
      
      container.scrollTo({
        top: Math.max(0, scrollTop),
        behavior: 'smooth'
      })
      
      setShouldScrollToNew(false)
    }
    
    // Используем несколько requestAnimationFrame и setTimeout для гарантии, что элемент отрендерился
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setTimeout(() => attemptScroll(0), 50)
      })
    })
  }, [messages.length, shouldScrollToNew])

  // Функция для вычисления позиций всех запросов
  const updateAllPositions = useCallback(() => {
    // Получаем все запросы пользователя в порядке их появления
    const userMessages = messages.filter(m => m.role === 'user')
    
    userMessages.forEach((userMessage, index) => {
      const workflowId = userMessage.timestamp
      
      // Вычисляем сумму высот всех предыдущих запросов
      let cumulativeHeight = 0
      for (let i = 0; i < index; i++) {
        const prevWorkflowId = userMessages[i].timestamp
        const prevQuerySection = document.querySelector(`.user-interaction-container[data-workflow-id="${prevWorkflowId}"] .sticky-query-section.sticky-active`) as HTMLElement
        const prevPlanSection = stickyPlanSectionRefs.current.get(prevWorkflowId)
        const prevStepsSection = stepsSectionRefs.current.get(prevWorkflowId)
        const prevResultSection = stickyResultSectionRefs.current.get(prevWorkflowId)
        
        if (prevQuerySection) {
          const queryHeight = prevQuerySection.offsetHeight
          const planHeight = prevPlanSection ? prevPlanSection.offsetHeight : 0
          // Не учитываем stepsHeight - шаги прокручиваются под планом
          const resultHeight = prevResultSection ? prevResultSection.offsetHeight : 0
          cumulativeHeight += queryHeight + planHeight + resultHeight
        }
      }
      
      // Устанавливаем позицию для текущего запроса
      const querySection = document.querySelector(`.user-interaction-container[data-workflow-id="${workflowId}"] .sticky-query-section.sticky-active`) as HTMLElement
      const planSection = stickyPlanSectionRefs.current.get(workflowId)
      const resultSection = stickyResultSectionRefs.current.get(workflowId)
      
      if (querySection && planSection) {
        // План останавливается после запроса
        // Для sticky positioning, top - это смещение от верха viewport
        // padding-top контейнера уже учтен, не добавляем его повторно
        const planTop = querySection.offsetHeight
        const beforeHeight = planSection.offsetHeight
        planSection.style.top = `${planTop}px`
        const afterHeight = planSection.offsetHeight      }
      
      if (resultSection) {
        const querySection = document.querySelector(`.user-interaction-container[data-workflow-id="${workflowId}"] .sticky-query-section.sticky-active`) as HTMLElement
        const planSection = stickyPlanSectionRefs.current.get(workflowId)
        
        if (querySection && planSection) {
          const queryHeight = querySection.offsetHeight
          const planHeight = planSection.offsetHeight
          // Результат останавливается после плана (без учета высоты шагов)
          // Для sticky positioning, top - это смещение от верха viewport
          // padding-top контейнера уже учтен, не добавляем его повторно
          resultSection.style.top = `${queryHeight + planHeight}px`
        }
      }
    })
  }, [messages])

  // Слушаем события сворачивания блоков
  useEffect(() => {
    const handleCollapsing = () => {
      isCollapsingRef.current = true    }
    
    const handleCollapsed = () => {
      isCollapsingRef.current = false    }
    
    window.addEventListener('collapsibleBlockCollapsing', handleCollapsing)
    window.addEventListener('collapsibleBlockCollapsed', handleCollapsed)
    
    return () => {
      window.removeEventListener('collapsibleBlockCollapsing', handleCollapsing)
      window.removeEventListener('collapsibleBlockCollapsed', handleCollapsed)
    }
  }, [])
  
  // Обновляем позиции всех запросов при изменении размеров
  useEffect(() => {
    // Обновляем при монтировании и изменении размеров
    updateAllPositions()    // Используем ResizeObserver для отслеживания изменений размера всех элементов
    const observers: ResizeObserver[] = []
    
    // Отслеживаем изменения размера всех запросов
    stickyPlanSectionRefs.current.forEach((planSection, workflowId) => {
      const querySection = document.querySelector(`.user-interaction-container[data-workflow-id="${workflowId}"] .sticky-query-section.sticky-active`) as HTMLElement
      if (querySection) {
        const observer = new ResizeObserver(() => {
          updateAllPositions()
        })
        observer.observe(querySection)
        observers.push(observer)
      }
      
      if (planSection) {
        let lastHeight = planSection.offsetHeight
        
        const observer = new ResizeObserver((entries) => {          const currentHeight = planSection.offsetHeight
          
          // Если высота уменьшилась (блоки сворачиваются), НЕ вызываем updateAllPositions
          if (currentHeight < lastHeight) {            lastHeight = currentHeight
            return // НЕ вызываем updateAllPositions при сворачивании
          }
          
          // Обновляем позиции только если высота увеличилась или не изменилась
          updateAllPositions()
          lastHeight = currentHeight
        })
        observer.observe(planSection)
        observers.push(observer)
      }
    })
    
    stepsSectionRefs.current.forEach((stepsSection) => {
      if (stepsSection) {
        const observer = new ResizeObserver(() => {
          updateAllPositions()
        })
        observer.observe(stepsSection)
        observers.push(observer)
      }
    })
    
    stickyResultSectionRefs.current.forEach((resultSection) => {
      if (resultSection) {
        const observer = new ResizeObserver(() => {
          updateAllPositions()
        })
        observer.observe(resultSection)
        observers.push(observer)
      }
    })

    return () => {
      observers.forEach(observer => observer.disconnect())
    }
  }, [messages, workflows, updateAllPositions])

  // Обновляем позиции всех запросов после рендера всех элементов
  useEffect(() => {
    const updatePositions = () => {
      updateAllPositions()
    }

    // Небольшая задержка для того, чтобы все элементы успели отрендериться
    const timeout = setTimeout(updatePositions, 100)
    
    // Также обновляем сразу
    updatePositions()

    return () => clearTimeout(timeout)
  }, [messages, workflows, updateAllPositions])
  
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    
    // Ensure we have a session
    let sessionId: string = currentSession || ''
    if (!sessionId) {
      try {
        const sessionData = await createSession(executionMode, selectedModel || undefined)
        sessionId = sessionData.session_id
        setCurrentSession(sessionId)
        wsClient.connect(sessionId)
      } catch (error) {
        console.error('[ChatInterface] Failed to create session for file upload:', error)
        alert('Не удалось создать сессию для загрузки файла')
        return
      }
    }
    
    // Process each file
    for (const file of Array.from(files)) {
      // Validate file type
      if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
        alert(`Файл "${file.name}" не поддерживается. Поддерживаются только изображения и PDF файлы.`)
        continue
      }
      
      // Check file size (20MB limit)
      if (file.size > 20 * 1024 * 1024) {
        alert(`Файл "${file.name}" слишком большой. Максимальный размер: 20MB`)
        continue
      }
      
      try {
        const fileData = await uploadFile(file, sessionId)
        
        // Create preview for images
        let preview: string | undefined
        if (file.type.startsWith('image/')) {
          preview = URL.createObjectURL(file)
        }
        
        setAttachedFiles(prev => [...prev, {
          id: fileData.file_id,
          name: file.name,
          type: file.type,
          preview
        }])
      } catch (error: any) {
        console.error('[ChatInterface] File upload error:', error)
        const errorMessage = error?.response?.data?.detail || error?.message || 'Неизвестная ошибка'
        alert(`Ошибка загрузки файла "${file.name}": ${errorMessage}`)
      }
    }
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }
  
  const handleRemoveFile = (fileId: string) => {
    setAttachedFiles(prev => {
      const file = prev.find(f => f.id === fileId)
      if (file?.preview) {
        URL.revokeObjectURL(file.preview)
      }
      return prev.filter(f => f.id !== fileId)
    })
  }
  
  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || isSending) return

    const userMessage = input.trim()
    const fileIds = attachedFiles.map(f => f.id)
    
    // Collect open files from workspace tabs (excluding placeholder)
    const openFiles = tabs
      .filter(tab => tab.type !== 'placeholder')
      .map(tab => ({
        type: tab.type,
        title: tab.title,
        url: tab.url,
        spreadsheet_id: tab.data?.spreadsheet_id,
        document_id: tab.data?.document_id,
      }))
    
    console.log('[ChatInterface] Sending message:', userMessage, 'with files:', fileIds, 'open files:', openFiles)
    console.log('[ChatInterface] Current session:', currentSession)
    console.log('[ChatInterface] WebSocket connected:', wsClient.isConnected())
    
    setInput('')
    // Clean up preview URLs
    attachedFiles.forEach(file => {
      if (file.preview) {
        URL.revokeObjectURL(file.preview)
      }
    })
    setAttachedFiles([])
    setIsSending(true)

    // Don't clear workflow - we want to preserve history and only work with the active (last) workflow
    // The workflow will be managed per user message through metadata

    // Add user message immediately to show it in UI
    addMessage({
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
    })

    // Activate scroll to new message    setShouldScrollToNew(true)
    
    // Mark agent as typing
    setAgentTyping(true)

    try {
      // Try WebSocket first if session exists and connection is open
      if (currentSession && wsClient.isConnected()) {
        // Use REST API when files are attached (WebSocket doesn't support files yet)
        if (fileIds.length > 0 || openFiles.length > 0) {
          console.log('[ChatInterface] Using REST API (files attached or open files)')
          await sendMessage({
            message: userMessage,
            session_id: currentSession,
            execution_mode: executionMode,
            file_ids: fileIds.length > 0 ? fileIds : undefined,
            open_files: openFiles.length > 0 ? openFiles : undefined,
          })
        } else {
          console.log('[ChatInterface] Using WebSocket to send message')
          const sent = wsClient.sendMessage(userMessage)
          if (!sent) {
            console.warn('[ChatInterface] WebSocket send failed, falling back to REST API')
            await sendMessage({
              message: userMessage,
              session_id: currentSession,
              execution_mode: executionMode,
            })
          }
        }
      } else if (currentSession) {
        // Session exists but WebSocket not connected, try to reconnect and use REST API as fallback
        console.warn('[ChatInterface] WebSocket not connected, using REST API')
        wsClient.connect(currentSession)
        
        console.log('[ChatInterface] Sending via REST API (fallback)')
        await sendMessage({
          message: userMessage,
          session_id: currentSession,
          execution_mode: executionMode,
          file_ids: fileIds.length > 0 ? fileIds : undefined,
          open_files: openFiles.length > 0 ? openFiles : undefined,
        })
      } else {
        // Create new session FIRST, then connect WebSocket, then send message
        console.log('[ChatInterface] Creating new session first')
        const sessionData = await createSession(executionMode, selectedModel || undefined)
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
        // Note: WebSocket doesn't support file_ids/open_files yet, so we use REST API when files are attached
        if (fileIds.length > 0 || openFiles.length > 0 || !wsClient.isConnected()) {
          console.log('[ChatInterface] Using REST API (files attached, open files, or WebSocket not connected)')
          await sendMessage({
            message: userMessage,
            session_id: newSessionId,
            execution_mode: executionMode,
            file_ids: fileIds.length > 0 ? fileIds : undefined,
            open_files: openFiles.length > 0 ? openFiles : undefined,
          })
        } else {
          console.log('[ChatInterface] Sending message via WebSocket')
          const sent = wsClient.sendMessage(userMessage)
          if (!sent) {
            console.warn('[ChatInterface] WebSocket send failed, using REST API')
            await sendMessage({
              message: userMessage,
              session_id: newSessionId,
              execution_mode: executionMode,
            })
          }
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
        textareaRef.current.style.height = '40px'
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
    // Clean up file previews
    attachedFiles.forEach(file => {
      if (file.preview) {
        URL.revokeObjectURL(file.preview)
      }
    })
    setAttachedFiles([])
  }
  
  const handleStopGeneration = () => {
    console.log('[ChatInterface] Stopping generation')
    wsClient.stopGeneration()
    setIsSending(false)
    setAgentTyping(false)
  }
  
  const handleExecutionModeChange = async (mode: 'instant' | 'approval' | 'react' | 'query') => {
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
    if (!modelId) return <Sparkles className="w-2.5 h-2.5" />
    const model = models.find(m => m.id === modelId)
    if (model?.provider === 'openai') {
      return <Brain className="w-2.5 h-2.5" />
    }
    return <Sparkles className="w-2.5 h-2.5" />
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
    <>
      {userAssistanceRequest && (
        <UserAssistanceDialog
          assistance_id={userAssistanceRequest.assistance_id}
          question={userAssistanceRequest.question}
          options={userAssistanceRequest.options}
          context={userAssistanceRequest.context}
        />
      )}
      <div className="chat-container">
      {/* Messages Container */}
      <div className="messages-container" ref={messagesContainerRef}>
        {/* Render all messages */}
        {messages.map((message, index) => {
          const isLastUserMessage = index === lastUserIndexInMessages
          
          if (message.role === 'user') {
            const workflowId = message.timestamp
            const workflow = workflows[workflowId]
            const isActive = workflowId === activeWorkflowId
            const isCompleted = !!workflow?.finalResult
            
            return (
              <React.Fragment key={`fragment-${workflowId}`}>
                <div 
                  key={`user-interaction-${workflowId}`} 
                  className="user-interaction-container"
                  data-workflow-id={workflowId}
                >
                  {/* Sticky section: user query */}
                  <div className="sticky-query-section sticky-active">
                    <div 
                      ref={(el) => {
                        if (isLastUserMessage) {                          (currentInteractionRef as React.MutableRefObject<HTMLDivElement | null>).current = el
                        }
                      }}
                      className="user-query-flow-block"
                    >
                      <span className="user-query-text">{message.content}</span>
                    </div>
                  </div>
                  {/* Sticky section: plan */}
                  {(() => {
                    // Проверяем, нужно ли рендерить план
                    const workflowPlan = workflow?.plan
                    const hasPlanContent = workflowPlan && (
                      workflowPlan.planThinking || 
                      workflowPlan.planThinkingIsStreaming || 
                      (workflowPlan.plan && workflowPlan.plan.trim()) || 
                      (workflowPlan.steps && workflowPlan.steps.length > 0) || 
                      workflowPlan.awaitingConfirmation
                    )
                    
                    if (!hasPlanContent) return null
                    
                    return (
                      <div 
                        ref={(el) => {
                          if (el) {
                            stickyPlanSectionRefs.current.set(workflowId, el)                          } else {
                            stickyPlanSectionRefs.current.delete(workflowId)
                          }
                        }}
                        className="sticky-plan-section sticky-active"
                      >
                        {/* Show workflow plan */}
                        <PlanBlock workflowId={workflowId} />
                        
                        {/* Show question forms (Plan mode) */}
                        {(() => {
                          const questionMessages = useChatStore((state) => state.questionMessages[workflowId] || [])
                          return questionMessages.map((question) => (
                            <div key={question.id} style={{ marginTop: '16px', padding: '0 14px' }}>
                              <QuestionForm
                                question={question}
                                workflowId={workflowId}
                                onAnswer={(questionId, answers) => {
                                  useChatStore.getState().updateQuestionAnswer(workflowId, questionId, answers)
                                }}
                              />
                            </div>
                          ))
                        })()}
                      </div>
                    )
                  })()}
                  {/* Прокручиваемый контент - шаги */}
                  {/* Обертываем в дополнительный контейнер для контроля видимости */}
                  {(() => {
                    // Проверяем, нужно ли рендерить шаги
                    const workflowPlan = workflow?.plan
                    const hasStepsContent = workflowPlan && 
                      workflowPlan.steps && 
                      workflowPlan.steps.length > 0 && (
                        Object.keys(workflow?.steps || {}).length > 0 || 
                        workflow?.finalResult
                      )
                    
                    if (!hasStepsContent) return null
                    
                    return (
                      <div 
                        ref={(el) => {
                          if (el) {
                            stepsSectionRefs.current.set(workflowId, el)                          } else {
                            stepsSectionRefs.current.delete(workflowId)
                          }
                        }}
                        className="scrollable-content-wrapper"
                      >
                        <div className="scrollable-content">
                          <StepProgress workflowId={workflowId} />
                          
                          {/* Show action messages (Cursor-style actions) */}
                          {(() => {
                            const actionMessages = useChatStore((state) => state.actionMessages[workflowId] || [])
                            if (actionMessages.length === 0) return null
                            
                            return (
                              <div style={{ padding: '0 14px', marginTop: '16px' }}>
                                <div className="action-messages-list">
                                  {actionMessages.map((action, index) => (
                                    <ActionItem
                                      key={action.id}
                                      action={action}
                                      isLast={index === actionMessages.length - 1}
                                    />
                                  ))}
                                </div>
                              </div>
                            )
                          })()}
                        </div>
                      </div>
                    )
                  })()}
                  {/* Результат - sticky, останавливается после шагов */}
                  {workflow?.finalResult !== null && workflow?.finalResult !== undefined && (
                    <div 
                      ref={(el) => {
                        if (el) {
                          stickyResultSectionRefs.current.set(workflowId, el)
                        } else {
                          stickyResultSectionRefs.current.delete(workflowId)
                        }
                      }}
                      className="sticky-result-section sticky-result-active"
                    >
                      {/* Show result summary if available */}
                      {(() => {
                        const resultSummary = useChatStore((state) => state.resultSummaries[workflowId])
                        if (resultSummary) {
                          return <ResultSummary summary={resultSummary} />
                        }
                        return null
                      })()}
                      
                      <FinalResultBlock content={workflow.finalResult} />
                    </div>
                  )}
                </div>
              </React.Fragment>
            )
          }
          
          if (message.role === 'assistant') {
            // Assistant messages are now handled through workflows and FinalResultBlock
            // We don't render them here to avoid duplication
            return null
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
        
        {/* Render streaming assistant messages FIRST - they might contain reasoning blocks */}
        {(() => {
          const assistantMessagesArray = Object.values(assistantMessages)
          const isEmpty = assistantMessagesArray.length === 0
          
          // #region agent log
          fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:render:assistantMessages',message:'Rendering assistant messages section',data:{isEmpty,assistantMessagesCount:assistantMessagesArray.length,messageIds:assistantMessagesArray.map(m=>m.id),executionMode,messagesCount:messages.length,workflowsCount:Object.keys(workflows).length,activeWorkflowId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
          // #endregion
          
          // CRITICAL: If no assistant messages, return null immediately to prevent empty wrapper
          if (isEmpty) {
            return null
          }
          
          console.log('[ChatInterface] Rendering assistant messages', { 
            count: assistantMessagesArray.length, 
            messageIds: assistantMessagesArray.map(m => m.id),
            executionMode 
          })
          
          return assistantMessagesArray.map((assistantMsg) => {
            console.log('[ChatInterface] Processing assistant message', { 
              id: assistantMsg.id, 
              reasoningBlocksCount: assistantMsg.reasoningBlocks.length,
              answerBlocksCount: assistantMsg.answerBlocks.length,
              executionMode
            })
            
            // CRITICAL: For ReAct mode, render reasoning blocks directly using CollapsibleBlock (same as Plan mode)
            // This check MUST come FIRST, before all other checks, to ensure ReAct blocks are rendered
            if (executionMode === 'react' && assistantMsg.reasoningBlocks.length > 0) {
              console.log('[ChatInterface] ReAct mode - rendering reasoning blocks directly', { 
                messageId: assistantMsg.id, 
                executionMode,
                reasoningBlocksCount: assistantMsg.reasoningBlocks.length
              })
              
              return (
                <div 
                  key={assistantMsg.id} 
                  className="assistant-message-wrapper react-assistant-message-wrapper" 
                  data-message-id={assistantMsg.id} 
                  data-react-mode="true"
                  style={{ maxWidth: '900px', width: '100%', margin: '0 auto', padding: '0 14px', display: 'flex', flexDirection: 'column' }}
                >
                  {assistantMsg.reasoningBlocks.map((block) => {
                    const hasContent = block.content && block.content.trim().length > 0
                    if (!hasContent && !block.isStreaming) {
                      return null
                    }
                    
                    return (
                      <CollapsibleBlock
                        key={block.id}
                        title="думаю..."
                        icon={<Brain className="reasoning-block-icon" />}
                        isStreaming={block.isStreaming}
                        isCollapsed={false} // ReAct blocks start expanded
                        autoCollapse={false} // Don't auto-collapse ReAct blocks
                        alwaysOpen={false}
                        className="react-reasoning-block"
                      >
                        <div className="prose max-w-none prose-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {block.content || (block.isStreaming ? 'Анализирую запрос...' : '')}
                          </ReactMarkdown>
                        </div>
                      </CollapsibleBlock>
                    )
                  })}
                  {/* Render answer blocks if any */}
                  {assistantMsg.answerBlocks.map((block) => {
                    const hasContent = block.content && block.content.trim().length > 0
                    if (!hasContent) {
                      return null
                    }
                    
                    return (
                      <div key={block.id} className="prose max-w-none" style={{ marginTop: '16px' }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {block.content}
                        </ReactMarkdown>
                      </div>
                    )
                  })}
                </div>
              )
            }
            
            // Check if workflow exists - multi-step tasks use workflow system exclusively
            const userMessages = messages.filter(m => m.role === 'user')
            if (userMessages.length > 0) {
              const lastUserMessage = userMessages[userMessages.length - 1]
              const lastUserWorkflowId = lastUserMessage.timestamp
              const lastUserWorkflow = workflows[lastUserWorkflowId]
              
              // Don't render assistant-message-wrapper if workflow exists
              // Multi-step workflows display content through PlanBlock, StepProgress, FinalResultBlock
              // BUT: For ReAct mode, always render assistant messages (no workflow system)
              if (lastUserWorkflow && executionMode !== 'react') {
                // Simple task: no plan or plan has no steps
                const isSimpleTask = !lastUserWorkflow.plan || !lastUserWorkflow.plan.steps || lastUserWorkflow.plan.steps.length === 0
                
                // For simple tasks, don't render ChatMessage (reasoning/answer blocks)
                // The result will be shown in FinalResultBlock instead
                if (isSimpleTask) {
                  console.log('[ChatInterface] Skipping assistant message - simple task with workflow', { messageId: assistantMsg.id })
                  return null
                }
                
                // For multi-step workflows, also don't render ChatMessage
                console.log('[ChatInterface] Skipping assistant message - multi-step workflow', { messageId: assistantMsg.id })
                return null
              }
              
              // For ReAct mode, always render assistant messages (even if workflow exists)
              if (executionMode === 'react') {
                console.log('[ChatInterface] Rendering assistant message for ReAct mode', { messageId: assistantMsg.id })
              }
              
              // No workflow - render normally
              const isSimpleTask = false
              
              // For simple tasks, don't render ChatMessage (reasoning/answer blocks)
              // The result will be shown in FinalResultBlock instead
              if (isSimpleTask) {
                return null
              }
            }
          
          // For non-ReAct mode, check content and use ChatMessage (backward compatibility)
          // Проверяем, есть ли реальный контент в блоках (не только их наличие)
          const hasReasoningContent = assistantMsg.reasoningBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          const hasAnswerContent = assistantMsg.answerBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          const hasContent = hasReasoningContent || hasAnswerContent
          
          console.log('[ChatInterface] Checking content for assistant message (non-ReAct)', {
            messageId: assistantMsg.id,
            reasoningBlocksCount: assistantMsg.reasoningBlocks.length,
            reasoningBlocksContent: assistantMsg.reasoningBlocks.map(b => ({ id: b.id, contentLength: b.content?.length || 0, contentPreview: b.content?.substring(0, 50) })),
            hasReasoningContent,
            hasAnswerContent,
            hasContent
          })
          
          // Если нет реального контента, не рендерим wrapper (ChatMessage вернет null)
          if (!hasContent) {
            console.log('[ChatInterface] No content, skipping assistant message', { messageId: assistantMsg.id })
            return null
          }
          
          // CRITICAL FIX: Mimic ChatMessage logic to check if it will render content
          // This prevents empty wrapper divs from appearing when ChatMessage would return null
          // ChatMessage returns null if:
          // 1. reasoningAnswerPairs.length === 0 (no pairs)
          // 2. allPairsHaveContent === false (all pairs are empty)
          // We need to check this BEFORE rendering the wrapper to avoid empty blocks
          
          // Simulate the reasoningAnswerPairs grouping logic from ChatMessage
          // Extract variables outside IIFE for logging
          const hasValidReasoning = assistantMsg.reasoningBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          const hasValidAnswer = assistantMsg.answerBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          const willRenderReasoning = assistantMsg.reasoningBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          const willRenderAnswer = assistantMsg.answerBlocks.some(block => 
            block.content && block.content.trim().length > 0
          )
          
          const willChatMessageRender = (() => {
            // If no content blocks at all, ChatMessage will return null
            if (!hasContent) {
              return false
            }
            
            // Check if there will be any valid pairs (mimicking ChatMessage logic)
            // A pair is valid if it has at least one block with content
            // If we have at least one valid block, there will be at least one pair
            // But we also need to check that the pair will actually render content
            // (ReasoningBlock and AnswerBlock can return null if content is empty)
            if (!hasValidReasoning && !hasValidAnswer) {
              return false
            }
            
            // Additional check: verify that blocks will actually render
            // ReasoningBlock returns null if content is empty (even if isStreaming)
            // So we need to ensure content exists
            return willRenderReasoning || willRenderAnswer
          })()
          
          console.log('[ChatInterface] willChatMessageRender check (non-ReAct)', {
            messageId: assistantMsg.id,
            willChatMessageRender,
            hasContent,
            hasValidReasoning,
            hasValidAnswer,
            willRenderReasoning,
            willRenderAnswer,
            executionMode
          })
          
          if (!willChatMessageRender) {
            console.log('[ChatInterface] ChatMessage will not render, skipping', { messageId: assistantMsg.id })
            return null
          }
          
          console.log('[ChatInterface] Rendering assistant message with ChatMessage', { messageId: assistantMsg.id })
          
          return (
            <div key={assistantMsg.id} className="assistant-message-wrapper" data-message-id={assistantMsg.id}>
              <ChatMessage message={assistantMsg} />
            </div>
          )
        })
        })()}
        
        
        {/* Scroll spacer */}
        <div className="scroll-spacer" />
      </div>

      {/* Input Area */}
      <div className="input-area">
        <div className="input-fade"></div>
        
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="input-form">
          <div className="input-wrapper">
            {/* Row 1: Full-width Text Input */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Текст"
              disabled={isSending || isAgentTyping}
              rows={1}
              className="chat-input"
            />

            {/* Attached Files Preview */}
            {attachedFiles.length > 0 && (
              <div className="attached-files">
                {attachedFiles.map(file => (
                  <div key={file.id} className="attached-file">
                    {file.preview ? (
                      <img src={file.preview} alt={file.name} className="file-preview" />
                    ) : (
                      <div className="file-icon">📄</div>
                    )}
                    <span className="file-name" title={file.name}>{file.name}</span>
                    <button 
                      type="button"
                      onClick={() => handleRemoveFile(file.id)}
                      className="remove-file"
                      title="Удалить файл"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Row 2: Mode Selector + Model Selector + Action Icons + Send/Stop Button */}
            <div className="input-row-controls">
              {/* Execution Mode Selector */}
              <div className="relative" ref={modeDropdownRef}>
                <button
                  type="button"
                  onClick={() => setIsModeDropdownOpen(!isModeDropdownOpen)}
                  className="mode-selector-dropdown-button"
                  title={
                    executionMode === 'instant' ? 'Мгновенное выполнение' :
                    executionMode === 'approval' ? 'С подтверждением действий' :
                    executionMode === 'query' ? 'Только чтение данных' :
                    'ReAct адаптивный режим'
                  }
                >
                  <span>
                    {executionMode === 'instant' ? 'Агент' :
                     executionMode === 'approval' ? 'План' :
                     executionMode === 'query' ? 'Вопрос' :
                     'ReAct'}
                  </span>
                  <ChevronDown className={`w-2.5 h-2.5 transition-transform ${isModeDropdownOpen ? 'rotate-180' : ''}`} />
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
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('react')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'react' ? 'active' : ''}`}
                    >
                      ReAct
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('query')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'query' ? 'active' : ''}`}
                    >
                      Вопрос
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
                  <ChevronDown className={`w-2.5 h-2.5 transition-transform ${isModelDropdownOpen ? 'rotate-180' : ''}`} />
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

              {/* New Dialog Icon */}
              <button
                type="button"
                onClick={handleNewSession}
                className="input-icon-button"
                title="Новый диалог"
              >
                <Plus className="w-3 h-3" />
              </button>
              
              {/* File Upload */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,.pdf"
                multiple
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="input-icon-button"
                title="Прикрепить файл (изображение или PDF)"
              >
                <Paperclip className="w-3 h-3" />
              </button>

              {/* Spacer */}
              <div className="input-actions-spacer"></div>

              {/* Send/Stop Button */}
              {(isSending || isAgentTyping) ? (
                <button
                  type="button"
                  onClick={handleStopGeneration}
                  className="send-button stop-button"
                  title="Остановить генерацию"
                >
                  <Square className="w-3 h-3" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={(!input.trim() && attachedFiles.length === 0)}
                  className="send-button"
                  title="Отправить"
                >
                  <Send className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

          {/* Hint */}
          <p className="input-hint">
            <kbd>Enter</kbd> отправить • <kbd>Shift + Enter</kbd> новая строка
          </p>
        </form>
      </div>
    </div>
    </>
  )
}
