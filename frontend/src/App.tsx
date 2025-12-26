import { useEffect, useState } from 'react'
import { ChatInterface } from './components/ChatInterface'
import { Header } from './components/Header'
import { useSettingsStore } from './store/settingsStore'
import { getGoogleCalendarStatus, getGmailStatus, getGoogleWorkspaceStatus } from './services/api'

// App version - increment to clear cache
const APP_VERSION = '5.0.0'
const VERSION_KEY = 'app-version'

function App() {
  const { theme, setIntegrationStatus } = useSettingsStore()
  const [notification, setNotification] = useState<{ type: 'success' | 'error', message: string } | null>(null)

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
