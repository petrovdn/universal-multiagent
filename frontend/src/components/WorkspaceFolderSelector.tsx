import { useState, useEffect } from 'react'
import { Folder, Loader2, X } from 'lucide-react'
import { listWorkspaceFolders, setWorkspaceFolder, createWorkspaceFolder, getCurrentWorkspaceFolder } from '../services/api'

interface WorkspaceFolderSelectorProps {
  isOpen: boolean
  onClose: () => void
  onFolderSelected: () => void
}

interface FolderItem {
  id: string
  name: string
  createdTime?: string
  modifiedTime?: string
  url?: string
}

export function WorkspaceFolderSelector({ isOpen, onClose, onFolderSelected }: WorkspaceFolderSelectorProps) {
  const [folders, setFolders] = useState<FolderItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [currentFolder, setCurrentFolder] = useState<FolderItem | null>(null)
  const [showCreateFolder, setShowCreateFolder] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadFolders()
      loadCurrentFolder()
    }
  }, [isOpen])

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
      onFolderSelected()
      onClose()
    } catch (error: any) {
      console.error('Failed to set folder:', error)
      alert(error.message || 'Не удалось установить папку')
    } finally {
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
    } finally {
      setIsCreating(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold">Выберите рабочую папку</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current folder info */}
        {currentFolder && (
          <div className="p-4 bg-blue-50 border-b">
            <div className="text-sm text-gray-600 mb-1">Текущая рабочая папка:</div>
            <div className="flex items-center space-x-2">
              <Folder className="w-4 h-4 text-blue-600" />
              <span className="font-medium text-blue-900">{currentFolder.name}</span>
            </div>
          </div>
        )}

        {/* Create folder form */}
        {showCreateFolder && (
          <div className="p-4 border-b bg-gray-50">
            <div className="flex space-x-2">
              <input
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Название папки"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateFolder()
                  }
                }}
              />
              <button
                onClick={handleCreateFolder}
                disabled={isCreating || !newFolderName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Создать'}
              </button>
              <button
                onClick={() => {
                  setShowCreateFolder(false)
                  setNewFolderName('')
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                Отмена
              </button>
            </div>
          </div>
        )}

        {/* Folder list */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : folders.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Folder className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>Папки не найдены</p>
            </div>
          ) : (
            <div className="space-y-2">
              {folders.map((folder) => (
                <button
                  key={folder.id}
                  onClick={() => handleSelectFolder(folder)}
                  disabled={isLoading || folder.id === currentFolder?.id}
                  className={`w-full text-left p-3 rounded-md border hover:bg-gray-50 transition-colors ${
                    folder.id === currentFolder?.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200'
                  } ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="flex items-center space-x-3">
                    <Folder className="w-5 h-5 text-blue-600" />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{folder.name}</div>
                      {folder.modifiedTime && (
                        <div className="text-sm text-gray-500">
                          Изменено: {new Date(folder.modifiedTime).toLocaleDateString('ru-RU')}
                        </div>
                      )}
                    </div>
                    {folder.id === currentFolder?.id && (
                      <span className="text-sm text-blue-600 font-medium">Текущая</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
          <button
            onClick={() => setShowCreateFolder(!showCreateFolder)}
            className="px-4 py-2 text-blue-600 hover:text-blue-700 font-medium"
          >
            + Создать новую папку
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}



