import { useState, useEffect } from 'react'
import { X, TestTube, Save, Eye, EyeOff } from 'lucide-react'
import { saveOneCConfig, getOneCConfig, testOneCConnection, OneCConfig } from '../services/api'

interface OneCSettingsDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfigSaved?: () => void
}

export function OneCSettingsDialog({ isOpen, onClose, onConfigSaved }: OneCSettingsDialogProps) {
  const [config, setConfig] = useState<OneCConfig>({
    odata_base_url: '',
    username: '',
    password: '',
    organization_guid: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [error, setError] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadConfig()
    }
  }, [isOpen])

  const loadConfig = async () => {
    try {
      const result = await getOneCConfig()
      if (result.configured && result.config) {
        setConfig({
          odata_base_url: result.config.odata_base_url || '',
          username: result.config.username || '',
          password: result.config.password === '***' ? '' : (result.config.password || ''),
          organization_guid: result.config.organization_guid || '',
        })
      } else {
        // Reset to defaults
        setConfig({
          odata_base_url: '',
          username: '',
          password: '',
          organization_guid: '',
        })
      }
      setError('')
      setTestResult(null)
    } catch (err: any) {
      console.error('Failed to load 1C config:', err)
      setError('Не удалось загрузить настройки')
    }
  }

  const handleTest = async () => {
    if (!config.odata_base_url || !config.username || !config.password) {
      setError('Заполните все обязательные поля')
      return
    }

    setIsTesting(true)
    setError('')
    setTestResult(null)

    try {
      // Save config temporarily for test
      await saveOneCConfig(config)
      const result = await testOneCConnection()
      
      if (result.connected) {
        setTestResult({ success: true, message: result.message || 'Подключение успешно' })
      } else {
        setTestResult({ success: false, message: result.message || 'Не удалось подключиться' })
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Ошибка при проверке подключения'
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = async () => {
    if (!config.odata_base_url || !config.username || !config.password) {
      setError('Заполните все обязательные поля')
      return
    }

    setIsLoading(true)
    setError('')
    setTestResult(null)

    try {
      await saveOneCConfig(config)
      if (onConfigSaved) {
        onConfigSaved()
      }
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Не удалось сохранить настройки')
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Настройки 1С:Бухгалтерия
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              OData URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={config.odata_base_url}
              onChange={(e) => setConfig({ ...config, odata_base_url: e.target.value })}
              placeholder="https://your-domain.1cfresh.com/odata/standard.odata"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Базовый URL для OData endpoint из настроек 1С:Фреш
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Логин <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={config.username}
              onChange={(e) => setConfig({ ...config, username: e.target.value })}
              placeholder="odata_user"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Пароль <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={config.password}
                onChange={(e) => setConfig({ ...config, password: e.target.value })}
                placeholder="••••••••"
                className="w-full px-3 py-2 pr-10 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading || isTesting}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              GUID организации (опционально)
            </label>
            <input
              type="text"
              value={config.organization_guid || ''}
              onChange={(e) => setConfig({ ...config, organization_guid: e.target.value })}
              placeholder="00000000-0000-0000-0000-000000000000"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Оставьте пустым, если нужны данные по всем организациям
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {testResult && (
            <div
              className={`p-3 border rounded-lg ${
                testResult.success
                  ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                  : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
              }`}
            >
              <p
                className={`text-sm ${
                  testResult.success
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-red-600 dark:text-red-400'
                }`}
              >
                {testResult.message}
              </p>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button
              onClick={handleTest}
              disabled={isLoading || isTesting || !config.odata_base_url || !config.username || !config.password}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <TestTube className="w-4 h-4" />
              {isTesting ? 'Проверка...' : 'Проверить'}
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading || isTesting || !config.odata_base_url || !config.username || !config.password}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Save className="w-4 h-4" />
              {isLoading ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}



