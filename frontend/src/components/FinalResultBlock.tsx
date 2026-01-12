import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

interface FinalResultBlockProps {
  content: string
}

/**
 * Преобразует plain text URL в markdown ссылки
 */
function convertUrlsToLinks(text: string): string {
  try {
    // Сначала исправляем формат [текст] (url) на [текст](url) (убираем пробел)
    let processedText = text.replace(/\]\s*\(/g, '](')
    
    // Регулярное выражение для поиска URL (http, https)
    // Захватываем URL до пробела, новой строки, или знаков препинания (кроме тех, что могут быть в URL)
    const urlRegex = /(https?:\/\/[^\s\n<>"']+?)(?=[\s\n<>"'.,;:!?)]|$)/g
    
    const result = processedText.replace(urlRegex, (...args) => {
      // В String.replace() параметры: (match, p1, p2, ..., offset, string)
      // Последние два параметра всегда offset и string
      const match = args[0] // полное совпадение
      const offset = args[args.length - 2] // предпоследний параметр
      const fullText = args[args.length - 1] // последний параметр
      
      // Проверяем контекст вокруг URL
      const before = fullText.substring(Math.max(0, offset - 10), offset)
      const after = fullText.substring(offset + match.length, Math.min(fullText.length, offset + match.length + 10))
      
      // Если URL уже в markdown формате [text](url), не трогаем
      if (before.includes('](') || after.startsWith(')')) {
        return match
      }
      
      // Преобразуем plain text URL в markdown ссылку
      return `[${match}](${match})`
    })
    
    return result
  } catch (error) {
    // В случае ошибки возвращаем исходный текст
    return text
  }
}

export function FinalResultBlock({ content }: FinalResultBlockProps) {
  if (!content || content.trim().length === 0) {
    return null
  }

  // Преобразуем plain text URL в markdown ссылки
  const processedContent = convertUrlsToLinks(content)

  // Кастомные компоненты для ReactMarkdown
  const components: Components = {
    a: ({ node, href, children, ...props }) => {
      // Открываем все ссылки в новой вкладке
      // Стили применяются через CSS класс .final-result-prose a
      return (
        <a
          href={href || '#'}
          target="_blank"
          rel="noopener noreferrer"
          {...props}
        >
          {children}
        </a>
      )
    },
  }

  return (
    <div style={{ 
      maxWidth: '900px',
      width: '100%',
      margin: '0 auto',
      marginTop: '24px',
      paddingTop: '0',
      paddingBottom: '0',
      paddingLeft: '14px',
      paddingRight: '14px',
      borderTop: 'none'
    }}>
      {/* Заголовок результата */}
      <div className="final-result-header">
        Результат
      </div>
      
      <div className="prose max-w-none final-result-prose"
        style={{ padding: '0', fontSize: '13px', marginTop: '12px' }}>
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={components}
        >
          {processedContent}
        </ReactMarkdown>
      </div>
    </div>
  )
}
