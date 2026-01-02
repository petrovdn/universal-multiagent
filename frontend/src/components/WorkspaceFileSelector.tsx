import { useState, useEffect } from 'react'
import { File, Loader2, X, Search } from 'lucide-react'
import { listWorkspaceFiles } from '../services/api'

interface WorkspaceFileSelectorProps {
  isOpen: boolean
  onClose: () => void
  onFileSelected: (file: { id: string; name: string; mimeType: string }) => void
}

interface FileItem {
  id: string
  name: string
  mimeType: string
  createdTime?: string
  modifiedTime?: string
  url?: string
  size?: string
}

export function WorkspaceFileSelector({ isOpen, onClose, onFileSelected }: WorkspaceFileSelectorProps) {
  const [files, setFiles] = useState<FileItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (isOpen) {
      loadFiles()
    }
  }, [isOpen])

  const loadFiles = async (query?: string) => {
    setIsLoading(true)
    try {
      const result = await listWorkspaceFiles(undefined, query, 200)
      setFiles(result.files || [])
    } catch (error: any) {
      console.error('Failed to load files:', error)
      alert(error.message || 'Не удалось загрузить список файлов')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    loadFiles(searchQuery || undefined)
  }

  const handleSelectFile = (file: FileItem) => {
    onFileSelected({
      id: file.id,
      name: file.name,
      mimeType: file.mimeType
    })
    onClose()
  }


  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold">Выберите файл из рабочей области</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b">
          <form onSubmit={handleSearch} className="flex space-x-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск файлов..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Поиск'}
            </button>
          </form>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-slate-400">
              <File className="w-12 h-12 mx-auto mb-4 text-gray-300 dark:text-slate-600" />
              <p>Файлы не найдены</p>
            </div>
          ) : (
            <div className="space-y-2">
              {files.map((file) => (
                <button
                  key={file.id}
                  onClick={() => handleSelectFile(file)}
                  className="w-full text-left p-3 rounded-md border border-gray-200 hover:bg-gray-50 transition-colors cursor-pointer"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">
                      {file.name}
                    </div>
                    <div className="text-sm text-gray-500">
                      {file.mimeType}
                      {file.modifiedTime && (
                        <span className="ml-2">
                          • {new Date(file.modifiedTime).toLocaleDateString('ru-RU')}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50">
          <div className="text-sm text-gray-500">
            Найдено файлов: {files.length}
          </div>
        </div>
      </div>
    </div>
  )
}

