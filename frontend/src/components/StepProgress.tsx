import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Brain } from 'lucide-react'
import { useChatStore, WorkflowStep } from '../store/chatStore'
import { CollapsibleBlock } from './CollapsibleBlock'
import { FilePreviewCard } from './FilePreviewCard'
import { useWorkspaceStore } from '../store/workspaceStore'

interface StepProgressProps {
  workflowId: string
}

interface AttemptBlock {
  number: string
  title: string
  content: string
}

// Parse response text into action preparation and result parts
function parseStepResponse(text: string): { actionPreparation: string, result: string } {
  // Find marker "**Результат шага:**" or "**Результат:**"
  const resultMarker = /(\*\*Результат\s+шага:\*\*|\*\*Результат:\*\*)/i
  const match = text.match(resultMarker)
  
  if (match && match.index !== undefined) {
    const markerIndex = match.index
    const actionPreparation = text.substring(0, markerIndex).trim()
    const result = text.substring(markerIndex + match[0].length).trim()
    return { actionPreparation, result }
  }
  
  // Fallback: If no marker found, try to extract intermediate messages from the text
  // Look for patterns like "Открываю...", "Читаю...", "Анализирую..." etc.
  const intermediatePatterns = [
    /^(Открываю|Ищу|Читаю|Анализирую|Создаю|Добавляю|Применяю|Перемещаю|Формулирую|Готовлю|Выполняю|Проверяю|Нашел|Нашла|Прочитал|Прочитала|Создал|Создала|Добавил|Добавила|Применил|Применила)[^.!?]*[.!?]?/im,
    /^[○•\-\*]\s*(.+)$/m, // List items
  ]
  
  // Try to split by sentences and find intermediate messages
  const lines = text.split('\n').filter(line => line.trim())
  const intermediateLines: string[] = []
  let resultStartIndex = -1
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    // Check if line looks like an intermediate message
    const isIntermediate = intermediatePatterns.some(pattern => pattern.test(line)) ||
                          line.endsWith('...') ||
                          /^(✓|○|•|-) /.test(line)
    
    if (isIntermediate && resultStartIndex === -1) {
      intermediateLines.push(line)
    } else if (resultStartIndex === -1 && line.length > 20) {
      // Likely the start of result section
      resultStartIndex = i
      break
    }
  }
  
  if (intermediateLines.length > 0) {
    const actionPreparation = intermediateLines.join('\n')
    const result = resultStartIndex >= 0 ? lines.slice(resultStartIndex).join('\n') : text.trim()
    return { actionPreparation, result }
  }
  
  // If no intermediate messages found, all text is result
  return { actionPreparation: '', result: text.trim() }
}

// Map английских названий инструментов на русские
const TOOL_NAMES_RU: Record<string, string> = {
  'Search Workspace Files': 'Поиск файлов',
  'search_workspace_files': 'Поиск файлов',
  'workspace_search_files': 'Поиск файлов',
  'Open File': 'Открытие файла',
  'open_file': 'Открытие файла',
  'Find And Open File': 'Открытие файла',
  'workspace_find_and_open_file': 'Открытие файла',
  'Read Document': 'Чтение документа',
  'read_document': 'Чтение документа',
  'docs_read': 'Чтение документа',
  'Create Document': 'Создание документа',
  'create_document': 'Создание документа',
  'docs_create': 'Создание документа',
  'Update Document': 'Обновление документа',
  'update_document': 'Обновление документа',
  'docs_update': 'Обновление документа',
  'Create Spreadsheet': 'Создание таблицы',
  'create_spreadsheet': 'Создание таблицы',
  'Read Range': 'Чтение диапазона',
  'read_range': 'Чтение диапазона',
  'sheets_read_range': 'Чтение диапазона',
  'Write Range': 'Запись диапазона',
  'write_range': 'Запись диапазона',
  'sheets_write_range': 'Запись диапазона',
  'sheets_append_rows': 'Добавление строк',
  'Create Presentation': 'Создание презентации',
  'slides_create': 'Создание презентации',
  'create_presentation': 'Создание презентации',
  'Get Presentation': 'Получение презентации',
  'get_presentation': 'Получение презентации',
  'slides_get': 'Получение презентации',
  'Create Slide': 'Добавление слайда',
  'slides_create_slide': 'Добавление слайда',
  'create_slide': 'Добавление слайда',
  'Insert Slide Text': 'Вставка текста в слайд',
  'insert_slide_text': 'Вставка текста в слайд',
  'slides_insert_text': 'Вставка текста в слайд',
  'Update Slide': 'Обновление слайда',
  'update_slide': 'Обновление слайда',
  'slides_update': 'Обновление слайда',
  'gmail_search': 'Поиск писем',
  'gmail_send_email': 'Отправка письма',
}

// Нормализация текста действия: убираем многоточия, лишние пробелы, приводим к ключевым словам
function normalizeActionText(text: string): string {
  // Убираем многоточия и лишние пробелы
  let normalized = text.replace(/\.{2,}/g, '').trim()
  // Убираем пунктуацию в конце
  normalized = normalized.replace(/[.,;:!?]+$/, '')
  // Приводим к lowercase для сравнения
  normalized = normalized.toLowerCase()
  // Убираем лишние пробелы
  normalized = normalized.replace(/\s+/g, ' ')
  return normalized
}

// Извлечение ключевых слов действия (Get, Create, Insert и т.д.)
function extractActionKey(text: string): string {
  const normalized = normalizeActionText(text)
  // Ищем ключевые слова действий
  const actionKeywords = ['get', 'create', 'insert', 'update', 'read', 'write', 'search', 'open', 'find']
  for (const keyword of actionKeywords) {
    if (normalized.includes(keyword)) {
      // Извлекаем ключевое слово + следующее слово (например, "get presentation", "create slide")
      const match = normalized.match(new RegExp(`${keyword}\\s+(\\w+)`, 'i'))
      if (match) {
        return `${keyword} ${match[1]}`
      }
      return keyword
    }
  }
  return normalized
}

// Функция для замены английских названий инструментов на русские
function translateToolNames(text: string): string {
  let translated = text
  // Сначала переводим полные совпадения
  for (const [en, ru] of Object.entries(TOOL_NAMES_RU)) {
    // Заменяем как "Search Workspace Files", так и "search_workspace_files"
    const regex = new RegExp(en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    translated = translated.replace(regex, ru)
  }
  
  // Затем обрабатываем варианты с многоточиями (например, "Get Presentation...")
  // Ищем паттерны типа "Action..." и заменяем на переведённый вариант
  for (const [en, ru] of Object.entries(TOOL_NAMES_RU)) {
    // Паттерн для "Action..." или "Action ..."
    const regexWithDots = new RegExp(`(${en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\s*\\.{2,}`, 'gi')
    translated = translated.replace(regexWithDots, (match, action) => {
      // Заменяем на переведённый вариант с многоточием
      return `${ru}...`
    })
  }
  
  return translated
}

// Parse action preparation text into individual log items
function parseActionsFromText(text: string, isStreaming: boolean): Array<{ icon: string, text: string, status: 'done' | 'pending' }> {
  if (!text || !text.trim()) {
    return []
  }

  // Remove the "**Результат шага:**" marker and everything after it if present
  const resultMarker = /(\*\*Результат\s+шага:\*\*|\*\*Результат:\*\*)/i
  const markerMatch = text.match(resultMarker)
  if (markerMatch && markerMatch.index !== undefined) {
    text = text.substring(0, markerMatch.index).trim()
  }

  // Сначала разбиваем комбинированные строки (Action1... Action2...)
  // Ищем паттерны типа "Action1... Action2..." или "Action1, Action2..."
  const combinedPattern = /([A-Z][a-zA-Z\s]+?)(\.{2,}|,)\s*([A-Z][a-zA-Z\s]+?)(\.{2,}|,|$)/g
  let processedText = text
  let match
  const combinedActions: string[] = []
  
  // Извлекаем комбинированные действия
  while ((match = combinedPattern.exec(text)) !== null) {
    const action1 = match[1].trim()
    const action2 = match[3].trim()
    if (action1 && action2) {
      combinedActions.push(action1)
      combinedActions.push(action2)
      // Заменяем комбинированную строку на разделитель
      processedText = processedText.replace(match[0], `\n${action1}\n${action2}`)
    }
  }

  // Split by newlines and filter empty lines
  let lines = processedText.split('\n').filter(line => line.trim()).map(line => line.trim())
  
  // Если не нашли комбинированные через regex, пробуем разбить по многоточиям
  if (lines.length === 1 && text.includes('...')) {
    // Разбиваем по паттерну "Action1... Action2..." (без запятых)
    const dotSeparated = text.split(/(?<=\.{2,})\s+(?=[A-Z])/).filter(s => s.trim())
    if (dotSeparated.length > 1) {
      lines = dotSeparated.map(s => s.trim())
    }
  }
  
  if (lines.length === 0) {
    return []
  }
  
  // Переводим все строки
  const translatedLines = lines.map(line => translateToolNames(line))
  
  // Улучшенная дедупликация: используем ключи действий для сравнения
  const seenActionKeys = new Set<string>()
  const uniqueLines: string[] = []
  
  for (const line of translatedLines) {
    // Убираем маркеры списков
    const cleanLine = line.replace(/^[\s]*[•\-\*\d+\.\)]\s+/, '').trim()
    if (!cleanLine) continue
    
    // Извлекаем ключ действия для сравнения
    const actionKey = extractActionKey(cleanLine)
    
    // Также нормализуем для дополнительной проверки
    const normalized = normalizeActionText(cleanLine)
    
    // Проверяем по ключу действия (более строгое сравнение)
    if (!seenActionKeys.has(actionKey) && !seenActionKeys.has(normalized)) {
      seenActionKeys.add(actionKey)
      seenActionKeys.add(normalized)
      uniqueLines.push(cleanLine)
    }
  }
  
  // Если нет уникальных строк после обработки, возвращаем пустой массив
  if (uniqueLines.length === 0) {
    return []
  }
  
  // Check if it's a list format (bullet points, numbered, or dashes)
  const listPattern = /^[\s]*[•\-\*\d+\.\)]\s+(.+)$/
  const isListFormat = uniqueLines.some(line => listPattern.test(line))
  
  if (isListFormat) {
    // Parse as list items
    return uniqueLines.map((line, index) => {
      const match = line.match(listPattern)
      const actionText = match ? match[1] : line
      
      // Check if line indicates completion (contains checkmark or "готово", "выполнено", "готово")
      const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(actionText)
      
      return {
        icon: isDone ? '✓' : '○',
        text: actionText,
        status: isDone ? 'done' as const : (index === uniqueLines.length - 1 && isStreaming ? 'pending' as const : 'done' as const)
      }
    })
  }
  
  // Если не список, обрабатываем каждую строку отдельно
  // Для каждой строки проверяем, является ли она комбинированной
  const result: Array<{ icon: string, text: string, status: 'done' | 'pending' }> = []
  
  for (let i = 0; i < uniqueLines.length; i++) {
    const line = uniqueLines[i]
    const isLast = i === uniqueLines.length - 1
    
    // Проверяем, заканчивается ли строка на многоточие (в процессе)
    const hasDots = line.endsWith('...')
    const trimmed = hasDots ? line.slice(0, -3).trim() : line.trim()
    
    // Проверяем завершённость
    const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(trimmed) || (!hasDots && !isStreaming)
    
    result.push({
      icon: isDone ? '✓' : '○',
      text: trimmed,
      status: (isDone || (!isLast && !hasDots)) ? 'done' as const : (isStreaming ? 'pending' as const : 'done' as const)
    })
  }
  
  return result
}

export function StepProgress({ workflowId }: StepProgressProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan
  const addTab = useWorkspaceStore((state) => state.addTab)
  
  // Храним предыдущее состояние действий для каждого шага
  const previousActionsRef = React.useRef<Record<number, Array<{ icon: string, text: string, status: 'done' | 'pending' }>>>({})

  // Only show component when there's a plan (workflow exists)
  if (!workflowPlan || !workflowPlan.steps || workflowPlan.steps.length === 0) {
    return null
  }

  const planSteps = workflowPlan.steps // Array of step titles (strings)
  const workflowSteps = workflow?.steps || {} // Record<number, WorkflowStep>

  // If we have no workflow steps yet and no final result, don't show anything
  // (plan is shown in PlanBlock, steps will appear when execution starts)
  const hasAnyStepData = Object.keys(workflowSteps).length > 0
  const hasFinalResult = workflow?.finalResult

  if (!hasAnyStepData && !hasFinalResult) {
    return null
  }
  
  // Функция для обновления действий с учётом предыдущего состояния
  const getUpdatedActions = React.useCallback((stepNumber: number, newActions: Array<{ icon: string, text: string, status: 'done' | 'pending' }>): Array<{ icon: string, text: string, status: 'done' | 'pending' }> => {
    const previousActions = previousActionsRef.current[stepNumber] || []
    
    if (previousActions.length === 0) {
      // Первый раз - просто сохраняем
      previousActionsRef.current[stepNumber] = [...newActions]
      return newActions
    }
    
    // Создаём мапу предыдущих действий по ключу (нормализованный текст)
    const previousMap = new Map<string, { icon: string, text: string, status: 'done' | 'pending', index: number }>()
    previousActions.forEach((action, index) => {
      const key = extractActionKey(action.text)
      previousMap.set(key, { ...action, index })
    })
    
    const result: Array<{ icon: string, text: string, status: 'done' | 'pending' }> = []
    const processedKeys = new Set<string>()
    
    // Обрабатываем новые действия
    for (const newAction of newActions) {
      const key = extractActionKey(newAction.text)
      
      if (processedKeys.has(key)) {
        continue // Пропускаем дубликаты
      }
      
      processedKeys.add(key)
      
      const previousAction = previousMap.get(key)
      
      if (previousAction) {
        // Обновляем существующее действие
        // Если статус изменился с pending на done, обновляем
        if (previousAction.status === 'pending' && newAction.status === 'done') {
          result.push(newAction)
        } else if (previousAction.status === 'pending' && newAction.status === 'pending') {
          // Обновляем текст, но сохраняем pending
          result.push({ ...newAction, text: newAction.text })
        } else {
          // Сохраняем предыдущее состояние, если оно done
          result.push(previousAction)
        }
      } else {
        // Новое действие - добавляем
        result.push(newAction)
      }
    }
    
    // Сохраняем обновлённое состояние
    previousActionsRef.current[stepNumber] = [...result]
    return result
  }, [])

  return (
    <div style={{ 
      maxWidth: '900px', 
      width: '100%', 
      margin: '0 auto',
      /* Добавляем padding-top чтобы шаги не прилипали к sticky-секции */
      paddingTop: '8px'
    }}>
      {/* Render each step */}
      {planSteps.map((stepTitle, index) => {
        const stepNumber = index + 1
        const stepData: WorkflowStep | undefined = workflowSteps[stepNumber]

        // If step hasn't started yet, show as pending
        const status = stepData?.status || 'pending'
        const thinking = stepData?.thinking || ''
        const response = stepData?.response || ''
        const isStepStreaming = status === 'in_progress'
        
        // Parse response into action preparation and result
        const { actionPreparation, result } = parseStepResponse(response)

        // Parse actions for log
        const rawActions = parseActionsFromText(actionPreparation, isStepStreaming)
        
        // Обновляем действия с учётом предыдущего состояния (обновление вместо добавления)
        const actions = getUpdatedActions(stepNumber, rawActions)

        return (
          <div key={stepNumber} style={{ marginBottom: '12px' }}>
            {/* Блок ризонинга шага */}
            {thinking && thinking.trim() && (
              <CollapsibleBlock
                title="думаю..."
                icon={<Brain className="reasoning-block-icon" />}
                isStreaming={isStepStreaming}
                isCollapsed={true}
                autoCollapse={true}
              >
                {thinking}
              </CollapsibleBlock>
            )}

            {/* Компактный лог действий */}
            {(actions.length > 0 || (isStepStreaming && !result && !thinking)) && (
              <div className="execution-log" style={{ 
                maxWidth: '900px',
                width: '100%',
                marginLeft: 'auto',
                marginRight: 'auto',
                paddingLeft: '14px',
                paddingRight: '14px'
              }}>
                {actions.map((action, actionIndex) => (
                  <div key={actionIndex} className="execution-log-item">
                    <span className={`log-icon ${action.status}`}>{action.icon}</span>
                    <span className="log-text">{action.text}</span>
                  </div>
                ))}
                {isStepStreaming && !result && actions.length === 0 && (
                  <div className="execution-log-item">
                    <span className="log-icon pending">○</span>
                    <span className="log-text">Выполняю действия...</span>
                  </div>
                )}
              </div>
            )}

            {/* File Preview Card */}
            {stepData?.filePreview && (
              <div style={{ 
                maxWidth: '900px',
                width: '100%',
                marginTop: '12px',
                marginLeft: 'auto',
                marginRight: 'auto',
                paddingLeft: '14px',
                paddingRight: '14px'
              }}>
                <FilePreviewCard
                  type={stepData.filePreview.type}
                  title={stepData.filePreview.title}
                  subtitle={stepData.filePreview.subtitle}
                  previewData={stepData.filePreview.previewData}
                  fileId={stepData.filePreview.fileId}
                  fileUrl={stepData.filePreview.fileUrl}
                  onOpenInPanel={() => {
                    const preview = stepData.filePreview!
                    addTab({
                      type: preview.type,
                      title: preview.title,
                      url: preview.fileUrl,
                      data: preview.type === 'sheets' ? { spreadsheetId: preview.fileId } :
                            preview.type === 'docs' ? { documentId: preview.fileId } :
                            preview.type === 'slides' ? { presentationId: preview.fileId } :
                            preview.type === 'code' ? preview.previewData :
                            preview.type === 'email' ? preview.previewData :
                            preview.type === 'chart' ? preview.previewData :
                            {},
                      closeable: true
                    })
                  }}
                />
              </div>
            )}

            {/* Результат шага - просто текст без рамок и фона, с маркдауном */}
            {result && result.trim() && (
              <div style={{ 
                maxWidth: '900px',
                width: '100%',
                marginTop: '12px',
                marginLeft: 'auto',
                marginRight: 'auto',
                paddingLeft: '14px',
                paddingRight: '14px'
              }}>
                <div className="prose max-w-none 
                  prose-p:text-gray-900 
                  prose-p:leading-6 prose-p:my-3 prose-p:text-[13px]
                  prose-h1:text-gray-900 prose-h1:text-[20px] prose-h1:font-semibold prose-h1:mb-3 prose-h1:mt-6 prose-h1:first:mt-0 prose-h1:leading-tight
                  prose-h2:text-gray-900 prose-h2:text-[18px] prose-h2:font-semibold prose-h2:mb-2 prose-h2:mt-5 prose-h2:leading-tight
                  prose-h3:text-gray-900 prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mb-2 prose-h3:mt-4 prose-h3:leading-tight
                  prose-strong:text-gray-900 prose-strong:font-semibold
                  prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:border prose-code:border-gray-200
                  prose-pre:bg-gray-100 prose-pre:text-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:text-[13px] prose-pre:rounded-lg prose-pre:p-4
                  prose-ul:text-gray-900 prose-ul:my-3 prose-ul:pl-8
                  prose-ol:text-gray-900 prose-ol:my-3 prose-ol:pl-8
                  prose-li:text-gray-900 prose-li:my-1.5 prose-li:text-[13px]
                  prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-700
                  prose-blockquote:text-gray-600 prose-blockquote:border-l-gray-300 prose-blockquote:pl-4 prose-blockquote:my-3
                  prose-table:w-full prose-table:border-collapse prose-table:my-4
                  prose-th:border prose-th:border-gray-300 prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold
                  prose-td:border prose-td:border-gray-300 prose-td:px-3 prose-td:py-2
                  prose-tr:hover:bg-gray-50">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* Show placeholder when step is in progress but no content yet */}
            {status === 'in_progress' && !thinking && !response && (
              <div style={{ fontSize: '14px', color: '#6c757d', fontStyle: 'italic', maxWidth: '900px', width: '100%', marginLeft: 'auto', marginRight: 'auto', paddingLeft: '14px', paddingRight: '14px' }}>
                Выполнение шага...
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
