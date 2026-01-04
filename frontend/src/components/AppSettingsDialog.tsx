import { useState, useEffect } from 'react'
import { X, TestTube, Save, Eye, EyeOff } from 'lucide-react'

export interface AppFieldConfig {
  key: string
  label: string
  type: 'text' | 'password' | 'email' | 'url'
  placeholder?: string
  required?: boolean
  helpText?: string
}

interface AppSettingsDialogProps {
  isOpen: boolean
  onClose: () => void
  appName: string
  fields: AppFieldConfig[]
  initialValues: Record<string, string>
  onSave: (values: Record<string, string>) => Promise<void>
  onTest?: (values: Record<string, string>) => Promise<{ success: boolean; message: string }>
  onConfigSaved?: () => void
}

export function AppSettingsDialog({
  isOpen,
  onClose,
  appName,
  fields,
  initialValues,
  onSave,
  onTest,
  onConfigSaved,
}: AppSettingsDialogProps) {
  const [values, setValues] = useState<Record<string, string>>(initialValues)
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [error, setError] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  useEffect(() => {
    if (isOpen) {
      setValues(initialValues)
      setShowPasswords({})
      setError('')
      setTestResult(null)
    }
  }, [isOpen, initialValues])

  const togglePasswordVisibility = (fieldKey: string) => {
    setShowPasswords((prev) => ({
      ...prev,
      [fieldKey]: !prev[fieldKey],
    }))
  }

  const validateFields = (): boolean => {
    for (const field of fields) {
      if (field.required && !values[field.key]?.trim()) {
        setError(`Поле "${field.label}" обязательно для заполнения`)
        return false
      }
    }
    return true
  }

  const handleTest = async () => {
    if (!validateFields()) {
      return
    }

    if (!onTest) {
      return
    }

    setIsTesting(true)
    setError('')
    setTestResult(null)

    try {
      const result = await onTest(values)
      setTestResult(result)
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
      await onSave(values)
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

  const updateValue = (key: string, value: string) => {
    setValues((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Настройки {appName}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {fields.map((field) => (
            <div key={field.key}>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                {field.label}
                {field.required && <span className="text-red-500"> *</span>}
              </label>
              {field.type === 'password' ? (
                <div className="relative">
                  <input
                    type={showPasswords[field.key] ? 'text' : 'password'}
                    value={values[field.key] || ''}
                    onChange={(e) => updateValue(field.key, e.target.value)}
                    placeholder={field.placeholder || '••••••••'}
                    className="w-full px-3 py-2 pr-10 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isLoading || isTesting}
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility(field.key)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                    tabIndex={-1}
                  >
                    {showPasswords[field.key] ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              ) : (
                <input
                  type={field.type}
                  value={values[field.key] || ''}
                  onChange={(e) => updateValue(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading || isTesting}
                />
              )}
              {field.helpText && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{field.helpText}</p>
              )}
            </div>
          ))}

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
            {onTest && (
              <button
                onClick={handleTest}
                disabled={
                  isLoading ||
                  isTesting ||
                  fields.some((field) => field.required && !values[field.key]?.trim())
                }
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <TestTube className="w-4 h-4" />
                {isTesting ? 'Проверка...' : 'Проверить'}
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={
                isLoading ||
                isTesting ||
                fields.some((field) => field.required && !values[field.key]?.trim())
              }
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

