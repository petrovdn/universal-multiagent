import React, { useRef, useEffect } from 'react'
import { useWorkspaceStore } from '../store/workspaceStore'

interface TextStreamingBlockProps {
  fileName: string
  content: string
  isStreaming: boolean
  fileId?: string
  fileUrl?: string
  fileType?: 'sheets' | 'docs' | 'slides' | 'code' | 'email' | 'chart'
  previewData?: any
  className?: string
}

export function TextStreamingBlock({
  fileName,
  content,
  isStreaming,
  fileId,
  fileUrl,
  fileType,
  previewData,
  className = ''
}: TextStreamingBlockProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const addTab = useWorkspaceStore((state) => state.addTab)

  // Auto-scroll вверх при стриминге
  useEffect(() => {
    if (contentRef.current && isStreaming) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [content, isStreaming])

  // Открываем файл в правой панели при появлении
  useEffect(() => {
    if (fileId && fileUrl && fileType && content && content.trim().length > 0) {
      // Проверяем, не открыт ли уже этот файл
      const tabs = useWorkspaceStore.getState().tabs
      const isAlreadyOpen = tabs.some(tab => tab.url === fileUrl || (tab.data && (tab.data as any).documentId === fileId || (tab.data as any).spreadsheetId === fileId || (tab.data as any).presentationId === fileId))
      
      if (!isAlreadyOpen && (fileType === 'sheets' || fileType === 'docs' || fileType === 'slides' || fileType === 'code')) {
        addTab({
          type: fileType as 'sheets' | 'docs' | 'slides' | 'code',
          title: fileName,
          url: fileUrl,
          data: fileType === 'sheets' ? { spreadsheetId: fileId } :
                fileType === 'docs' ? { documentId: fileId } :
                fileType === 'slides' ? { presentationId: fileId } :
                fileType === 'code' ? previewData :
                {},
          closeable: true
        })
      }
    }
  }, [fileId, fileUrl, fileType, fileName, content, addTab, previewData])

  return (
    <div className={`text-streaming-block ${className}`}>
      <div className="text-streaming-header">
        {fileName}
      </div>
      <div 
        ref={contentRef}
        className="text-streaming-content"
      >
        {content}
        {isStreaming && (
          <span className="text-streaming-cursor">▊</span>
        )}
      </div>
    </div>
  )
}
