import React, { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Loader2, Sparkles, Plus, Paperclip, ChevronDown, Brain, Square, X, Mic, MicOff } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useSettingsStore, ExecutionMode } from '../store/settingsStore'
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
// ThinkingMessage removed - using IntentMessage instead
import { IntentMessage } from './IntentMessage'

interface AttachedFile {
  id: string
  name: string
  type: string
  preview?: string
  content?: string // Для текстовых файлов и PDF
}

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isModeDropdownOpen, setIsModeDropdownOpen] = useState(false)
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [shouldScrollToNew, setShouldScrollToNew] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const [filePreviewModal, setFilePreviewModal] = useState<{name: string, content: string, type: string, preview?: string} | null>(null)
  const [isListening, setIsListening] = useState(false)
  const currentInteractionRef = useRef<HTMLDivElement>(null)
  const lastUserMessageCountRef = useRef<number>(0)
  const isCollapsingRef = useRef<boolean>(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const modeDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const finalTextRef = useRef<string>('')
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
    resultSummaries,
    questionMessages,
    actionMessages,
    currentAction,
    clearCurrentAction,
    intentBlocks,
    toggleIntentCollapse,
    toggleIntentPhase,
    showThinkingIndicator,
    setShowThinkingIndicator,
  } = useChatStore()
  
  const { executionMode, setExecutionMode, showReasoning } = useSettingsStore()
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
        setAgentTyping(false)
      }, 60000) // 60 seconds timeout
      
      return () => clearTimeout(timeout)
    }
  }, [isAgentTyping, setAgentTyping])
  
  // Fetch models on mount
  useEffect(() => {
    fetchModels().catch((err) => {
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
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:150',message:'scroll effect triggered',data:{messagesLength:messages.length,shouldScrollToNew,userMessagesCount:messages.filter(m => m.role === 'user').length,lastUserMessageCount:lastUserMessageCountRef.current,currentInteractionRefExists:!!currentInteractionRef.current,messagesContainerRefExists:!!messagesContainerRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    const userMessages = messages.filter(m => m.role === 'user')
    const currentUserMessageCount = userMessages.length
    
    // Проверяем, появилось ли новое user сообщение
    const hasNewUserMessage = currentUserMessageCount > lastUserMessageCountRef.current
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:156',message:'scroll check',data:{hasNewUserMessage,currentUserMessageCount,lastUserMessageCount:lastUserMessageCountRef.current,currentInteractionRefExists:!!currentInteractionRef.current,messagesContainerRefExists:!!messagesContainerRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (!hasNewUserMessage || !currentInteractionRef.current || !messagesContainerRef.current) {
      if (hasNewUserMessage) {
        lastUserMessageCountRef.current = currentUserMessageCount
      }
      return
    }
    
    // Обновляем счетчик
    lastUserMessageCountRef.current = currentUserMessageCount
    
    // Функция для выполнения прокрутки с повторными попытками
    const attemptScroll = (attempt: number) => {
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:168',message:'attemptScroll called',data:{attempt,currentInteractionRefExists:!!currentInteractionRef.current,messagesContainerRefExists:!!messagesContainerRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      if (!currentInteractionRef.current || !messagesContainerRef.current) {        return
      }
      
      const container = messagesContainerRef.current
      const element = currentInteractionRef.current
      
      // Находим родительский user-interaction-container для правильного расчета позиции
      const interactionContainer = element.closest('.user-interaction-container') as HTMLElement
      
      if (!interactionContainer) {
        // #region debug log
        fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:178',message:'attemptScroll: no interactionContainer found',data:{attempt,elementText:element.textContent?.substring(0,50)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
        // #endregion
        return
      }
      
      // Используем getBoundingClientRect для получения абсолютной позиции
      const containerRect = container.getBoundingClientRect()
      const elementRect = interactionContainer.getBoundingClientRect()
      
      // Вычисляем позицию прокрутки: позиция элемента относительно контейнера + текущая прокрутка
      const scrollTop = container.scrollTop + (elementRect.top - containerRect.top) - 52 // 52px для header
      
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:186',message:'attemptScroll: calculated scroll position',data:{attempt,elementRectTop:elementRect.top,containerRectTop:containerRect.top,relativeTop:elementRect.top - containerRect.top,currentScrollTop:container.scrollTop,calculatedScrollTop:scrollTop},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      // Проверяем, что элемент имеет правильную позицию (не 0 или отрицательную)
      if ((elementRect.top - containerRect.top) <= 0 && attempt < 5) {        // Элемент еще не готов, пробуем еще раз
        setTimeout(() => attemptScroll(attempt + 1), 100)
        return
      }
      
      container.scrollTo({
        top: Math.max(0, scrollTop),
        behavior: 'smooth'
      })
      
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:197',message:'attemptScroll: scroll executed',data:{attempt,finalScrollTop:Math.max(0, scrollTop)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      setShouldScrollToNew(false)
    }
    
    // Используем несколько requestAnimationFrame и setTimeout для гарантии, что элемент отрендерился
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setTimeout(() => attemptScroll(0), 50)
      })
    })
  }, [messages.length, shouldScrollToNew])

  // Функция для проверки, находится ли пользователь внизу диалога (в пределах 200px)
  const isUserNearBottom = useCallback((container: HTMLElement): boolean => {
    const scrollTop = container.scrollTop
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    return distanceFromBottom <= 200
  }, [])

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

  // Слушаем события сворачивания/разворачивания блоков
  // При разворачивании/сворачивании блоков "Думаю" не прокручиваем, если пользователь читает старые сообщения
  useEffect(() => {
    const handleCollapsing = () => {
      isCollapsingRef.current = true
    }
    
    const handleCollapsed = () => {
      isCollapsingRef.current = false
      
      // После сворачивания проверяем, нужно ли скроллить
      if (!messagesContainerRef.current) return
      const container = messagesContainerRef.current
      const inputArea = document.querySelector('.input-area') as HTMLElement
      if (!inputArea) return
      
      // Если пользователь не внизу, не выполняем автоскролл
      if (!isUserNearBottom(container)) {
        return
      }
      
      // Если пользователь внизу, проверяем, не уходит ли контент под input
      requestAnimationFrame(() => {
        const allContentElements = container.querySelectorAll(
          '.iteration-block, .iteration-think-content, .iteration-operation-content, ' +
          '.sticky-result-section, .intent-message, .step-progress-item, .reasoning-block'
        )
        
        if (allContentElements.length === 0) return
        
        let lowestBottom = 0
        allContentElements.forEach(el => {
          const rect = el.getBoundingClientRect()
          if (rect.bottom > lowestBottom) {
            lowestBottom = rect.bottom
          }
        })
        
        const inputRect = inputArea.getBoundingClientRect()
        const inputTopWithGap = inputRect.top - 20
        
        if (lowestBottom > inputTopWithGap) {
          const scrollAmount = lowestBottom - inputTopWithGap
          container.scrollTo({
            top: container.scrollTop + scrollAmount,
            behavior: 'smooth'
          })
        }
      })
    }
    
    const handleExpanding = () => {
      // При разворачивании проверяем позицию скролла
      if (!messagesContainerRef.current) return
      const container = messagesContainerRef.current
      const inputArea = document.querySelector('.input-area') as HTMLElement
      if (!inputArea) return
      
      // Если пользователь не внизу, не выполняем автоскролл
      if (!isUserNearBottom(container)) {
        return
      }
      
      // Если пользователь внизу, проверяем, не уходит ли контент под input
      requestAnimationFrame(() => {
        const allContentElements = container.querySelectorAll(
          '.iteration-block, .iteration-think-content, .iteration-operation-content, ' +
          '.sticky-result-section, .intent-message, .step-progress-item, .reasoning-block'
        )
        
        if (allContentElements.length === 0) return
        
        let lowestBottom = 0
        allContentElements.forEach(el => {
          const rect = el.getBoundingClientRect()
          if (rect.bottom > lowestBottom) {
            lowestBottom = rect.bottom
          }
        })
        
        const inputRect = inputArea.getBoundingClientRect()
        const inputTopWithGap = inputRect.top - 20
        
        if (lowestBottom > inputTopWithGap) {
          const scrollAmount = lowestBottom - inputTopWithGap
          container.scrollTo({
            top: container.scrollTop + scrollAmount,
            behavior: 'smooth'
          })
        }
      })
    }
    
    window.addEventListener('collapsibleBlockCollapsing', handleCollapsing)
    window.addEventListener('collapsibleBlockCollapsed', handleCollapsed)
    window.addEventListener('collapsibleBlockExpanding', handleExpanding)
    
    return () => {
      window.removeEventListener('collapsibleBlockCollapsing', handleCollapsing)
      window.removeEventListener('collapsibleBlockCollapsed', handleCollapsed)
      window.removeEventListener('collapsibleBlockExpanding', handleExpanding)
    }
  }, [isUserNearBottom])

  // Автоскролл при любых изменениях контента (не только finalResult)
  // При появлении новых блоков или текста прокручиваем так, чтобы ничего не уходило под input
  // НО только если пользователь уже находится внизу диалога
  useEffect(() => {
    if (!messagesContainerRef.current) return
    
    const container = messagesContainerRef.current
    const inputArea = document.querySelector('.input-area') as HTMLElement
    if (!inputArea) return
    
    // Пропускаем автоскролл если пользователь не внизу (читает старые сообщения)
    if (!isUserNearBottom(container)) {
      return
    }
    
    // Функция для проверки и скролла
    const checkAndScroll = () => {
      // Находим самый нижний видимый элемент контента
      const allContentElements = container.querySelectorAll(
        '.iteration-block, .iteration-think-content, .iteration-operation-content, ' +
        '.sticky-result-section, .intent-message, .step-progress-item'
      )
      
      if (allContentElements.length === 0) return
      
      // Получаем самый нижний элемент
      let lowestBottom = 0
      allContentElements.forEach(el => {
        const rect = el.getBoundingClientRect()
        if (rect.bottom > lowestBottom) {
          lowestBottom = rect.bottom
        }
      })
      
      const inputRect = inputArea.getBoundingClientRect()
      const inputTopWithGap = inputRect.top - 20
      
      // Если контент уходит под input, скроллим
      if (lowestBottom > inputTopWithGap) {
        const scrollAmount = lowestBottom - inputTopWithGap
        container.scrollTo({
          top: container.scrollTop + scrollAmount,
          behavior: 'smooth'
        })
      }
    }
    
    // Проверяем при каждом изменении
    checkAndScroll()
  }, [activeWorkflowId, workflows, intentBlocks, isAgentTyping, isUserNearBottom])
  
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

  // Автоскролл при любых изменениях контента (не только finalResult)
  // При появлении новых блоков или текста прокручиваем так, чтобы ничего не уходило под input
  // НО только если пользователь уже находится внизу диалога
  useEffect(() => {
    if (!messagesContainerRef.current) return
    
    const container = messagesContainerRef.current
    const inputArea = document.querySelector('.input-area') as HTMLElement
    if (!inputArea) return
    
    // Пропускаем автоскролл если пользователь не внизу (читает старые сообщения)
    if (!isUserNearBottom(container)) {
      return
    }
    
    // Функция для проверки и скролла
    const checkAndScroll = () => {
      // Находим самый нижний видимый элемент контента
      const allContentElements = container.querySelectorAll(
        '.iteration-block, .iteration-think-content, .iteration-operation-content, ' +
        '.sticky-result-section, .intent-message, .step-progress-item'
      )
      
      if (allContentElements.length === 0) return
      
      // Получаем самый нижний элемент
      let lowestBottom = 0
      allContentElements.forEach(el => {
        const rect = el.getBoundingClientRect()
        if (rect.bottom > lowestBottom) {
          lowestBottom = rect.bottom
        }
      })
      
      const inputRect = inputArea.getBoundingClientRect()
      const inputTopWithGap = inputRect.top - 20
      
      // Если контент уходит под input, скроллим
      if (lowestBottom > inputTopWithGap) {
        const scrollAmount = lowestBottom - inputTopWithGap
        container.scrollTo({
          top: container.scrollTop + scrollAmount,
          behavior: 'smooth'
        })
      }
    }
    
    // Проверяем при каждом изменении
    checkAndScroll()
  }, [activeWorkflowId, workflows, intentBlocks, isAgentTyping, isUserNearBottom])

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
        alert('Не удалось создать сессию для загрузки файла')
        return
      }
    }
    
    // Process each file
    for (const file of Array.from(files)) {
      // Validate file type
      const supportedTypes = [
        'image/',
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
      ]
      if (!supportedTypes.some(type => file.type.startsWith(type) || file.type === type)) {
        alert(`Файл "${file.name}" не поддерживается. Поддерживаются только изображения, PDF и Word документы (.docx).`)
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
        let content: string | undefined
        
        if (file.type.startsWith('image/')) {
          preview = URL.createObjectURL(file)
        } else if (file.type === 'application/pdf') {
          // Для PDF сохраняем как data URL для просмотра
          const reader = new FileReader()
          await new Promise<void>((resolve, reject) => {
            reader.onload = (e) => {
              content = e.target?.result as string
              resolve()
            }
            reader.onerror = reject
            reader.readAsDataURL(file)
          })
        }
        
        setAttachedFiles(prev => [...prev, {
          id: fileData.file_id,
          name: file.name,
          type: file.type,
          preview,
          content
        }])
      } catch (error: any) {
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

  const handleViewFile = (file: AttachedFile) => {
    setFilePreviewModal({
      name: file.name,
      content: file.content || '',
      type: file.type,
      preview: file.preview
    })
  }
  
  const handleSend = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || isSending) {
      return
    }

    const userMessage = input.trim()
    const fileIds = attachedFiles.map(f => f.id)
    
    // Collect open files from workspace tabs (excluding placeholder)
    const openFiles = tabs
      .filter(tab => tab.type !== 'placeholder')
      .map(tab => {
        // Extract IDs from tab.data (camelCase) or from URL if not available
        let documentId = tab.data?.documentId || tab.data?.document_id
        let spreadsheetId = tab.data?.spreadsheetId || tab.data?.spreadsheet_id
        
        // If IDs not in data, try to extract from URL
        if (!documentId && tab.type === 'docs' && tab.url) {
          const docMatch = tab.url.match(/\/document\/d\/([a-zA-Z0-9-_]+)/)
          if (docMatch) {
            documentId = docMatch[1]
          }
        }
        if (!spreadsheetId && tab.type === 'sheets' && tab.url) {
          const sheetMatch = tab.url.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/)
          if (sheetMatch) {
            spreadsheetId = sheetMatch[1]
          }
        }
        
        return {
          type: tab.type,
          title: tab.title,
          url: tab.url,
          spreadsheet_id: spreadsheetId,
          document_id: documentId,
        }
      })
    
    setInput('')
    setIsSending(true)

    // Don't clear workflow - we want to preserve history and only work with the active (last) workflow
    // The workflow will be managed per user message through metadata

    // Add user message immediately to show it in UI
    const userMsgTimestamp = new Date().toISOString()
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:701',message:'handleSend: adding user message',data:{userMsgTimestamp,userMessage:userMessage.substring(0,50),currentMessagesCount:messages.length,currentUserMessagesCount:messages.filter(m => m.role === 'user').length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    addMessage({
      role: 'user',
      content: userMessage,
      timestamp: userMsgTimestamp,
      metadata: {
        attachedFiles: attachedFiles.map(f => ({
          id: f.id,
          name: f.name,
          type: f.type,
          preview: f.preview,
          content: f.content
        }))
      }
    })

    // Clear attached files (but don't revoke preview URLs yet - they're needed for modal)
    setAttachedFiles([])

    // Activate scroll to new message    setShouldScrollToNew(true)
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:720',message:'handleSend: setShouldScrollToNew(true)',data:{userMsgTimestamp},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    // Mark agent as typing
    setAgentTyping(true)
    
    // Показываем "Думаю..." через 0.5 секунды (если intent не появится раньше)
    setTimeout(() => {
      // Проверяем что всё ещё в процессе отправки и нет intent'ов
      const state = useChatStore.getState()
      if (state.isAgentTyping && !state.activeIntentId) {
        setShowThinkingIndicator(true)
      }
    }, 500)

    try {
      // Try WebSocket first if session exists and connection is open
      // WebSocket supports file_ids and open_files
      if (currentSession && wsClient.isConnected()) {
        const sent = wsClient.sendMessage(userMessage, fileIds.length > 0 ? fileIds : undefined, openFiles.length > 0 ? openFiles : undefined)
        if (!sent) {
          await sendMessage({
            message: userMessage,
            session_id: currentSession,
            execution_mode: executionMode,
            file_ids: fileIds.length > 0 ? fileIds : undefined,
            open_files: openFiles.length > 0 ? openFiles : undefined,
          })
        }
      } else if (currentSession) {
        // Session exists but WebSocket not connected, try to reconnect and use REST API as fallback
        wsClient.connect(currentSession)
        const response = await sendMessage({
          message: userMessage,
          session_id: currentSession,
          execution_mode: executionMode,
          file_ids: fileIds.length > 0 ? fileIds : undefined,
          open_files: openFiles.length > 0 ? openFiles : undefined,
        })
        
        // Handle REST API response when WebSocket is not connected
        if (response?.result?.response) {
          // For query mode, save to workflow finalResult instead of regular messages
          if (executionMode === 'query') {
            const workflowId = messages.find(m => m.role === 'user')?.timestamp
            if (workflowId) {
              useChatStore.getState().setWorkflowFinalResult(workflowId, response.result.response)
            }
          } else {
            addMessage({
              role: 'assistant',
              content: response.result.response,
              timestamp: new Date().toISOString(),
            })
          }
        }
      } else {
        // Create new session FIRST, then connect WebSocket, then send message
        const sessionData = await createSession(executionMode, selectedModel || undefined)
        const newSessionId = sessionData.session_id
        setCurrentSession(newSessionId)
        
        // Connect WebSocket BEFORE sending message
        wsClient.connect(newSessionId)
        
        // Wait for WebSocket to connect (backend waits up to 5 seconds)
        let connected = false
        for (let i = 0; i < 60; i++) {
          await new Promise(resolve => setTimeout(resolve, 100))
          if (wsClient.isConnected()) {
            connected = true
            break
          }
        }
        
        if (!connected) {
          // WebSocket did not connect within 6 seconds, proceeding anyway
        }
        
        // Now send message via WebSocket (preferred) or REST API (fallback)
        // WebSocket supports file_ids and open_files
        if (wsClient.isConnected()) {
          const sent = wsClient.sendMessage(userMessage, fileIds.length > 0 ? fileIds : undefined, openFiles.length > 0 ? openFiles : undefined, executionMode)
          if (!sent) {
            const response = await sendMessage({
              message: userMessage,
              session_id: newSessionId,
              execution_mode: executionMode,
              file_ids: fileIds.length > 0 ? fileIds : undefined,
              open_files: openFiles.length > 0 ? openFiles : undefined,
            })
            
            // Handle REST API response when WebSocket send failed
            if (response?.result?.response) {
              addMessage({
                role: 'assistant',
                content: response.result.response,
                timestamp: new Date().toISOString(),
              })
            }
          }
        } else {
          const response = await sendMessage({
            message: userMessage,
            session_id: newSessionId,
            execution_mode: executionMode,
            file_ids: fileIds.length > 0 ? fileIds : undefined,
            open_files: openFiles.length > 0 ? openFiles : undefined,
          })
            
          // Handle REST API response when WebSocket is not connected
          if (response?.result?.response) {
            addMessage({
              role: 'assistant',
              content: response.result.response,
              timestamp: new Date().toISOString(),
            })
          }
        }
      }
    } catch (error: any) {
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
    wsClient.stopGeneration()
    setIsSending(false)
    setAgentTyping(false)
  }
  
  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Ваш браузер не поддерживает голосовой ввод. Пожалуйста, используйте Chrome или Edge.')
      return
    }
    
    // Останавливаем предыдущую запись, если она активна
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    
    const recognition = new SpeechRecognition()
    recognition.lang = 'ru-RU'
    recognition.continuous = true
    recognition.interimResults = true
    
    // Инициализируем накопленный текст текущим значением input
    finalTextRef.current = input
    
    recognition.onresult = (event) => {
      let finalTranscript = ''
      let interimTranscript = ''
      
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' '
        } else {
          interimTranscript = transcript
        }
      }
      
      // Добавляем финальные результаты к накопленному тексту
      if (finalTranscript) {
        finalTextRef.current += finalTranscript
      }
      
      // Показываем накопленный финальный текст + текущий промежуточный
      setInput(finalTextRef.current + (interimTranscript ? ' ' + interimTranscript : ''))
    }
    
    recognition.onerror = (event) => {
      setIsListening(false)
      
      if (event.error === 'no-speech') {
        // Тихая ошибка - просто останавливаем запись
        recognition.stop()
      } else if (event.error === 'not-allowed') {
        alert('Доступ к микрофону запрещён. Пожалуйста, разрешите доступ в настройках браузера.')
      } else {
        alert(`Ошибка распознавания речи: ${event.error}`)
      }
    }
    
    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
    }
    
    try {
      recognitionRef.current = recognition
      recognition.start()
      setIsListening(true)
    } catch (error) {
      setIsListening(false)
      alert('Не удалось начать запись. Проверьте, что микрофон подключён и разрешён доступ.')
    }
  }, [input])
  
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    setIsListening(false)
    finalTextRef.current = '' // Сбрасываем накопленный текст
  }, [])
  
  // Cleanup при размонтировании компонента
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
        recognitionRef.current = null
      }
    }
  }, [])

  // Handle keyboard shortcuts - focus input
  useEffect(() => {
    const handleFocusInput = () => {
      if (textareaRef.current) {
        textareaRef.current.focus()
      }
    }

    window.addEventListener('focus-chat-input', handleFocusInput as EventListener)
    return () => {
      window.removeEventListener('focus-chat-input', handleFocusInput as EventListener)
    }
  }, [])
  
  const handleExecutionModeChange = async (mode: ExecutionMode) => {
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
                      {message.metadata?.attachedFiles?.length > 0 && (
                        <div className="user-attached-files">
                          {message.metadata?.attachedFiles?.map((file: AttachedFile) => (
                            <div 
                              key={file.id} 
                              className="user-attached-file"
                              onClick={() => handleViewFile(file)}
                              title={file.name}
                            >
                              {file.preview ? (
                                <img src={file.preview} alt={file.name} className="user-file-preview" />
                              ) : (
                                <span className="user-file-icon">📄</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Research phase indicator - show if this is the active workflow and we're in Plan mode */}
                  {(() => {
                    const isActive = workflowId === activeWorkflowId
                    const isPlanMode = executionMode === 'plan'
                    if (!isActive || !isPlanMode) return null
                    
                    // Find research phase message in messages array
                    const researchMessage = messages.find(
                      (msg) => 
                        msg.role === 'assistant' && 
                        msg.metadata?.type === 'phase_indicator' &&
                        msg.metadata?.phase === 'research' &&
                        new Date(msg.timestamp) >= new Date(message.timestamp) // Message after this user message
                    )
                    
                    if (!researchMessage) return null
                    
                    return (
                      <div className="research-phase-indicator" style={{ padding: '0 14px', marginTop: '12px', marginBottom: '12px' }}>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
                          <div className="text-sm text-blue-900 flex items-center gap-2">
                            <span className="text-blue-600">🔍</span>
                            <span>{researchMessage.content}</span>
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                  
                  {/* Intent blocks section (Cursor-style) - renders independently of plan */}
                  {/* Intent Blocks с фазами Планирую/Выполняю */}
                  {(() => {
                    const workflowIntentBlocks = intentBlocks[workflowId] || []
                    // isLastUserMessage уже вычислен выше
                    const shouldShowThinking = isLastUserMessage && showThinkingIndicator && workflowIntentBlocks.length === 0
                    const hasIntentBlocks = workflowIntentBlocks.length > 0
                    
                    // Ничего не показываем если нет блоков и не нужно показывать thinking
                    if (!hasIntentBlocks && !shouldShowThinking) {
                      return null
                    }
                    
                    return (
                      <div className="intent-blocks-section">
                        {/* Показываем "Думаю..." только если нет блоков */}
                        {shouldShowThinking && !hasIntentBlocks && (
                          <div className="thinking-indicator">
                            <span className="thinking-indicator-text">Думаю</span>
                            <span className="thinking-indicator-dots" />
                          </div>
                        )}
                        
                        {/* Intent блоки с фазами Планирую/Выполняю */}
                        {hasIntentBlocks && (() => {
                          // Фильтруем шаги: исключаем служебные шаги без реального содержимого
                          const filteredBlocks = workflowIntentBlocks.filter((block, index) => {
                            const isFormingAnswer = 
                              block.intent?.toLowerCase().includes('формирую ответ') ||
                              block.intent?.toLowerCase().includes('forming the answer') ||
                              block.id?.includes('intent-final') ||
                              block.id?.includes('final')
                            const hasNoReasoning = !block.thinkingText || block.thinkingText.trim().length === 0
                            const hasNoDetails = !block.details || block.details.length === 0
                            const hasNoOperations = !block.operations || Object.keys(block.operations).length === 0
                            const hasNoActions = hasNoDetails && hasNoOperations
                            
                            // Исключаем шаг "Формирую ответ", если нет reasoning и нет действий
                            if (isFormingAnswer && hasNoReasoning && hasNoActions) return false
                            
                            // Исключаем первый шаг, если он просто повторяет запрос пользователя без анализа
                            // (это происходит когда агент читает прикреплённые файлы)
                            if (index === 0 && hasNoActions) {
                              // Проверяем, есть ли следующий шаг с реальным анализом
                              const hasNextStep = workflowIntentBlocks.length > 1
                              // Если первый шаг — просто запрос без действий, а есть второй шаг — пропускаем первый
                              if (hasNextStep) return false
                            }
                            
                            return true
                          })
                          
                          // Считаем количество оставшихся шагов
                          const validStepCount = filteredBlocks.length
                          const shouldShowStepNumbers = validStepCount >= 2
                          
                          return filteredBlocks.map((intentBlock, index) => {
                            // Вычисляем номер шага для отображения
                            const stepNumber = shouldShowStepNumbers ? index + 1 : undefined
                            
                            return (
                              <IntentMessage
                                key={intentBlock.id}
                                block={intentBlock}
                                workflowId={workflowId}
                                stepNumber={stepNumber}
                                onToggleCollapse={() => toggleIntentCollapse(workflowId, intentBlock.id)}
                                onTogglePlanningCollapse={() => toggleIntentPhase(workflowId, intentBlock.id, 'planning')}
                                onToggleExecutingCollapse={() => toggleIntentPhase(workflowId, intentBlock.id, 'executing')}
                              />
                            )
                          })
                        })()}
                      </div>
                    )
                  })()}
                  
                  {/* Sticky section: plan */}
                  {(() => {
                    // План рендерится ТОЛЬКО в режиме 'plan'
                    // В режимах 'agent' и 'query' план НЕ отображается
                    if (executionMode !== 'plan') {
                      return null
                    }
                    
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
                        {(questionMessages[workflowId] || []).map((question) => (
                          <div key={question.id} style={{ marginTop: '16px', padding: '0 14px' }}>
                            <QuestionForm
                              question={question}
                              workflowId={workflowId}
                              onAnswer={(questionId, answers) => {
                                useChatStore.getState().updateQuestionAnswer(workflowId, questionId, answers)
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                  {/* Прокручиваемый контент - шаги */}
                  {/* Обертываем в дополнительный контейнер для контроля видимости */}
                  {(() => {
                    // Шаги рендерятся ТОЛЬКО в режиме 'plan'
                    // В режимах 'agent' и 'query' шаги НЕ отображаются
                    if (executionMode !== 'plan') {
                      return null
                    }
                    
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
                          {(actionMessages[workflowId] || []).length > 0 && (
                            <div style={{ padding: '0 14px', marginTop: '16px' }}>
                              <div className="action-messages-list">
                                {(actionMessages[workflowId] || []).map((action, index) => (
                                  <ActionItem
                                    key={action.id}
                                    action={action}
                                    isLast={index === (actionMessages[workflowId] || []).length - 1}
                                  />
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })()}
                  {/* Результат - sticky, останавливается после шагов */}
                  {(() => {
                    const hasFinalResult = workflow?.finalResult !== null && workflow?.finalResult !== undefined
                    
                    if (!hasFinalResult || !workflow || !workflow.finalResult) {
                      return null
                    }
                    
                    const finalResultContent = workflow.finalResult
                    
                    return (
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
                        {resultSummaries[workflowId] && (
                          <ResultSummary summary={resultSummaries[workflowId]} />
                        )}
                        
                        <FinalResultBlock content={finalResultContent} />
                      </div>
                    )
                  })()}
                </div>
              </React.Fragment>
            )
          }
          
          if (message.role === 'assistant') {
            // Phase indicator messages are now rendered inside user-interaction-container
            // Don't render them here to avoid duplication
            if (message.metadata?.type === 'phase_indicator') {
              return null
            }
            
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
          
          // CRITICAL: If no assistant messages, return null immediately to prevent empty wrapper
          if (isEmpty) {
            return null
          }
          
          return assistantMessagesArray.map((assistantMsg) => {
            // #region debug log
            fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ChatInterface.tsx:1351',message:'rendering assistant message',data:{assistantMsgId:assistantMsg.id,reasoningBlocksCount:assistantMsg.reasoningBlocks.length,answerBlocksCount:assistantMsg.answerBlocks.length,executionMode,userMessagesCount:messages.filter(m => m.role === 'user').length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
            // #endregion
            // CRITICAL: For ReAct mode, render reasoning blocks directly using CollapsibleBlock (same as Plan mode)
            // This check MUST come FIRST, before all other checks, to ensure ReAct blocks are rendered
            // For Query and Agent modes, only show reasoning if showReasoning setting is enabled
            const shouldShowReasoning = 
              (executionMode === 'query' && useSettingsStore.getState().showReasoning) ||
              (executionMode === 'agent' && useSettingsStore.getState().showReasoning)
            
            if (shouldShowReasoning && assistantMsg.reasoningBlocks.length > 0) {
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
              // Agent mode now works like Query mode - uses workflow.finalResult
              if (lastUserWorkflow && executionMode !== 'plan') {
                // Simple task: no plan or plan has no steps
                const isSimpleTask = !lastUserWorkflow.plan || !lastUserWorkflow.plan.steps || lastUserWorkflow.plan.steps.length === 0
                
                // For simple tasks, don't render ChatMessage (reasoning/answer blocks)
                // The result will be shown in FinalResultBlock instead
                if (isSimpleTask) {
                  return null
                }
                
                // For multi-step workflows, also don't render ChatMessage
                return null
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
          
          // Если нет реального контента, не рендерим wrapper (ChatMessage вернет null)
          if (!hasContent) {
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
          
          if (!willChatMessageRender) {
            return null
          }
          
          return (
            <div key={assistantMsg.id} className="assistant-message-wrapper" data-message-id={assistantMsg.id}>
              <ChatMessage message={assistantMsg} />
            </div>
          )
        })
        })()}
        
        {/* ThinkingMessage removed - now using IntentMessage (Cursor-style) instead */}
        
        
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
                    <div 
                      className="attached-file-content"
                      onClick={() => handleViewFile(file)}
                      title={`Просмотр: ${file.name}`}
                    >
                      {file.preview ? (
                        <img src={file.preview} alt={file.name} className="file-preview" />
                      ) : (
                        <div className="file-icon">📄</div>
                      )}
                      <span className="file-name" title={file.name}>{file.name}</span>
                    </div>
                    <button 
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRemoveFile(file.id)
                      }}
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
                    executionMode === 'query' ? 'Только чтение данных' :
                    executionMode === 'plan' ? 'С планированием и подтверждением' :
                    'Автономное выполнение'
                  }
                >
                  <span>
                    {executionMode === 'query' ? 'Вопрос' :
                     executionMode === 'plan' ? 'План' :
                     'Агент'}
                  </span>
                  <ChevronDown className={`w-2.5 h-2.5 transition-transform ${isModeDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isModeDropdownOpen && (
                  <div className="mode-selector-dropdown">
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
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('plan')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'plan' ? 'active' : ''}`}
                    >
                      План
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        handleExecutionModeChange('agent')
                        setIsModeDropdownOpen(false)
                      }}
                      className={`mode-dropdown-item ${executionMode === 'agent' ? 'active' : ''}`}
                    >
                      Агент
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
                accept="image/*,.pdf,.doc,.docx"
                multiple
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="input-icon-button"
                title="Прикрепить файл (изображение, PDF или Word)"
              >
                <Paperclip className="w-3 h-3" />
              </button>
              
              {/* Voice Input Button */}
              <button
                type="button"
                onClick={isListening ? stopListening : startListening}
                className={`input-icon-button ${isListening ? 'recording' : ''}`}
                title={isListening ? 'Остановить запись' : 'Голосовой ввод'}
                disabled={isSending || isAgentTyping}
              >
                {isListening ? (
                  <MicOff className="w-3 h-3 text-red-500" />
                ) : (
                  <Mic className="w-3 h-3" />
                )}
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

    {/* File Preview Modal */}
    {filePreviewModal && (
      <div className="file-preview-modal-overlay" onClick={() => setFilePreviewModal(null)}>
        <div className="file-preview-modal" onClick={(e) => e.stopPropagation()}>
          <div className="file-preview-modal-header">
            <h3 className="file-preview-modal-title">{filePreviewModal.name}</h3>
            <button
              className="file-preview-modal-close"
              onClick={() => setFilePreviewModal(null)}
              title="Закрыть"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="file-preview-modal-content">
            {filePreviewModal.type.startsWith('image/') && filePreviewModal.preview ? (
              <img 
                src={filePreviewModal.preview} 
                alt={filePreviewModal.name}
                className="file-preview-modal-image"
              />
            ) : filePreviewModal.type === 'application/pdf' && filePreviewModal.content ? (
              <iframe
                src={filePreviewModal.content}
                className="file-preview-modal-pdf"
                title={filePreviewModal.name}
              />
            ) : (
              <div className="file-preview-modal-text">
                {filePreviewModal.content || 'Содержимое файла недоступно'}
              </div>
            )}
          </div>
        </div>
      </div>
    )}
    </>
  )
}
