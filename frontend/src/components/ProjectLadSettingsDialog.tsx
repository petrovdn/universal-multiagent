import { useState, useEffect } from 'react'
import { X, TestTube, Save, Eye, EyeOff } from 'lucide-react'
import { saveProjectLadConfig, getProjectLadConfig, testProjectLadConnection, ProjectLadConfig } from '../services/api'

interface ProjectLadSettingsDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfigSaved?: () => void
}

export function ProjectLadSettingsDialog({ isOpen, onClose, onConfigSaved }: ProjectLadSettingsDialogProps) {
  const [config, setConfig] = useState<ProjectLadConfig>({
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
    if (isOpen) {
      loadConfig()
    }
  }, [isOpen])
  
  // #region agent log
  useEffect(() => {
    const baseUrlTrimmed = config.base_url?.trim() || ''
    const emailTrimmed = config.email?.trim() || ''
    const passwordTrimmed = config.password?.trim() || ''
    const testButtonDisabled = isLoading || isTesting || !baseUrlTrimmed || !emailTrimmed || !passwordTrimmed
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:config:changed',message:'Config state changed',data:{base_url:config.base_url,base_url_trimmed:baseUrlTrimmed,email:config.email,email_trimmed:emailTrimmed,password_length:config.password?.length||0,password_trimmed_length:passwordTrimmed.length,showPassword,isLoading,isTesting,testButtonDisabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
  }, [config, showPassword, isLoading, isTesting]);
  // #endregion

  const loadConfig = async () => {
    try {
      const result = await getProjectLadConfig()
      if (result.configured && result.config) {
        setConfig({
          base_url: result.config.base_url || '',
          email: result.config.email || '',
          password: result.config.password === '***' ? '' : (result.config.password || ''),
        })
      } else {
        // Reset to defaults
        setConfig({
          base_url: '',
          email: '',
          password: '',
        })
      }
      setError('')
      setTestResult(null)
    } catch (err: any) {
      console.error('Failed to load Project Lad config:', err)
      setError('Не удалось загрузить настройки')
    }
  }

  const handleTest = async () => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:entry',message:'handleTest called',data:{base_url:config.base_url,email:config.email,password_length:config.password?.length,base_url_trimmed:config.base_url?.trim(),email_trimmed:config.email?.trim(),password_trimmed:config.password?.trim()},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    // #region agent log
    const baseUrlCheck = !config.base_url?.trim()
    const emailCheck = !config.email?.trim()
    const passwordCheck = !config.password?.trim()
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:validation',message:'Validation checks',data:{baseUrlCheck,emailCheck,passwordCheck,willReturn:baseUrlCheck||emailCheck||passwordCheck},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (!config.base_url || !config.email || !config.password) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:validation_failed',message:'Validation failed, returning early',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      setError('Заполните все обязательные поля')
      return
    }

    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:starting',message:'Starting test process',data:{isTesting_before:isTesting},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    setIsTesting(true)
    setError('')
    setTestResult(null)

    try {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:before_save',message:'About to save config',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      // Save config temporarily for test
      await saveProjectLadConfig(config)
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:before_test',message:'About to test connection',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      const result = await testProjectLadConnection()
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:result_received',message:'Test result received',data:{connected:result.connected,result_message:result.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      if (result.connected) {
        setTestResult({ success: true, message: result.message || 'Подключение успешно' })
      } else {
        setTestResult({ success: false, message: result.message || 'Не удалось подключиться' })
      }
    } catch (err: any) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:handleTest:error',message:'Error in handleTest',data:{error:err?.message,error_type:err?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      setTestResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Ошибка при проверке подключения'
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = async () => {
    if (!config.base_url || !config.email || !config.password) {
      setError('Заполните все обязательные поля')
      return
    }

    setIsLoading(true)
    setError('')
    setTestResult(null)

    try {
      await saveProjectLadConfig(config)
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
            Настройки Project Lad
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
              Base URL <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={config.base_url}
              onChange={(e) => {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:base_url:onChange',message:'Base URL changed',data:{value:e.target.value,trimmed:e.target.value.trim(),length:e.target.value.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                // #endregion
                setConfig({ ...config, base_url: e.target.value })
              }}
              placeholder="https://api.staging.po.ladcloud.ru"
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading || isTesting}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Базовый URL для Project Lad API
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={config.email}
              onChange={(e) => {
                // #region agent log
                fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:email:onChange',message:'Email changed',data:{value:e.target.value,trimmed:e.target.value.trim(),length:e.target.value.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                // #endregion
                setConfig({ ...config, email: e.target.value })
              }}
              placeholder="user@example.com"
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
                value={config.password || ''}
                onChange={(e) => {
                  const newValue = e.target.value
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:password:onChange',message:'Password changed',data:{value_length:newValue.length,trimmed_length:newValue.trim().length,showPassword,current_password_length:config.password?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                  // #endregion
                  setConfig((prev) => {
                    const updated = { ...prev, password: newValue }
                    // #region agent log
                    setTimeout(() => {
                      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:password:after_setConfig',message:'After setConfig',data:{updated_password_length:updated.password?.length||0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
                    }, 50);
                    // #endregion
                    return updated
                  })
                }}
                placeholder="••••••••"
                className="w-full px-3 py-2 pr-10 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoading || isTesting}
                autoComplete="off"
              />
              <button
                type="button"
                onClick={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:password_toggle:click',message:'Password toggle clicked',data:{showPassword_before:showPassword,isLoading,isTesting},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                  const newValue = !showPassword
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:password_toggle:setState',message:'Setting showPassword',data:{newValue},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
                  // #endregion
                  setShowPassword(newValue)
                  // #region agent log
                  setTimeout(() => {
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:password_toggle:after_setState',message:'After setShowPassword',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
                  }, 100);
                  // #endregion
                }}
                disabled={isLoading || isTesting}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer z-10 pointer-events-auto"
                tabIndex={-1}
                style={{ pointerEvents: 'auto' }}
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
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
              onClick={(e) => {
                // #region agent log
                const baseUrlTrimmed = config.base_url?.trim() || ''
                const emailTrimmed = config.email?.trim() || ''
                const passwordTrimmed = config.password?.trim() || ''
                const isDisabled = isLoading || isTesting || !baseUrlTrimmed || !emailTrimmed || !passwordTrimmed
                fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProjectLadSettingsDialog.tsx:test_button:click',message:'Test button clicked',data:{base_url:config.base_url,base_url_trimmed:baseUrlTrimmed,base_url_length:baseUrlTrimmed.length,email:config.email,email_trimmed:emailTrimmed,email_length:emailTrimmed.length,password_length:config.password?.length||0,password_trimmed_length:passwordTrimmed.length,isLoading,isTesting,isDisabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
                // #endregion
                if (!isDisabled) {
                  e.preventDefault()
                  e.stopPropagation()
                  handleTest()
                }
              }}
              disabled={isLoading || isTesting || !config.base_url?.trim() || !config.email?.trim() || !config.password?.trim()}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <TestTube className="w-4 h-4" />
              {isTesting ? 'Проверка...' : 'Проверить'}
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading || isTesting || !config.base_url?.trim() || !config.email?.trim() || !config.password?.trim()}
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

