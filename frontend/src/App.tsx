import { useEffect, useState } from 'react'
import { ChatInterface } from './components/ChatInterface'
import { Header } from './components/Header'
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

  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:useEffect',message:'App mount - starting auth check',data:{justLoggedIn},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B,C,E'})}).catch(()=>{});
    // #endregion
    // Check authentication status only if not just logged in
    if (!justLoggedIn) {
      checkAuth()
    } else {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:useEffect',message:'Skipping auth check - just logged in',data:{justLoggedIn},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      setIsCheckingAuth(false)
    }
  }, [])

  const checkAuth = async () => {
    // #region agent log
    const checkAuthStartTime = Date.now()
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth',message:'checkAuth started',data:{startTime:checkAuthStartTime},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,C,D'})}).catch(()=>{});
    // #endregion
    try {
      // #region agent log
      const getUserStartTime = Date.now()
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth',message:'Calling getCurrentUser',data:{getUserStartTime},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,D'})}).catch(()=>{});
      // #endregion
      const user = await getCurrentUser()
      // #region agent log
      const getUserEndTime = Date.now()
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth',message:'getCurrentUser success',data:{username:user.username,getUserDuration:getUserEndTime-getUserStartTime},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,D'})}).catch(()=>{});
      // #endregion
      setIsAuthenticated(true)
      setCurrentUsername(user.username)
    } catch (err: any) {
      // #region agent log
      const getUserEndTime = Date.now()
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth',message:'getCurrentUser error',data:{error:err.message,status:err.response?.status,getUserDuration:getUserEndTime-checkAuthStartTime},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,C,D'})}).catch(()=>{});
      // #endregion
      // If it's a 404 (session not found), it's fine - user just needs to login
      if (err.response?.status === 404 || err.response?.status === 401) {
        setIsAuthenticated(false)
        setCurrentUsername(null)
      } else {
        // Other errors might be network issues, log them
        console.error('Auth check error:', err)
        setIsAuthenticated(false)
        setCurrentUsername(null)
      }
    } finally {
      // #region agent log
      const checkAuthEndTime = Date.now()
      fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:checkAuth',message:'checkAuth completed',data:{totalDuration:checkAuthEndTime-checkAuthStartTime,isCheckingAuthWillBeSetTo:false},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,C,D'})}).catch(()=>{});
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

  if (isCheckingAuth) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4160cfcc-021e-4a6f-8f55-d3d9e039c6e3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:render',message:'Showing loading screen',data:{isCheckingAuth,justLoggedIn,isAuthenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B,C,D'})}).catch(()=>{});
    // #endregion
    return (
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
        <ChatInterface />
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
