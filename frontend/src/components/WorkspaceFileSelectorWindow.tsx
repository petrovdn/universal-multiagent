import React, { useState, useEffect } from 'react'
import { 
  File, 
  Loader2, 
  FileSpreadsheet, 
  FileText, 
  Presentation, 
  FileImage, 
  Folder, 
  FileCode,
  FileVideo,
  FileAudio,
  Archive,
  FileType
} from 'lucide-react'
import { listWorkspaceFiles } from '../services/api'

interface FileItem {
  id: string
  name: string
  mimeType: string
  createdTime?: string
  modifiedTime?: string
  url?: string
  size?: string
  owner?: string
}

export function WorkspaceFileSelectorWindow() {
  const [files, setFiles] = useState<FileItem[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    console.log('[WorkspaceFileSelectorWindow] Component mounted, calling loadFiles')
    loadFiles()
  }, [])

  useEffect(() => {
    console.log('[WorkspaceFileSelectorWindow] Render state:', { filesCount: files.length, isLoading })
  }, [files.length, isLoading])

  const loadFiles = async () => {
    console.log('[WorkspaceFileSelectorWindow] loadFiles called')
    setIsLoading(true)
    try {
      console.log('[WorkspaceFileSelectorWindow] About to call listWorkspaceFiles')
      const result = await listWorkspaceFiles(undefined, undefined, 200)
      console.log('[WorkspaceFileSelectorWindow] listWorkspaceFiles result:', { filesCount: result?.files?.length || 0, count: result?.count || 0 })
      setFiles(result.files || [])
      console.log('[WorkspaceFileSelectorWindow] Files state updated:', result.files?.length || 0)
    } catch (error: any) {
      console.error('[WorkspaceFileSelectorWindow] Error loading files:', error)
      alert(error.message || 'Не удалось загрузить список файлов')
    } finally {
      setIsLoading(false)
      console.log('[WorkspaceFileSelectorWindow] loadFiles completed, isLoading:', false)
    }
  }

  const handleSelectFile = (file: FileItem) => {
    if (window.opener) {
      window.opener.postMessage({
        type: 'workspace-file-selected',
        file: {
          id: file.id,
          name: file.name,
          mimeType: file.mimeType
        }
      }, window.location.origin)
      window.close()
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-'
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) {
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays < 7) {
      return date.toLocaleDateString('ru-RU', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
    } else {
      return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
    }
  }

  const getFileIcon = (mimeType: string) => {
    // Google Workspace files
    if (mimeType === 'application/vnd.google-apps.spreadsheet') {
      return { icon: FileSpreadsheet, color: '#0F9D58' } // Google Sheets green
    }
    if (mimeType === 'application/vnd.google-apps.document') {
      return { icon: FileText, color: '#4285F4' } // Google Docs blue
    }
    if (mimeType === 'application/vnd.google-apps.presentation') {
      return { icon: Presentation, color: '#F4B400' } // Google Slides yellow
    }
    if (mimeType === 'application/vnd.google-apps.folder') {
      return { icon: Folder, color: '#FF9800' } // Folder orange
    }
    if (mimeType === 'application/vnd.google-apps.form') {
      return { icon: FileText, color: '#673AB7' } // Google Forms purple
    }
    if (mimeType === 'application/vnd.google-apps.drawing') {
      return { icon: FileImage, color: '#9C27B0' } // Google Drawings purple
    }
    
    // Standard file types
    if (mimeType.startsWith('image/')) {
      return { icon: FileImage, color: '#9C27B0' } // Image purple
    }
    if (mimeType.startsWith('video/')) {
      return { icon: FileVideo, color: '#E91E63' } // Video pink
    }
    if (mimeType.startsWith('audio/')) {
      return { icon: FileAudio, color: '#FF5722' } // Audio deep orange
    }
    if (mimeType === 'application/pdf') {
      return { icon: FileType, color: '#DC143C' } // PDF red
    }
    if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('archive')) {
      return { icon: Archive, color: '#795548' } // Archive brown
    }
    if (mimeType.startsWith('text/') || mimeType.includes('javascript') || mimeType.includes('json') || mimeType.includes('xml')) {
      return { icon: FileCode, color: '#607D8B' } // Code blue-grey
    }
    
    // Default
    return { icon: File, color: '#757575' } // Default grey
  }

  return (
    <div className="h-screen w-full flex flex-col bg-white dark:bg-slate-900">
      <div className="flex items-center p-4 border-b border-slate-200 dark:border-slate-700 flex-shrink-0 bg-slate-50 dark:bg-slate-800">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Выберите файл из рабочей области</h2>
      </div>

      <div className="flex-1 overflow-y-auto bg-white dark:bg-slate-900">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400 dark:text-slate-500" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            <File className="w-12 h-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
            <p>Файлы не найдены</p>
          </div>
        ) : (
          <div style={{ paddingLeft: '16px', paddingRight: '16px' }}>
            <table className="w-full table-fixed">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="text-center font-medium text-slate-700 dark:text-slate-300 w-16" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}></th>
                <th className="text-left font-medium text-slate-700 dark:text-slate-300" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                  <div className="flex items-center gap-2">
                    Название
                    <span className="text-blue-500 dark:text-blue-400">↑</span>
                  </div>
                </th>
                <th className="text-left font-medium text-slate-700 dark:text-slate-300 w-80" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>Владелец</th>
                <th className="text-left font-medium text-slate-700 dark:text-slate-300 w-56" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>Дата изменения</th>
              </tr>
            </thead>
            <tbody>
              {files.map((file) => {
                const { icon: IconComponent, color } = getFileIcon(file.mimeType)
                return (
                  <tr
                    key={file.id}
                    onClick={() => handleSelectFile(file)}
                    className="border-b border-slate-200 dark:border-slate-700 cursor-pointer transition-colors"
                    style={{
                      backgroundColor: 'transparent'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = document.documentElement.classList.contains('dark') ? 'rgb(51 65 85)' : 'rgb(241 245 249)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent'
                    }}
                  >
                    <td className="text-center w-16" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                      <div 
                        className="w-8 h-8 rounded flex items-center justify-center"
                        style={{ backgroundColor: `${color}15`, margin: '0 auto' }}
                      >
                        <IconComponent 
                          className="w-5 h-5" 
                          style={{ color: color }}
                        />
                      </div>
                    </td>
                    <td style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                      <span 
                        className="font-medium text-slate-900 dark:text-slate-100 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSelectFile(file)
                        }}
                      >
                        {file.name}
                      </span>
                    </td>
                    <td className="w-80" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                      <span className="text-slate-700 dark:text-slate-300 whitespace-nowrap block">{file.owner || ''}</span>
                    </td>
                    <td className="text-slate-600 dark:text-slate-400 w-56 whitespace-nowrap" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                      {formatDate(file.modifiedTime)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex-shrink-0">
        <div className="text-sm text-slate-500 dark:text-slate-400">
          Найдено файлов: {files.length}
        </div>
      </div>
    </div>
  )
}
