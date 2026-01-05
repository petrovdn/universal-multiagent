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
  'Create Slide': 'Добавление слайда',
  'slides_create_slide': 'Добавление слайда',
  'gmail_search': 'Поиск писем',
  'gmail_send_email': 'Отправка письма',
}

// Функция для замены английских названий инструментов на русские
function translateToolNames(text: string): string {
  let translated = text
  for (const [en, ru] of Object.entries(TOOL_NAMES_RU)) {
    // Заменяем как "Search Workspace Files", так и "search_workspace_files"
    const regex = new RegExp(en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    translated = translated.replace(regex, ru)
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

  // Split by newlines and filter empty lines
  const lines = text.split('\n').filter(line => line.trim()).map(line => line.trim())
  
  if (lines.length === 0) {
    return []
  }
  
  // Дедупликация: убираем повторяющиеся строки (нормализуем для сравнения)
  // Сначала переводим все строки, потом фильтруем дубликаты по нормализованным версиям
  const translatedLines = lines.map(line => translateToolNames(line))
  const seenTexts = new Set<string>()
  const uniqueLines = translatedLines.filter(line => {
    // Нормализуем строку: убираем маркеры списков и лишние пробелы
    const normalized = line.replace(/^[\s]*[•\-\*\d+\.\)]\s+/, '').trim().toLowerCase()
    if (seenTexts.has(normalized)) {
      return false
    }
    seenTexts.add(normalized)
    return true
  })
  
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
  
  // If not a list, split by sentences or lines
  // First try splitting by sentences (ending with . ! ?)
  const sentences = text.split(/(?<=[.!?])\s+/).filter(s => s.trim())
  
  if (sentences.length > 1) {
    return sentences.map((sentence, index) => {
      const trimmed = sentence.trim()
      // Check if sentence indicates completion
      const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(trimmed) || 
                     (index < sentences.length - 1) // Previous sentences are done
      
      return {
        icon: isDone ? '✓' : '○',
        text: trimmed,
        status: isDone ? 'done' as const : (index === sentences.length - 1 && isStreaming ? 'pending' as const : 'done' as const)
      }
    })
  }
  
  // If single line, try splitting by common separators (..., then, после чего)
  const separators = /(\.\.\.|\.\.|, затем|, потом|, после чего|, далее)/i
  if (separators.test(text)) {
    const parts = text.split(separators).filter(p => p.trim() && !separators.test(p.trim()))
    if (parts.length > 1) {
      return parts.map((part, index) => ({
        icon: index < parts.length - 1 ? '✓' : (isStreaming ? '○' : '✓'),
        text: part.trim(),
        status: index < parts.length - 1 ? 'done' as const : (isStreaming ? 'pending' as const : 'done' as const)
      }))
    }
  }
  
  // Single action - check if it ends with "..." (in progress) or indicates completion
  const trimmed = text.trim()
  const isInProgress = trimmed.endsWith('...') || isStreaming
  const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(trimmed) || !isInProgress
  
  return [{
    icon: isDone ? '✓' : '○',
    text: trimmed,
    status: isDone ? 'done' as const : 'pending' as const
  }]
}

export function StepProgress({ workflowId }: StepProgressProps) {
  // Get workflow by ID from store
  const workflow = useChatStore((state) => state.workflows[workflowId])
  const workflowPlan = workflow?.plan
  const addTab = useWorkspaceStore((state) => state.addTab)

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
        const actions = parseActionsFromText(actionPreparation, isStepStreaming)

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
