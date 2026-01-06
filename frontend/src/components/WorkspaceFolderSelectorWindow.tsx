import { useState, useEffect } from 'react'
import { Folder, Loader2, X } from 'lucide-react'
import { listWorkspaceFolders, setWorkspaceFolder, createWorkspaceFolder, getCurrentWorkspaceFolder } from '../services/api'

interface FolderItem {
  id: string
  name: string
  createdTime?: string
  modifiedTime?: string
  url?: string
}

export function WorkspaceFolderSelectorWindow() {
  const [folders, setFolders] = useState<FolderItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [currentFolder, setCurrentFolder] = useState<FolderItem | null>(null)
  const [showCreateFolder, setShowCreateFolder] = useState(false)

  useEffect(() => {
    loadFolders()
    loadCurrentFolder()
  }, [])

  const loadFolders = async () => {
    setIsLoading(true)
    try {
      const result = await listWorkspaceFolders()
      setFolders(result.folders || [])
    } catch (error: any) {
      console.error('Failed to load folders:', error)
      alert(error.message || 'Не удалось загрузить список папок')
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

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      alert('Введите название папки')
      return
    }

    setIsCreating(true)
    try {
      const result = await createWorkspaceFolder(newFolderName.trim())
      const newFolder: FolderItem = {
        id: result.id,
        name: result.name,
        url: result.url,
      }
      setFolders([newFolder, ...folders])
      setNewFolderName('')
      setShowCreateFolder(false)
      // Automatically select the newly created folder
      await handleSelectFolder(newFolder)
    } catch (error: any) {
      console.error('Failed to create folder:', error)
      alert(error.message || 'Не удалось создать папку')
      setIsCreating(false)
    }
  }

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

      {/* Current folder info */}
      {currentFolder && (
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border-b border-slate-200 dark:border-slate-700 flex-shrink-0">
          <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Текущая рабочая папка:</div>
          <div className="flex items-center space-x-2">
            <Folder className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="font-medium text-blue-900 dark:text-blue-100">{currentFolder.name}</span>
          </div>
        </div>
      )}

      {/* Create folder form */}
      {showCreateFolder && (
        <div className="p-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex-shrink-0">
          <div className="flex space-x-2">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="Название папки"
              className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleCreateFolder()
                }
              }}
            />
            <button
              onClick={handleCreateFolder}
              disabled={isCreating || !newFolderName.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-slate-400 disabled:cursor-not-allowed"
            >
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Создать'}
            </button>
            <button
              onClick={() => {
                setShowCreateFolder(false)
                setNewFolderName('')
              }}
              className="px-4 py-2 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-md hover:bg-slate-300 dark:hover:bg-slate-500"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Folder list */}
      <div 
        className="flex-1 overflow-y-auto p-4"
        style={{
          minHeight: '0'
        }}
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400 dark:text-slate-500" />
          </div>
        ) : folders.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            <Folder className="w-12 h-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
            <p>Папки не найдены</p>
          </div>
        ) : (
          <div className="space-y-2">
            {folders.map((folder) => (
              <button
                key={folder.id}
                onClick={() => handleSelectFolder(folder)}
                disabled={isLoading || folder.id === currentFolder?.id}
                className={`w-full text-left p-3 rounded-md border transition-colors ${
                  folder.id === currentFolder?.id
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'
                } ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="flex items-center space-x-3">
                  <Folder className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <div className="flex-1">
                    <div className="font-medium text-slate-900 dark:text-slate-100">{folder.name}</div>
                    {folder.modifiedTime && (
                      <div className="text-sm text-slate-500 dark:text-slate-400">
                        Изменено: {new Date(folder.modifiedTime).toLocaleDateString('ru-RU')}
                      </div>
                    )}
                  </div>
                  {folder.id === currentFolder?.id && (
                    <span className="text-sm text-blue-600 dark:text-blue-400 font-medium">Текущая</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex justify-between items-center flex-shrink-0">
        <button
          onClick={() => setShowCreateFolder(!showCreateFolder)}
          className="px-4 py-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
        >
          + Создать новую папку
        </button>
        <button
          onClick={() => window.close()}
          className="px-4 py-2 bg-slate-200 dark:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-md hover:bg-slate-300 dark:hover:bg-slate-500"
        >
          Закрыть
        </button>
      </div>
    </div>
  )
}




