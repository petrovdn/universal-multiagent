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
  // Также распознаём английские заголовки действий
  const intermediatePatterns = [
    /^(Открываю|Ищу|Читаю|Анализирую|Создаю|Добавляю|Применяю|Перемещаю|Формулирую|Готовлю|Выполняю|Проверяю|Нашел|Нашла|Прочитал|Прочитала|Создал|Создала|Добавил|Добавила|Применил|Применила)[^.!?]*[.!?]?/im,
    /^(Create|Get|Insert|Update|Read|Write|Search|Open|Find|Append)\s+[A-Z][^.!?]*[.!?]?/im, // English action headers
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
  'Create Presentation': 'Создаю презентацию',
  'slides_create': 'Создаю презентацию',
  'create_presentation': 'Создаю презентацию',
  'Create Presentation From Doc': 'Создаю презентацию из документа',
  'create_presentation_from_doc': 'Создаю презентацию из документа',
  'Get Presentation': 'Получаю презентацию',
  'get_presentation': 'Получаю презентацию',
  'slides_get': 'Получаю презентацию',
  'Create Slide': 'Создаю слайд',
  'slides_create_slide': 'Создаю слайд',
  'create_slide': 'Создаю слайд',
  'Insert Slide Text': 'Вставляю текст в слайд',
  'insert_slide_text': 'Вставляю текст в слайд',
  'slides_insert_text': 'Вставляю текст в слайд',
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

// Проверка, является ли текст английским (не переведённым)
function isEnglishText(text: string): boolean {
  const trimmed = text.trim()
  
  // Проверяем английские ключевые слова действий в начале строки (с заглавной буквы)
  const startsWithEnglishAction = /^(Get|Create|Insert|Update|Read|Write|Search|Open|Find|Append)\s+[A-Z]/
  if (startsWithEnglishAction.test(trimmed)) {
    return true
  }
  
  // Проверяем паттерны типа "Create Presentation From Doc", "Create Presentation '...'"
  const englishPatterns = [
    /^Create\s+Presentation/i,
    /^Create\s+Slide/i,
    /^Get\s+Presentation/i,
    /^Insert\s+Slide/i,
    /^Update\s+Slide/i,
    /^Read\s+Document/i,
    /^Create\s+Document/i,
    /^Update\s+Document/i,
    /^Read\s+Range/i,
    /^Write\s+Range/i,
    /^Search\s+Workspace/i,
    /^Open\s+File/i,
    /^Find\s+File/i,
  ]
  
  for (const pattern of englishPatterns) {
    if (pattern.test(trimmed)) {
      return true
    }
  }
  
  // Проверяем, содержит ли текст английские фразы действий (после нормализации)
  const normalized = normalizeActionText(text)
  const englishActionPhrases = [
    'create presentation', 'create slide', 'get presentation', 'insert slide', 'update slide',
    'read document', 'create document', 'update document', 'read range', 'write range',
    'search workspace', 'open file', 'find file', 'create presentation from'
  ]
  
  for (const phrase of englishActionPhrases) {
    if (normalized.includes(phrase)) {
      return true
    }
  }
  
  return false
}

// Функция для замены английских названий инструментов на русские
function translateToolNames(text: string): string {
  let translated = text
  const originalText = text
  
  // Сначала переводим сложные паттерны типа "Create Presentation '...'..." или "Create Slide... Insert Slide Text..."
  // Паттерн для "Create Presentation 'название'..." -> "Создаю презентацию 'название'..."
  translated = translated.replace(/Create\s+Presentation\s+From\s+Doc/gi, 'Создаю презентацию из документа')
  translated = translated.replace(/Create\s+Presentation\s+['"]([^'"]+)['"]\s*\.{0,3}/gi, (match, name) => {
    const result = `Создаю презентацию '${name}'`
    return result
  })
  translated = translated.replace(/Create\s+Presentation/gi, 'Создаю презентацию')
  translated = translated.replace(/Get\s+Presentation/gi, 'Получаю презентацию')
  // "Create Slide 'название'..." -> "Создаю слайд 'название'"
  translated = translated.replace(/Create\s+Slide\s+['"]([^'"]+)['"]\s*\.{0,3}/gi, (match, name) => {
    const result = `Создаю слайд "${name}"`
    return result
  })
  translated = translated.replace(/Create\s+Slide/gi, 'Создаю слайд')
  translated = translated.replace(/Insert\s+Slide\s+Text/gi, 'Вставляю текст в слайд')
  translated = translated.replace(/Update\s+Slide/gi, 'Обновляю слайд')
  translated = translated.replace(/Read\s+Document/gi, 'Читаю документ')
  translated = translated.replace(/Create\s+Document/gi, 'Создаю документ')
  translated = translated.replace(/Update\s+Document/gi, 'Обновляю документ')
  
  // Затем переводим полные совпадения из словаря
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
  
  if (originalText !== translated) {
  }
  
  return translated
}

// Извлечение деталей действия (название слайда, текст и т.д.)
function extractActionDetails(actionText: string, fullText?: string): { title: string, details?: string, hasText?: boolean, textContent?: string } {
  
  // Паттерны для извлечения деталей
  // "Создаю слайд 'Введение'" -> title: "Создаю слайд", details: "Введение"
  // "Создаю слайд "Завязка истории"" -> title: "Создаю слайд", details: "Завязка истории"
  // Также поддерживаем варианты без кавычек, если название идет после действия
  const slideTitlePatterns = [
    /(?:Создаю|Добавляю)\s+слайд\s+["']([^"']+)["']/i,
    /(?:Создаю|Добавляю)\s+слайд\s+["']([^"']+)["']\s*\.{0,3}/i,
  ]
  
  for (const pattern of slideTitlePatterns) {
    const match = actionText.match(pattern)
    if (match && match[1]) {
      const slideName = match[1]
      // Убираем название слайда из текста действия
      const title = actionText.replace(pattern, (m) => {
        return m.replace(`"${slideName}"`, '').replace(`'${slideName}'`, '').replace(/\.{2,}/g, '').trim()
      }).trim()
      
      
      return {
        title: title || 'Создаю слайд',
        details: slideName
      }
    }
  }
  
  // Если в actionText есть "Создаю слайд" без названия, но в fullText может быть название
  // Ищем паттерны типа "Создаю слайд" и пытаемся найти название во всем response
  if (/^(?:Создаю|Добавляю)\s+слайд/i.test(actionText)) {
    // Сначала ищем в самом actionText (может быть "Создаю слайд 'название'")
    const inlineMatch = actionText.match(/(?:Создаю|Добавляю)\s+слайд\s+["']([^"']{3,100})["']/i)
    if (inlineMatch && inlineMatch[1]) {
      const slideName = inlineMatch[1]
      return {
        title: actionText.replace(/["']([^"']+)["']/, '').replace(/\.{2,}/g, '').trim(),
        details: slideName
      }
    }
    
    // Если fullText есть, ищем в нем
    if (fullText) {
      const lines = fullText.split('\n')
      // Сначала ищем в секции результата (после маркера "**Результат шага:**")
      const resultMarker = /(\*\*Результат\s+шага:\*\*|\*\*Результат:\*\*)/i
      const markerMatch = fullText.match(resultMarker)
      const searchStartIndex = markerMatch && markerMatch.index !== undefined ? markerMatch.index : 0
      
      // Ищем название слайда в кавычках во всем response, начиная с секции результата
      // Паттерны для поиска: "Завязка истории", 'Завязка истории', "Основной сюжет и приключения"
      const slideNamePatterns = [
        /["']([^"']{3,50})["']/g, // Название в кавычках (от 3 до 50 символов)
      ]
      
      for (const pattern of slideNamePatterns) {
        let match
        // Ищем все совпадения в response, начиная с секции результата
        while ((match = pattern.exec(fullText.substring(searchStartIndex))) !== null) {
          const slideName = match[1]
          // Проверяем, что это не часть другого текста (не слишком длинное, не содержит специальных символов)
          if (slideName.length >= 3 && slideName.length <= 100 && 
              !slideName.match(/^(Create|Insert|Update|Get|Read|Write|Search|Open|Find|Append)/i) &&
              !slideName.match(/^(Создаю|Добавляю|Вставляю|Готово|Выполнено)/i) &&
              !slideName.match(/\.{2,}$/)) {
            return {
              title: actionText.replace(/\.{2,}/g, '').trim(),
              details: slideName
            }
          }
        }
      }
      
      // Если не нашли в секции результата, ищем в следующих строках после действия
      const actionIndex = lines.findIndex(l => l.includes(actionText) || actionText.includes(l.trim()))
      if (actionIndex >= 0) {
        // Ищем название слайда в следующих строках
        for (let i = actionIndex + 1; i < Math.min(actionIndex + 10, lines.length); i++) {
          const line = lines[i].trim()
          // Ищем паттерн с названием в кавычках
          const nameMatch = line.match(/["']([^"']{3,100})["']/)
          if (nameMatch && nameMatch[1].length >= 3 && nameMatch[1].length < 100 &&
              !nameMatch[1].match(/^(Create|Insert|Update|Get|Read|Write|Search|Open|Find|Append)/i) &&
              !nameMatch[1].match(/^(Создаю|Добавляю|Вставляю|Готово|Выполнено)/i)) {
            return {
              title: actionText.replace(/\.{2,}/g, '').trim(),
              details: nameMatch[1]
            }
          }
        }
      }
    }
  }
  
  // "Вставляю текст в слайд..." или "Вставка текста в слайд..." -> может содержать текст
  const textActionPattern = /(?:Вставляю|Добавляю)\s+(?:текст|текста)\s+(?:в\s+слайд|в\s+слайды)/i
  if (textActionPattern.test(actionText)) {
    // Если есть полный текст, пытаемся извлечь текст из него
    let textContent: string | undefined
    if (fullText) {
      // Ищем текст после маркера результата
      const resultMarker = /(\*\*Результат\s+шага:\*\*|\*\*Результат:\*\*)/i
      const markerMatch = fullText.match(resultMarker)
      if (markerMatch && markerMatch.index !== undefined) {
        const resultText = fullText.substring(markerMatch.index + markerMatch[0].length).trim()
        // Убираем маркеры действий и оставляем только текст
        const cleanedText = resultText
          .split('\n')
          .filter(line => {
            const trimmed = line.trim()
            // Пропускаем пустые строки, маркеры действий и короткие строки
            return trimmed.length > 10 && 
                   !trimmed.match(/^(✓|○|•|-|\d+\.)/) && 
                   !trimmed.match(/^(Создаю|Добавляю|Вставляю|Готово|Выполнено|Create|Add|Insert)/i) &&
                   !trimmed.match(/\.{2,}$/) &&
                   !trimmed.match(/^\*\*/)
          })
          .join('\n')
          .trim()
        
        if (cleanedText.length > 20) {
          textContent = cleanedText
          // Не ограничиваем длину слишком сильно - пусть скроллится
          if (textContent.length > 5000) {
            textContent = textContent.substring(0, 5000) + '...'
          }
        }
      } else {
        // Берем последние строки как текст (если они достаточно длинные)
        const lines = fullText.split('\n').filter(l => l.trim())
        // Ищем блок текста в конце (обычно это содержимое, которое вставляется)
        let foundText = ''
        for (let i = lines.length - 1; i >= 0 && i >= lines.length - 15; i--) {
          const line = lines[i].trim()
          // Пропускаем маркеры, короткие строки и действия
          if (line.length > 20 && 
              !line.match(/^(✓|○|•|-|\d+\.)/) && 
              !line.match(/^(Создаю|Добавляю|Вставляю|Готово|Выполнено|Create|Add|Insert)/i) &&
              !line.match(/\.{2,}$/) &&
              !line.match(/^\*\*/)) {
            foundText = line + (foundText ? '\n' + foundText : '')
          }
        }
        if (foundText.length > 30) {
          textContent = foundText
          if (textContent.length > 5000) {
            textContent = textContent.substring(0, 5000) + '...'
          }
        }
      }
    }
    
    return {
      title: actionText.replace(/\.{2,}/g, '').trim(),
      hasText: true,
      textContent
    }
  }
  
  return { title: actionText.replace(/\.{2,}/g, '').trim() }
}

// Parse action preparation text into individual log items
function parseActionsFromText(text: string, isStreaming: boolean, fullResponse?: string): Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean }> {
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
  
  // Переводим все строки и сохраняем соответствие оригинал -> перевод
  const translatedLines = lines.map(line => {
    const translated = translateToolNames(line)
    return {
      original: line,
      translated: translated
    }
  })
  
  // Улучшенная дедупликация: используем ключи действий для сравнения
  const seenActionKeys = new Set<string>()
  const uniqueLines: Array<{ original: string, translated: string }> = []
  
  for (const { original, translated } of translatedLines) {
    // Убираем маркеры списков
    const cleanTranslated = translated.replace(/^[\s]*[•\-\*\d+\.\)]\s+/, '').trim()
    if (!cleanTranslated) continue
    
    // Извлекаем ключ действия для сравнения (из переведённой версии)
    const actionKey = extractActionKey(cleanTranslated)
    
    // Также нормализуем для дополнительной проверки
    const normalized = normalizeActionText(cleanTranslated)
    
    // Проверяем по ключу действия (более строгое сравнение)
    if (!seenActionKeys.has(actionKey) && !seenActionKeys.has(normalized)) {
      seenActionKeys.add(actionKey)
      seenActionKeys.add(normalized)
      uniqueLines.push({ original, translated: cleanTranslated })
    }
  }
  
  // Если нет уникальных строк после обработки, возвращаем пустой массив
  if (uniqueLines.length === 0) {
    return []
  }
  
  // Фильтруем: убираем строки на английском (не переведённые)
  // Проверяем и оригинал, и перевод - если перевод всё ещё содержит английские паттерны, значит он не переведён
  const translatedOnlyLines = uniqueLines
    .filter(({ original, translated }) => {
      // Если оригинал английский И перевод тоже английский (не изменился), фильтруем
      const isOriginalEnglish = isEnglishText(original)
      const isTranslatedEnglish = isEnglishText(translated)
      // Если оба английские, значит перевод не сработал - фильтруем
      if (isOriginalEnglish && isTranslatedEnglish) {
        return false
      }
      
      // Если оригинал английский, но перевод русский - оставляем (перевод сработал)
      // Если оригинал русский - оставляем
      return true
    })
    .map(({ translated }) => translated)
  if (translatedOnlyLines.length === 0) {
    return []
  }
  
  // Check if it's a list format (bullet points, numbered, or dashes)
  const listPattern = /^[\s]*[•\-\*\d+\.\)]\s+(.+)$/
  const isListFormat = translatedOnlyLines.some(line => listPattern.test(line))
  
  if (isListFormat) {
    // Parse as list items
    return translatedOnlyLines.map((line, index) => {
      const match = line.match(listPattern)
      const actionText = match ? match[1] : line
      
      // Check if line indicates completion (contains checkmark or "готово", "выполнено", "готово")
      const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(actionText)
      
      // Извлекаем детали действия
      const details = extractActionDetails(actionText, fullResponse)
      
      return {
        icon: isDone ? '✓' : '○',
        text: details.title,
        status: isDone ? 'done' as const : (index === translatedOnlyLines.length - 1 && isStreaming ? 'pending' as const : 'done' as const),
        details: details.textContent || details.details, // textContent для текста, details для названия слайда
        hasText: details.hasText
      }
    })
  }
  
  // Если не список, обрабатываем каждую строку отдельно
  // Для каждой строки проверяем, является ли она комбинированной
  const result: Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean }> = []
  
  for (let i = 0; i < translatedOnlyLines.length; i++) {
    const line = translatedOnlyLines[i]
    const isLast = i === translatedOnlyLines.length - 1
    
    // Проверяем, заканчивается ли строка на многоточие (в процессе)
    const hasDots = line.endsWith('...')
    const trimmed = hasDots ? line.slice(0, -3).trim() : line.trim()
    
    // Проверяем завершённость
    const isDone = /✓|готово|выполнено|завершено|done|готово:/i.test(trimmed) || (!hasDots && !isStreaming)
    
    // Извлекаем детали действия
    const actionDetails = extractActionDetails(trimmed, fullResponse)
    
    result.push({
      icon: isDone ? '✓' : '○',
      text: actionDetails.title,
      status: (isDone || (!isLast && !hasDots)) ? 'done' as const : (isStreaming ? 'pending' as const : 'done' as const),
      details: actionDetails.textContent || actionDetails.details, // textContent для текста, details для названия слайда
      hasText: actionDetails.hasText
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
  const previousActionsRef = React.useRef<Record<number, Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean }>>>({})

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
  const getUpdatedActions = React.useCallback((stepNumber: number, newActions: Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean }>): Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean }> => {
    const previousActions = previousActionsRef.current[stepNumber] || []
    if (previousActions.length === 0) {
      // Первый раз - просто сохраняем
      previousActionsRef.current[stepNumber] = [...newActions]
      return newActions
    }
    
    // Создаём мапу предыдущих действий по ключу (нормализованный текст)
    const previousMap = new Map<string, { icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean, textContent?: string, index: number }>()
    previousActions.forEach((action, index) => {
      const key = extractActionKey(action.text)
      previousMap.set(key, { ...action, index })
    })
    
    const result: Array<{ icon: string, text: string, status: 'done' | 'pending', details?: string, hasText?: boolean, textContent?: string }> = []
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

  // Вычисляем прогресс выполнения
  const totalSteps = planSteps.length
  const completedSteps = Object.values(workflowSteps).filter(
    step => step.status === 'completed'
  ).length
  const inProgressStep = Object.values(workflowSteps).find(
    step => step.status === 'in_progress'
  )
  const progressPercentage = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  return (
    <div style={{ 
      maxWidth: '900px', 
      width: '100%', 
      margin: '0 auto',
      /* Добавляем padding-top чтобы шаги не прилипали к sticky-секции */
      paddingTop: '8px'
    }}>
      {/* Progress Bar */}
      {totalSteps > 0 && (completedSteps > 0 || inProgressStep) && (
        <div className="step-progress-bar-container" style={{ marginBottom: '16px', padding: '0 14px' }}>
          <div className="step-progress-bar-header">
            <span className="step-progress-bar-text">
              {inProgressStep 
                ? `Шаг ${completedSteps + 1} из ${totalSteps}` 
                : `${completedSteps} из ${totalSteps} шагов выполнено`}
            </span>
            <span className="step-progress-bar-percentage">{Math.round(progressPercentage)}%</span>
          </div>
          <div className="step-progress-bar">
            <div 
              className="step-progress-bar-fill"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      )}

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
        // Parse actions for log (передаём полный response для извлечения текста и названий слайдов)
        // Если response пустой, используем actionPreparation + result как fallback
        const fullTextForExtraction = response || (actionPreparation + '\n' + result)
        const rawActions = parseActionsFromText(actionPreparation, isStepStreaming, fullTextForExtraction)
        // Обновляем действия с учётом предыдущего состояния (обновление вместо добавления)
        const actions = getUpdatedActions(stepNumber, rawActions)

        return (
          <div key={stepNumber} style={{ marginBottom: '6px' }}>
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
                {actions.map((action, actionIndex) => {
                  // Если hasText=true, то details содержит текст для вставки
                  // Если hasText=false, то details содержит название слайда
                  const isSlideTitle = !action.hasText && action.details
                  const isTextContent = action.hasText && action.details
                  
                  return (
                    <div key={actionIndex} className="execution-log-item">
                      <span className={`log-icon ${action.status}`}>{action.icon}</span>
                      <div className="log-text-container">
                        <span className="log-text-title">
                          {action.text}
                          {isSlideTitle && (
                            <span style={{ color: 'var(--text-secondary)', fontWeight: 'normal' }}>
                              {' '}"{action.details}"
                            </span>
                          )}
                        </span>
                        {isTextContent && (
                          <div className="log-text-details">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{action.details}</ReactMarkdown>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
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
