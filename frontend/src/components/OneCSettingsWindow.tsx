import { useState, useEffect } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { getOneCConfig, saveOneCConfig, testOneCConnection, type OneCConfig } from '../services/api'

export function OneCSettingsWindow() {
  const [values, setValues] = useState({
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
  const [hasExistingPassword, setHasExistingPassword] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const result = await getOneCConfig()
      if (result.configured && result.config) {
        const hasPassword = result.config.password === '***'
        setHasExistingPassword(hasPassword)
        setValues({
          odata_base_url: result.config.odata_base_url || '',
          username: result.config.username || '',
          password: hasPassword ? '********' : (result.config.password || ''),
          organization_guid: result.config.organization_guid || '',
        })
      }
    } catch (err) {
      console.error('Failed to load 1C config:', err)
    }
  }

  const togglePasswordVisibility = () => {
    setShowPassword((prev) => !prev)
  }

  const validateFields = (): boolean => {
    if (!values.odata_base_url?.trim()) {
      setError('Поле "OData URL" обязательно для заполнения')
      return false
    }
    if (!values.username?.trim()) {
      setError('Поле "Логин" обязательно для заполнения')
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
      const config: OneCConfig = {
        odata_base_url: values.odata_base_url,
        username: values.username,
        password: passwordToSave,
        organization_guid: values.organization_guid || undefined,
      }
      await saveOneCConfig(config)
      const result = await testOneCConnection()
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
      const config: OneCConfig = {
        odata_base_url: values.odata_base_url,
        username: values.username,
        password: passwordToSave,
        organization_guid: values.organization_guid || undefined,
      }
      await saveOneCConfig(config)
      
      // Send message to parent window
      if (window.opener) {
        window.opener.postMessage({
          type: 'onec-config-saved',
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
          Настройки 1С:Бухгалтерия
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
          {/* OData URL */}
          <div className="login-field">
            <label htmlFor="odata_base_url" className="login-label">
              OData URL
            </label>
            <input
              id="odata_base_url"
              type="url"
              value={values.odata_base_url}
              onChange={(e) => updateValue('odata_base_url', e.target.value)}
              placeholder="https://your-domain.1cfresh.com/odata/standard.odata"
              className="login-input"
              disabled={isLoading || isTesting}
            />
          </div>

          {/* Username */}
          <div className="login-field">
            <label htmlFor="username" className="login-label">
              Логин
            </label>
            <input
              id="username"
              type="text"
              value={values.username}
              onChange={(e) => updateValue('username', e.target.value)}
              placeholder="odata_user"
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

          {/* Organization GUID */}
          <div className="login-field">
            <label htmlFor="organization_guid" className="login-label">
              GUID организации <span className="font-normal text-slate-500 dark:text-slate-400">(опционально)</span>
            </label>
            <input
              id="organization_guid"
              type="text"
              value={values.organization_guid}
              onChange={(e) => updateValue('organization_guid', e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              className="login-input"
              disabled={isLoading || isTesting}
            />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Оставьте пустым, если нужны данные по всем организациям
            </p>
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
                !values.odata_base_url?.trim() ||
                !values.username?.trim() ||
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
                !values.odata_base_url?.trim() ||
                !values.username?.trim() ||
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

