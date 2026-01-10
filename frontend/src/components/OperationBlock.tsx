import React, { useRef, useEffect, useState } from 'react'
import { Operation, FileType } from '../store/chatStore'
import { useWorkspaceStore } from '../store/workspaceStore'

interface OperationBlockProps {
  operation: Operation
  onToggleCollapse: () => void
  className?: string
}

export function OperationBlock({
  operation,
  onToggleCollapse,
  className = ''
}: OperationBlockProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const addTab = useWorkspaceStore((state) => state.addTab)
  const [hasOpenedFile, setHasOpenedFile] = useState(false)

  const { id, title, streamingTitle, status, summary, data, isCollapsed, fileId, fileUrl, fileType } = operation
  
  // Формируем контент для окна стриминга
  const streamingContent = data.join('\n')

  // Auto-scroll при стриминге
  useEffect(() => {
    if (contentRef.current && status === 'streaming' && !isCollapsed) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [data, status, isCollapsed])

  // Автоматическое открытие файла в правой панели при появлении file_url
  useEffect(() => {
    if (fileId && fileUrl && fileType && !hasOpenedFile && (fileType === 'sheets' || fileType === 'docs' || fileType === 'slides')) {
      // Проверяем, не открыт ли уже этот файл
      const tabs = useWorkspaceStore.getState().tabs
      const isAlreadyOpen = tabs.some(tab => {
        if (tab.url === fileUrl) return true
        if (tab.data) {
          const tabData = tab.data as any
          if (fileType === 'sheets' && tabData.spreadsheetId === fileId) return true
          if (fileType === 'docs' && tabData.documentId === fileId) return true
          if (fileType === 'slides' && tabData.presentationId === fileId) return true
        }
        return false
      })
      
      if (!isAlreadyOpen) {
        addTab({
          type: fileType as 'sheets' | 'docs' | 'slides',
          title: streamingTitle,
          url: fileUrl,
          data: fileType === 'sheets' ? { spreadsheetId: fileId } :
                fileType === 'docs' ? { documentId: fileId } :
                fileType === 'slides' ? { presentationId: fileId } :
                {},
          closeable: true
        })
        setHasOpenedFile(true)
      }
    }
  }, [fileId, fileUrl, fileType, streamingTitle, hasOpenedFile, addTab])

  // Определяем заголовок операции
  const operationTitle = status === 'completed' && summary ? summary : title
  const isPending = status === 'pending'
  const isStreaming = status === 'streaming'
  const isCompleted = status === 'completed'

  // #region agent log - H1: Track operation status changes and title content
  useEffect(() => {
    const logData = {
      location: 'OperationBlock.tsx:69',
      message: 'Operation status changed',
      data: { 
        id, 
        status, 
        title, 
        operationTitle, 
        operationTitleLength: operationTitle?.length,
        operationTitleHasDots: operationTitle?.includes('...'),
        hasStreamingContent: !!streamingContent 
      },
      timestamp: Date.now(),
      sessionId: 'debug-session',
      runId: 'run1',
      hypothesisId: 'H1'
    }
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(logData)
    }).catch(() => {})
  }, [id, status, title, operationTitle, streamingContent])
  // #endregion

  return (
    <div className={`operation-block ${className}`}>
      {/* Заголовок операции */}
      <div className="execution-log-item">
        <span className={`log-icon ${isCompleted ? 'done' : 'pending'}`}>
          {isCompleted ? '✓' : '○'}
        </span>
        <div className="log-text-container">
          <span className="log-text-title">
            {operationTitle}
          </span>
        </div>
      </div>

      {/* Окно стриминга данных */}
      {(streamingContent || isStreaming) && (
        <div className={`operation-streaming-block ${isCollapsed ? 'operation-streaming-collapsed' : ''}`}>
          <div 
            className="operation-streaming-header"
            onClick={onToggleCollapse}
            style={{ cursor: 'pointer' }}
          >
            <span style={{ fontSize: '10px', marginRight: '4px' }}>
              {isCollapsed ? '▶' : '▼'}
            </span>
            <span>{streamingTitle}</span>
            {isStreaming && (
              <span style={{ marginLeft: 'auto', fontSize: '12px' }}>🔄</span>
            )}
          </div>
          {!isCollapsed && (
            <div 
              ref={contentRef}
              className="operation-streaming-content"
            >
              {streamingContent}
              {isStreaming && (
                <span className="text-streaming-cursor">▊</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}