import { useEffect, useState, useRef } from 'react'
import { Header } from './components/Header'
import { SplitLayout } from './components/SplitLayout'
import { LoginDialog } from './components/LoginDialog'
import { useSettingsStore } from './store/settingsStore'
import { getGoogleCalendarStatus, getGmailStatus, getGoogleWorkspaceStatus, getCurrentUser } from './services/api'

// App version - increment to clear cache
const APP_VERSION = '5.0.0'
const VERSION_KEY = 'app-version'

function App() {
  const { theme, setIntegrationStatus } = useSettingsStore()
  const [notification, setNotification] = useState<{ type: 'success' | 'error', message: string } | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [currentUsername, setCurrentUsername] = useState<string | null>(null)
  const [justLoggedIn, setJustLoggedIn] = useState(false)
  const checkAuthRef = useRef<Promise<void> | null>(null)

  useEffect(() => {
    console.log('[App] useEffect called', { justLoggedIn })
    // Check authentication status only if not just logged in
    if (!justLoggedIn) {
      // Prevent multiple simultaneous auth checks
      if (!checkAuthRef.current) {
        console.log('[App] Calling checkAuth...')
        checkAuthRef.current = checkAuth().finally(() => {
          checkAuthRef.current = null
        })
      } else {
        console.log('[App] Auth check already in progress, skipping...')
      }
    } else {
      console.log('[App] Just logged in, skipping checkAuth')
      setIsCheckingAuth(false)
    }
  }, [])

  const checkAuth = async () => {
    console.log('[App] checkAuth started')
    try {
      console.log('[App] Calling getCurrentUser...')
      const user = await getCurrentUser()
      console.log('[App] getCurrentUser success:', user)
      setIsAuthenticated(true)
      setCurrentUsername(user.username)
    } catch (err: any) {
      console.error('[App] checkAuth error:', err)
      // If it's a 404 (session not found) or 401 (unauthorized), show login
      if (err.response?.status === 404 || err.response?.status === 401) {
        setIsAuthenticated(false)
        setCurrentUsername(null)
      } else if (err.response?.status === 500) {
        // Server error - treat as not authenticated, show login
        console.warn('[App] Auth check server error (500) - showing login')
        setIsAuthenticated(false)
        setCurrentUsername(null)
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('время ожидания')) {
        // Timeout - treat as not authenticated, show login
        console.warn('[App] Auth check timeout - showing login')
        setIsAuthenticated(false)
        setCurrentUsername(null)
      } else {
        // Other errors might be network issues, log them
        console.error('Auth check error:', err)
        setIsAuthenticated(false)
        setCurrentUsername(null)
      }
    } finally {
      console.log('[App] checkAuth finally - setting isCheckingAuth to false')
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth-finally',message:'checkAuth finally block',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      setIsCheckingAuth(false)
    }
  }

  const handleLoginSuccess = (sessionId: string, username: string) => {
    setJustLoggedIn(true)
    setIsAuthenticated(true)
    setCurrentUsername(username)
    setIsCheckingAuth(false)
    // Trigger auth status change event for Header
    window.dispatchEvent(new CustomEvent('auth-status-changed'))
    // Update session if needed
    if (window.location.search.includes('auth=success')) {
      window.history.replaceState({}, '', '/')
    }
  }

  useEffect(() => {
    // Check and clear cache if version changed
    const storedVersion = localStorage.getItem(VERSION_KEY)
    if (storedVersion !== APP_VERSION) {
      // Clear all app-related localStorage
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && (key.startsWith('chat-storage') || key.startsWith('settings-storage'))) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach(key => localStorage.removeItem(key))
      
      // Store new version
      localStorage.setItem(VERSION_KEY, APP_VERSION)
      
      // Force page reload to apply changes
      window.location.reload()
      return
    }
  }, [])

  useEffect(() => {
    // Apply theme
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])

  useEffect(() => {
    // Handle messages from file selector window
    const handleMessage = (event: MessageEvent) => {
      // Only accept messages from same origin
      if (event.origin !== window.location.origin) {
        return
      }
      
      if (event.data?.type === 'open-workspace-settings') {
        // Dispatch custom event to open workspace settings
        window.dispatchEvent(new CustomEvent('open-workspace-settings', {
          detail: { action: event.data.action }
        }))
      }
      
      if (event.data?.type === 'workspace-folder-selected') {
        // Folder was selected in separate window, reload workspace status
        getGoogleWorkspaceStatus()
          .then((status) => {
            setIntegrationStatus('googleWorkspace', {
              enabled: status.authenticated && status.folder_configured,
              authenticated: status.authenticated || false,
              folderConfigured: status.folder_configured || false,
              folderName: status.folder?.name,
              folderId: status.folder?.id,
            })
            setNotification({ 
              type: 'success', 
              message: `Рабочая папка "${status.folder?.name || ''}" успешно выбрана!` 
            })
            setTimeout(() => setNotification(null), 5000)
            // Trigger status reload in Header component
            window.dispatchEvent(new CustomEvent('integration-status-changed'))
          })
          .catch((error) => {
            console.error('Failed to reload workspace status after folder selection:', error)
            setNotification({ 
              type: 'error', 
              message: 'Не удалось обновить статус после выбора папки' 
            })
            setTimeout(() => setNotification(null), 5000)
          })
      }
      
      if (event.data?.type === 'onec-config-saved') {
        // 1C config was saved in separate window, reload integration status
        window.dispatchEvent(new CustomEvent('integration-status-changed'))
        setNotification({ 
          type: 'success', 
          message: 'Настройки 1С:Бухгалтерия успешно сохранены!' 
        })
        setTimeout(() => setNotification(null), 5000)
      }
      
      if (event.data?.type === 'projectlad-config-saved') {
        // ProjectLad config was saved in separate window, reload integration status
        window.dispatchEvent(new CustomEvent('integration-status-changed'))
        setNotification({ 
          type: 'success', 
          message: 'Настройки Project Lad успешно сохранены!' 
        })
        setTimeout(() => setNotification(null), 5000)
      }
    }
    
    window.addEventListener('message', handleMessage)
    return () => {
      window.removeEventListener('message', handleMessage)
    }
  }, [])

  useEffect(() => {
    // Handle OAuth callback
    const urlParams = new URLSearchParams(window.location.search)
    const calendarAuth = urlParams.get('calendar_auth')
    const gmailAuth = urlParams.get('gmail_auth')
    const sheetsAuth = urlParams.get('sheets_auth')
    const workspaceAuth = urlParams.get('workspace_auth')
    const error = urlParams.get('error')
    
    // Handle errors
    if (error) {
      const errorMessage = decodeURIComponent(error)
      setNotification({ type: 'error', message: `Ошибка авторизации: ${errorMessage}` })
      const newUrl = window.location.pathname
      window.history.replaceState({}, '', newUrl)
      setTimeout(() => setNotification(null), 5000)
      return
    }
    
    if (calendarAuth === 'success') {
      getGoogleCalendarStatus()
        .then((status) => {
          // Update status - enabled should be true if authenticated
          const isAuthenticated = status.authenticated || false
          setIntegrationStatus('googleCalendar', {
            enabled: isAuthenticated,
            authenticated: isAuthenticated,
          })
          setNotification({ type: 'success', message: 'Google Calendar успешно подключен!' })
          setTimeout(() => setNotification(null), 5000)
          // Trigger status reload in Header component
          window.dispatchEvent(new CustomEvent('integration-status-changed'))
        })
        .catch((error) => {
          console.error('Failed to load calendar status after OAuth:', error)
          setNotification({ type: 'error', message: 'Не удалось проверить статус интеграции' })
          setTimeout(() => setNotification(null), 5000)
        })
      
      const newUrl = window.location.pathname
      window.history.replaceState({}, '', newUrl)
    }
    
    if (gmailAuth === 'success') {
      getGmailStatus()
        .then((status) => {
          // Update status - enabled should be true if authenticated
          const isAuthenticated = status.authenticated || false
          setIntegrationStatus('gmail', {
            enabled: isAuthenticated,
            authenticated: isAuthenticated,
            email: status.email,
          })
          const emailText = status.email ? ` (${status.email})` : ''
          setNotification({ type: 'success', message: `Gmail успешно подключен${emailText}!` })
          setTimeout(() => setNotification(null), 5000)
          // Trigger status reload in Header component
          window.dispatchEvent(new CustomEvent('integration-status-changed'))
        })
        .catch((error) => {
          console.error('Failed to load Gmail status after OAuth:', error)
          setNotification({ type: 'error', message: 'Не удалось проверить статус интеграции Gmail' })
          setTimeout(() => setNotification(null), 5000)
        })
      
      const newUrl = window.location.pathname
      window.history.replaceState({}, '', newUrl)
    }
    
    if (sheetsAuth === 'success') {
      setNotification({ type: 'success', message: 'Google Sheets успешно подключен!' })
      setTimeout(() => setNotification(null), 5000)
      const newUrl = window.location.pathname
      window.history.replaceState({}, '', newUrl)
    }
    
    if (workspaceAuth === 'success') {
      getGoogleWorkspaceStatus()
        .then((status) => {
          const isAuthenticated = status.authenticated || false
          const folderConfigured = status.folder_configured || false
          // Set enabled to true only if both authenticated and folder configured
          setIntegrationStatus('googleWorkspace', {
            enabled: isAuthenticated && folderConfigured,
            authenticated: isAuthenticated,
            folderConfigured: folderConfigured,
            folderName: status.folder?.name,
            folderId: status.folder?.id,
          })
          
          if (folderConfigured) {
            setNotification({ type: 'success', message: 'Google Workspace успешно подключен!' })
          } else {
            // Trigger folder selector to show
            window.dispatchEvent(new CustomEvent('workspace-needs-folder-config'))
            setNotification({ type: 'success', message: 'Google Workspace подключен! Пожалуйста, выберите рабочую папку.' })
          }
          setTimeout(() => setNotification(null), 5000)
          // Trigger status reload in Header component
          window.dispatchEvent(new CustomEvent('integration-status-changed'))
        })
        .catch((error) => {
          console.error('Failed to load Workspace status after OAuth:', error)
          setNotification({ type: 'error', message: 'Не удалось проверить статус интеграции Google Workspace' })
          setTimeout(() => setNotification(null), 5000)
        })
      
      const newUrl = window.location.pathname
      window.history.replaceState({}, '', newUrl)
    }
  }, [setIntegrationStatus])

  if (isCheckingAuth) {return (
      <div className="h-screen w-full flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="text-slate-600 dark:text-slate-400">Загрузка...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginDialog onLoginSuccess={handleLoginSuccess} />
  }

  return (
    <div className="h-screen w-full flex flex-col bg-slate-50 dark:bg-slate-900">
      <Header />
      <div className="flex-1 overflow-hidden">
        <SplitLayout />
      </div>
      {/* Notification */}
      {notification && (
        <div className={`fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg ${
          notification.type === 'success' 
            ? 'bg-green-500 text-white' 
            : 'bg-red-500 text-white'
        }`}>
          <div className="flex items-center space-x-2">
            <span>{notification.message}</span>
            <button
              onClick={() => setNotification(null)}
              className="ml-2 hover:opacity-80"
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
