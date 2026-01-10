import { useState, useEffect } from 'react'
import { Folder, Loader2, X, AlertCircle, ChevronRight, ArrowLeft, Check } from 'lucide-react'
import { listWorkspaceFolders, setWorkspaceFolder, getCurrentWorkspaceFolder } from '../services/api'

interface FolderItem {
  id: string
  name: string
  createdTime?: string
  modifiedTime?: string
  url?: string
  parents?: string[]
}

interface BreadcrumbItem {
  id: string | null
  name: string
}

export function WorkspaceFolderSelectorWindow() {
  const [folders, setFolders] = useState<FolderItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentFolder, setCurrentFolder] = useState<FolderItem | null>(null)
  const [error, setError] = useState<{ message: string; isConfigError: boolean } | null>(null)
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([{ id: null, name: 'Мой диск' }])
  const [currentParentId, setCurrentParentId] = useState<string | null>(null)

  useEffect(() => {
    loadFolders(null)
    loadCurrentFolder()
  }, [])

  const loadFolders = async (parentId: string | null) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await listWorkspaceFolders(parentId || undefined)
      setFolders(result.folders || [])
      setCurrentParentId(parentId)
    } catch (error: any) {
      console.error('[WorkspaceFolderSelectorWindow] Error loading folders:', error)
      const errorMessage = error.message || error.response?.data?.detail || 'Не удалось загрузить список папок'
      const isConfigError = errorMessage.includes('not authenticated') || 
                          errorMessage.includes('не аутентифицирован') ||
                          errorMessage.includes('authentication')
      setError({
        message: errorMessage,
        isConfigError
      })
    } finally {
      setIsLoading(false)
    }
  }

  const loadCurrentFolder = async () => {
    try {
      const result = await getCurrentWorkspaceFolder()
      if (result.folder_id) {
        setCurrentFolder({
          id: result.folder_id,
          name: result.folder_name || 'Неизвестная папка',
          url: result.folder_url,
        })
      }
    } catch (error) {
      console.error('Failed to load current folder:', error)
    }
  }

  const handleOpenFolder = (folder: FolderItem) => {
    // Add folder to breadcrumbs and load its subfolders
    const newBreadcrumbs = [...breadcrumbs, { id: folder.id, name: folder.name }]
    setBreadcrumbs(newBreadcrumbs)
    loadFolders(folder.id)
  }

  const handleBreadcrumbClick = (breadcrumbIndex: number) => {
    // Navigate to the clicked breadcrumb
    const newBreadcrumbs = breadcrumbs.slice(0, breadcrumbIndex + 1)
    setBreadcrumbs(newBreadcrumbs)
    
    const targetBreadcrumb = newBreadcrumbs[newBreadcrumbs.length - 1]
    loadFolders(targetBreadcrumb.id)
  }

  const handleSelectFolder = async (folder: FolderItem) => {
    setIsLoading(true)
    try {
      await setWorkspaceFolder(folder.id, folder.name)
      setCurrentFolder(folder)
      
      // Send message to parent window
      if (window.opener) {
        window.opener.postMessage({
          type: 'workspace-folder-selected',
          folder: {
            id: folder.id,
            name: folder.name,
            url: folder.url,
          }
        }, window.location.origin)
      }
      
      // Close window
      window.close()
    } catch (error: any) {
      console.error('Failed to set folder:', error)
      alert(error.message || 'Не удалось установить папку')
      setIsLoading(false)
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

  // Sort folders: current folder first, then by modifiedTime desc
  const sortedFolders = [...folders].sort((a, b) => {
    if (currentFolder) {
      if (a.id === currentFolder.id) return -1
      if (b.id === currentFolder.id) return 1
    }
    const aTime = a.modifiedTime ? new Date(a.modifiedTime).getTime() : 0
    const bTime = b.modifiedTime ? new Date(b.modifiedTime).getTime() : 0
    return bTime - aTime
  })

  const folderIconColor = '#FF9800' // Folder orange
  const currentFolderIconColor = '#4285F4' // Google blue for current folder

  return (
    <div 
      className="bg-white dark:bg-slate-900"
      style={{
        height: '100vh',
        width: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex-shrink-0">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Выберите рабочую папку</h2>
        <button
          onClick={() => window.close()}
          className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Breadcrumbs */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex-shrink-0 overflow-x-auto">
        {breadcrumbs.map((breadcrumb, index) => (
          <div key={breadcrumb.id || 'root'} className="flex items-center gap-1 flex-shrink-0">
            {index > 0 && (
              <ChevronRight className="w-4 h-4 text-slate-400 dark:text-slate-500 mx-1" />
            )}
            <button
              onClick={() => handleBreadcrumbClick(index)}
              className={`px-2 py-1 rounded text-sm font-medium transition-colors ${
                index === breadcrumbs.length - 1
                  ? 'text-slate-900 dark:text-slate-100 bg-slate-100 dark:bg-slate-800'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {breadcrumb.name}
            </button>
          </div>
        ))}
      </div>

      {/* Back button if not at root */}
      {currentParentId && (
        <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex-shrink-0">
          <button
            onClick={() => {
              if (breadcrumbs.length > 1) {
                handleBreadcrumbClick(breadcrumbs.length - 2)
              }
            }}
            className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Назад</span>
          </button>
        </div>
      )}

      {/* Content */}
      <div 
        className="bg-white dark:bg-slate-900"
        style={{
          flex: '1 1 0%',
          minHeight: '0',
          overflowY: 'auto',
          overflowX: 'hidden'
        }}
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400 dark:text-slate-500" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-12 px-4">
            <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-6 shadow-lg">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <AlertCircle className="w-8 h-8 text-amber-500 dark:text-amber-400" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-2">
                    {error.isConfigError ? 'Ошибка аутентификации' : 'Ошибка загрузки папок'}
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                    {error.message}
                  </p>
                  <button
                    onClick={() => loadFolders(currentParentId)}
                    className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                  >
                    Попробовать снова
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : sortedFolders.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            <Folder className="w-12 h-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
            <p>Папки не найдены</p>
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
                  <th className="text-left font-medium text-slate-700 dark:text-slate-300 w-56" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>Дата изменения</th>
                  <th className="text-center font-medium text-slate-700 dark:text-slate-300 w-32" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {sortedFolders.map((folder) => {
                  const isCurrent = folder.id === currentFolder?.id
                  const iconColor = isCurrent ? currentFolderIconColor : folderIconColor
                  return (
                    <tr
                      key={folder.id}
                      onClick={() => !isLoading && handleOpenFolder(folder)}
                      className={`border-b border-slate-200 dark:border-slate-700 transition-colors ${
                        isCurrent 
                          ? 'bg-blue-50 dark:bg-blue-900/20' 
                          : 'cursor-pointer'
                      } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                      onMouseEnter={(e) => {
                        if (!isLoading && !isCurrent) {
                          e.currentTarget.style.backgroundColor = document.documentElement.classList.contains('dark') ? 'rgb(51 65 85)' : 'rgb(241 245 249)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isCurrent) {
                          e.currentTarget.style.backgroundColor = ''
                        }
                      }}
                    >
                      <td className="text-center w-16" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                        <div 
                          className="w-8 h-8 rounded flex items-center justify-center"
                          style={{ backgroundColor: `${iconColor}15`, margin: '0 auto' }}
                        >
                          <Folder 
                            className="w-5 h-5" 
                            style={{ color: iconColor }}
                          />
                        </div>
                      </td>
                      <td style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                        <span 
                          className={`font-medium transition-colors ${
                            isCurrent 
                              ? 'text-blue-600 dark:text-blue-400' 
                              : 'text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer'
                          }`}
                          onClick={(e) => {
                            e.stopPropagation()
                            if (!isLoading) {
                              handleOpenFolder(folder)
                            }
                          }}
                          title="Клик - открыть папку"
                        >
                          {folder.name}
                        </span>
                      </td>
                      <td className="text-slate-600 dark:text-slate-400 w-56 whitespace-nowrap" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                        {formatDate(folder.modifiedTime)}
                      </td>
                      <td className="text-center w-32" style={{ paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (!isLoading) {
                              handleSelectFolder(folder)
                            }
                          }}
                          disabled={isLoading}
                          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                            isCurrent
                              ? 'bg-blue-600 text-white cursor-default'
                              : 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-slate-400 disabled:cursor-not-allowed'
                          }`}
                          title="Выбрать эту папку как рабочую"
                        >
                          {isCurrent ? (
                            <div className="flex items-center gap-1.5">
                              <Check className="w-4 h-4" />
                              <span>Выбрана</span>
                            </div>
                          ) : (
                            'Выбрать'
                          )}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex-shrink-0">
        <div className="text-sm text-slate-500 dark:text-slate-400">
          Найдено папок: {folders.length}
        </div>
      </div>
    </div>
  )
}




