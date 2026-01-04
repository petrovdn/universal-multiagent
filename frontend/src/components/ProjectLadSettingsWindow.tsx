import { useState, useEffect } from 'react'
import { X, TestTube, Save, Eye, EyeOff } from 'lucide-react'
import { getProjectLadConfig, saveProjectLadConfig, testProjectLadConnection, type ProjectLadConfig } from '../services/api'

export function ProjectLadSettingsWindow() {
  const [values, setValues] = useState({
    base_url: '',
    email: '',
    password: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [error, setError] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const result = await getProjectLadConfig()
      if (result.configured && result.config) {
        setValues({
          base_url: result.config.base_url || '',
          email: result.config.email || '',
          password: result.config.password === '***' ? '' : (result.config.password || ''),
        })
      }
    } catch (err) {
      console.error('Failed to load ProjectLad config:', err)
    }
  }

  const togglePasswordVisibility = () => {
    setShowPassword((prev) => !prev)
  }

  const validateFields = (): boolean => {
    if (!values.base_url?.trim()) {
      setError('Поле "Base URL" обязательно для заполнения')
      return false
    }
    if (!values.email?.trim()) {
      setError('Поле "Email" обязательно для заполнения')
      return false
    }
    if (!values.password?.trim()) {
      setError('Поле "Пароль" обязательно для заполнения')
      return false
    }
    return true
  }

  const handleTest = async () => {
    if (!validateFields()) {
      return
    }

    setIsTesting(true)
    setError('')
    setTestResult(null)

    try {
      const config: ProjectLadConfig = {
        base_url: values.base_url,
        email: values.email,
        password: values.password,
      }
      await saveProjectLadConfig(config)
      const result = await testProjectLadConnection()
      setTestResult({
        success: result.connected || false,
        message: result.message || (result.connected ? 'Подключение успешно' : 'Не удалось подключиться'),
      })
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Ошибка при проверке подключения',
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = async () => {
    if (!validateFields()) {
      return
    }

    setIsLoading(true)
    setError('')
    setTestResult(null)

    try {
      const config: ProjectLadConfig = {
        base_url: values.base_url,
        email: values.email,
        password: values.password,
      }
      await saveProjectLadConfig(config)
      
      // Send message to parent window
      if (window.opener) {
        window.opener.postMessage({
          type: 'projectlad-config-saved',
        }, window.location.origin)
      }
      
      // Close window
      window.close()
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Не удалось сохранить настройки')
      setIsLoading(false)
    }
  }

  const updateValue = (key: string, value: string) => {
    setValues((prev) => ({
      ...prev,
      [key]: value,
    }))
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
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Настройки Project Lad</h2>
        <button
          onClick={() => window.close()}
          className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div 
        className="flex-1 overflow-y-auto p-6"
        style={{
          minHeight: '0'
        }}
      >
        <div className="max-w-2xl mx-auto space-y-4">
          {/* Base URL */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Base URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              value={values.base_url}
              onChange={(e) => updateValue('base_url', e.target.value)}
              placeholder="https://api.staging.po.ladcloud.ru"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Базовый URL для Project Lad API
            </p>
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={values.email}
              onChange={(e) => updateValue('email', e.target.value)}
              placeholder="user@example.com"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Пароль <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={values.password}
                onChange={(e) => updateValue('password', e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 pr-10 border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading || isTesting}
                autoComplete="off"
              />
              <button
                type="button"
                onClick={togglePasswordVisibility}
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

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div
              className={`p-3 border rounded-md ${
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
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex gap-2 flex-shrink-0">
        <button
          onClick={handleTest}
          disabled={
            isLoading ||
            isTesting ||
            !values.base_url?.trim() ||
            !values.email?.trim() ||
            !values.password?.trim()
          }
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-md hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <TestTube className="w-4 h-4" />
          {isTesting ? 'Проверка...' : 'Проверить'}
        </button>
        <button
          onClick={handleSave}
          disabled={
            isLoading ||
            isTesting ||
            !values.base_url?.trim() ||
            !values.email?.trim() ||
            !values.password?.trim()
          }
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Save className="w-4 h-4" />
          {isLoading ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </div>
  )
}

