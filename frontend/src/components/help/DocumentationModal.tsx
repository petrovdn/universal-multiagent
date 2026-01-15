import { useEffect, useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface DocumentationModalProps {
  isOpen: boolean
  onClose: () => void
}

// Кэш для контента
const contentCache = new Map<string, string>()

export function DocumentationModal({ isOpen, onClose }: DocumentationModalProps) {
  const [content, setContent] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      
      const cacheKey = 'USER_GUIDE.md'
      
      // Проверяем кэш - если есть, показываем сразу
      if (contentCache.has(cacheKey)) {
        setContent(contentCache.get(cacheKey)!)
        setIsLoading(false)
        return
      }

      // Если контент уже загружен, показываем его
      if (content) {
        setIsLoading(false)
        return
      }

      // Загружаем контент постепенно
      setIsLoading(true)
      setContent('') // Начинаем с пустого контента
      
      abortControllerRef.current = new AbortController()
      
      fetch('/docs/USER_GUIDE.md', { signal: abortControllerRef.current.signal })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.text()
        })
        .then((text) => {
          // Сохраняем в кэш
          contentCache.set(cacheKey, text)
          
          // Показываем контент постепенно (по частям)
          const chunkSize = 1000 // Символов за раз
          let currentIndex = 0
          
          const showChunk = () => {
            if (currentIndex < text.length) {
              const chunk = text.slice(0, currentIndex + chunkSize)
              setContent(chunk)
              currentIndex += chunkSize
              
              // Используем requestAnimationFrame для плавной прокрутки
              requestAnimationFrame(() => {
                setTimeout(showChunk, 10) // 10ms задержка между чанками
              })
            } else {
              setContent(text) // Финальный контент
              setIsLoading(false)
            }
          }
          
          showChunk()
        })
        .catch((err) => {
          if (err.name === 'AbortError') return
          console.error('Failed to load documentation:', err)
          setContent('# Ошибка загрузки документации\n\nНе удалось загрузить документацию.')
          setIsLoading(false)
        })
    } else {
      // Отменяем загрузку при закрытии
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
    }
    
    return () => {
      if (isOpen) {
        document.body.style.overflow = ''
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [isOpen, content])

  // Модальное окно показывается сразу, даже если контент еще загружается
  if (!isOpen) return null

  // Рендерим через Portal напрямую в body, чтобы избежать stacking context проблем
  return createPortal(
    <div className="documentation-modal-overlay" onClick={onClose}>
      <div className="documentation-modal" onClick={(e) => e.stopPropagation()}>
        <div className="documentation-modal-header">
          <h2 className="documentation-modal-title">Документация</h2>
          <button
            className="documentation-modal-close"
            onClick={onClose}
            title="Закрыть"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="documentation-modal-content">
          {isLoading && content.length === 0 ? (
            <div className="documentation-loading">Загрузка документации...</div>
          ) : (
            <>
              {isLoading && (
                <div className="documentation-loading" style={{ position: 'sticky', top: 0, background: 'var(--bg-primary)', padding: '8px 0', zIndex: 10 }}>
                  Загрузка...
                </div>
              )}
              <ReactMarkdown 
                className="documentation-markdown"
                remarkPlugins={[remarkGfm]}
              >
                {content}
              </ReactMarkdown>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
