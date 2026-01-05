import { useState, useEffect } from 'react'
import { Eye, EyeOff } from 'lucide-react'
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
  const [hasExistingPassword, setHasExistingPassword] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const result = await getProjectLadConfig()
      if (result.configured && result.config) {
        const hasPassword = result.config.password === '***'
        setHasExistingPassword(hasPassword)
        setValues({
          base_url: result.config.base_url || '',
          email: result.config.email || '',
          password: hasPassword ? '********' : (result.config.password || ''),
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
      // Если пароль не был изменен (остались звездочки), отправляем пустую строку
      const passwordToSave = hasExistingPassword && values.password === '********' ? '' : values.password
      const config: ProjectLadConfig = {
        base_url: values.base_url,
        email: values.email,
        password: passwordToSave,
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
      // Если пароль не был изменен (остались звездочки), отправляем пустую строку
      const passwordToSave = hasExistingPassword && values.password === '********' ? '' : values.password
      const config: ProjectLadConfig = {
        base_url: values.base_url,
        email: values.email,
        password: passwordToSave,
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
    // Если пользователь начал изменять пароль, сбрасываем флаг существующего пароля
    if (key === 'password' && hasExistingPassword && value !== '********') {
      setHasExistingPassword(false)
    }
  }

  return (
    <div 
      className="h-screen w-full flex flex-col bg-white dark:bg-[#1e1e1e]"
    >
      {/* Header */}
      <div className="px-6 pt-6 pb-3 border-b border-slate-200 dark:border-[#3d3d3d] flex-shrink-0">
        <h2 className="text-lg font-medium text-slate-900 dark:text-white tracking-tight" style={{ textAlign: 'center' }}>
          Настройки Project Lad
        </h2>
      </div>

      {/* Content */}
      <div 
        className="flex-1 overflow-y-auto py-5"
        style={{
          minHeight: '0'
        }}
      >
        <div className="max-w-2xl mx-auto" style={{ paddingLeft: '24px', paddingRight: '24px' }}>
          <form className="login-form">
          {/* Base URL */}
          <div className="login-field">
            <label htmlFor="base_url" className="login-label">
              Base URL
            </label>
            <input
              id="base_url"
              type="url"
              value={values.base_url}
              onChange={(e) => updateValue('base_url', e.target.value)}
              placeholder="https://api.staging.po.ladcloud.ru"
              className="login-input"
              disabled={isLoading || isTesting}
            />
          </div>

          {/* Email */}
          <div className="login-field">
            <label htmlFor="email" className="login-label">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={values.email}
              onChange={(e) => updateValue('email', e.target.value)}
              placeholder="user@example.com"
              className="login-input"
              disabled={isLoading || isTesting}
            />
          </div>
          
          {/* Password */}
          <div className="login-field">
            <label htmlFor="password" className="login-label">
              Пароль
            </label>
            <div className="login-password-wrapper">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={values.password}
                onChange={(e) => updateValue('password', e.target.value)}
                placeholder="••••••••"
                className="login-input login-password-input"
                disabled={isLoading || isTesting}
                autoComplete="off"
              />
              <button
                type="button"
                onClick={togglePasswordVisibility}
                className="login-password-toggle"
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
            <div className="login-error">
              {error}
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div className={testResult.success ? 'p-3 bg-green-50 dark:bg-[#1e3a2f] border border-green-200 dark:border-[#2d5a3f] rounded-md' : 'login-error'}>
              <p className={testResult.success ? 'text-sm text-green-600 dark:text-[#4ade80]' : ''}>
                {testResult.message}
              </p>
            </div>
          )}
          </form>
          
          {/* Buttons */}
          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'center', 
            marginTop: '24px',
            width: '100%'
          }}>
            <button
              onClick={handleTest}
              disabled={
                isLoading ||
                isTesting ||
                !values.base_url?.trim() ||
                !values.email?.trim() ||
                !values.password?.trim()
              }
              className="login-button-inline"
            >
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
              className="login-button-inline"
            >
              {isLoading ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

