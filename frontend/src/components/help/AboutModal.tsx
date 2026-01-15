import { useEffect, useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface AboutModalProps {
  isOpen: boolean
  onClose: () => void
}

const contentCache = new Map<string, string>()

export function AboutModal({ isOpen, onClose }: AboutModalProps) {
  const [content, setContent] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
      
      const cacheKey = 'ABOUT.md'
      
      if (contentCache.has(cacheKey)) {
        setContent(contentCache.get(cacheKey)!)
        setIsLoading(false)
        return
      }

      if (content) {
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setContent('')
      
      abortControllerRef.current = new AbortController()
      
      fetch('/docs/ABOUT.md', { signal: abortControllerRef.current.signal })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.text()
        })
        .then((text) => {
          contentCache.set(cacheKey, text)
          
          const chunkSize = 500
          let currentIndex = 0
          
          const showChunk = () => {
            if (currentIndex < text.length) {
              const chunk = text.slice(0, currentIndex + chunkSize)
              setContent(chunk)
              currentIndex += chunkSize
              requestAnimationFrame(() => {
                setTimeout(showChunk, 10)
              })
            } else {
              setContent(text)
              setIsLoading(false)
            }
          }
          
          showChunk()
        })
        .catch((err) => {
          if (err.name === 'AbortError') return
          console.error('Failed to load about:', err)
          setContent('# Ошибка загрузки\n\nНе удалось загрузить информацию о программе.')
          setIsLoading(false)
        })
    } else {
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

  if (!isOpen) return null

  return createPortal(
    <div className="documentation-modal-overlay" onClick={onClose}>
      <div className="documentation-modal" onClick={(e) => e.stopPropagation()}>
        <div className="documentation-modal-header">
          <h2 className="documentation-modal-title">О программе</h2>
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
            <div className="documentation-loading">Загрузка...</div>
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
