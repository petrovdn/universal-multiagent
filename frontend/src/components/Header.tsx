import { useState, useEffect, useRef } from 'react'
import { Settings, Calendar, Mail, ChevronDown, Folder, LogOut, Database, FileSpreadsheet } from 'lucide-react'
import { useSettingsStore } from '../store/settingsStore'
import { enableGoogleCalendar, disableGoogleCalendar, getGoogleCalendarStatus, enableGmail, disableGmail, getGmailStatus, enableGoogleWorkspace, disableGoogleWorkspace, getGoogleWorkspaceStatus, enableGoogleSheets, disableGoogleSheets, getGoogleSheetsStatus, logout, getCurrentUser, getOneCStatus, getProjectLadStatus } from '../services/api'
import { WorkspaceFolderSelector } from './WorkspaceFolderSelector'
import { OneCSettingsDialog } from './OneCSettingsDialog'
import { ProjectLadSettingsDialog } from './ProjectLadSettingsDialog'

export function Header() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false)
  const [isOneCDialogOpen, setIsOneCDialogOpen] = useState(false)
  const [isProjectLadDialogOpen, setIsProjectLadDialogOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { integrations, setIntegrationStatus, debugMode, setDebugMode } = useSettingsStore()
  const [currentUser, setCurrentUser] = useState<string | null>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsSettingsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle messages from file selector window to open workspace settings
  useEffect(() => {
    const handleOpenWorkspaceSettings = (event: CustomEvent) => {
      // Open settings dropdown
      setIsSettingsOpen(true)
      // Open folder selector if action is to configure folder
      if (event.detail?.action === 'configure-folder') {
        // Small delay to ensure dropdown is open
        setTimeout(() => {
          setIsFolderSelectorOpen(true)
        }, 100)
      }
    }

    window.addEventListener('open-workspace-settings', handleOpenWorkspaceSettings as EventListener)
    return () => {
      window.removeEventListener('open-workspace-settings', handleOpenWorkspaceSettings as EventListener)
    }
  }, [])

  // Load integration status on mount and when status changes
  useEffect(() => {
    loadIntegrationStatus()
    
    // Listen for status change events from OAuth callback
    const handleStatusChange = () => {
      loadIntegrationStatus()
    }
    window.addEventListener('integration-status-changed', handleStatusChange)
    
    // Listen for workspace folder config needed event
    const handleWorkspaceNeedsFolderConfig = () => {
      // Check if workspace is authenticated but folder not configured
      if (integrations.googleWorkspace.authenticated && !integrations.googleWorkspace.folderConfigured) {
        setIsFolderSelectorOpen(true)
      }
    }
    window.addEventListener('workspace-needs-folder-config', handleWorkspaceNeedsFolderConfig)
    
    // Check for OAuth callback parameters in URL
    const urlParams = new URLSearchParams(window.location.search)
    const sheetsAuth = urlParams.get('sheets_auth')
    if (sheetsAuth === 'success' || sheetsAuth === 'already_enabled') {
      // Reload integration status after OAuth success
      loadIntegrationStatus()
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname)
      // Dispatch event to update UI
      window.dispatchEvent(new Event('integration-status-changed'))
    }
    
    return () => {
      window.removeEventListener('integration-status-changed', handleStatusChange)
      window.removeEventListener('workspace-needs-folder-config', handleWorkspaceNeedsFolderConfig)
    }
  }, [integrations.googleWorkspace.authenticated, integrations.googleWorkspace.folderConfigured])

  // Load current user on mount and listen for auth changes
  useEffect(() => {
    loadCurrentUser()
    
    // Listen for auth status changes
    const handleAuthChange = () => {
      loadCurrentUser()
    }
    window.addEventListener('auth-status-changed', handleAuthChange)
    
    return () => {
      window.removeEventListener('auth-status-changed', handleAuthChange)
    }
  }, [])

  const loadCurrentUser = async () => {
    try {
      const user = await getCurrentUser()
      console.log('Loaded current user:', user.username)
      setCurrentUser(user.username)
    } catch (err) {
      console.log('Failed to load current user:', err)
      setCurrentUser(null)
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
      setCurrentUser(null)
      window.location.href = '/' // Reload to show login
    } catch (err) {
      console.error('Logout error:', err)
    }
  }

  const loadIntegrationStatus = async () => {
    try {
      const calendarStatus = await getGoogleCalendarStatus()
      const calendarAuthenticated = calendarStatus.authenticated || false
      setIntegrationStatus('googleCalendar', {
        enabled: calendarAuthenticated,
        authenticated: calendarAuthenticated,
      })
      
      const gmailStatus = await getGmailStatus()
      const gmailAuthenticated = gmailStatus.authenticated || false
      setIntegrationStatus('gmail', {
        enabled: gmailAuthenticated,
        authenticated: gmailAuthenticated,
        email: gmailStatus.email,
      })
      
      const workspaceStatus = await getGoogleWorkspaceStatus()
      const workspaceAuthenticated = workspaceStatus.authenticated || false
      const folderConfigured = workspaceStatus.folder_configured || false
      setIntegrationStatus('googleWorkspace', {
        enabled: workspaceAuthenticated && folderConfigured,
        authenticated: workspaceAuthenticated,
        folderConfigured: folderConfigured,
        folderName: workspaceStatus.folder?.name,
        folderId: workspaceStatus.folder?.id,
      })
      
      const sheetsStatus = await getGoogleSheetsStatus()
      const sheetsAuthenticated = sheetsStatus.authenticated || false
      setIntegrationStatus('googleSheets', {
        enabled: sheetsAuthenticated,
        authenticated: sheetsAuthenticated,
      })
      
      const onecStatus = await getOneCStatus()
      const onecConfigured = onecStatus.configured || false
      setIntegrationStatus('onec', {
        enabled: onecConfigured,
        authenticated: onecConfigured,
      })
      
      const projectladStatus = await getProjectLadStatus()
      const projectladConfigured = projectladStatus.configured || false
      setIntegrationStatus('projectlad', {
        enabled: projectladConfigured,
        authenticated: projectladConfigured,
      })
    } catch (error) {
      console.error('Failed to load integration status:', error)
    }
  }

  const handleCalendarToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGoogleCalendar()
        if (result.status === 'oauth_required' && result.auth_url) {
          // Redirect directly to Google OAuth page instead of popup
          window.location.href = result.auth_url
          return // Don't set loading to false, as we're redirecting
        } else {
          // Already authenticated
          setIntegrationStatus('googleCalendar', { enabled: true, authenticated: true })
          setIsLoading(false)
        }
      } else {
        await disableGoogleCalendar()
        setIntegrationStatus('googleCalendar', { enabled: false, authenticated: false })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Calendar integration:', error)
      alert(error.message || 'Не удалось изменить настройки интеграции')
      setIsLoading(false)
    }
  }

  const handleGmailToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGmail()
        if (result.status === 'oauth_required' && result.auth_url) {
          // Redirect directly to Google OAuth page instead of popup
          window.location.href = result.auth_url
          return // Don't set loading to false, as we're redirecting
        } else {
          // Already authenticated
          setIntegrationStatus('gmail', { enabled: true, authenticated: true, email: result.email })
          setIsLoading(false)
        }
      } else {
        await disableGmail()
        setIntegrationStatus('gmail', { enabled: false, authenticated: false, email: undefined })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Gmail integration:', error)
      alert(error.message || 'Не удалось изменить настройки интеграции Gmail')
      setIsLoading(false)
    }
  }

  const handleWorkspaceToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGoogleWorkspace()
        if (result.status === 'oauth_required' && result.auth_url) {
          // Redirect directly to Google OAuth page instead of popup
          window.location.href = result.auth_url
          return // Don't set loading to false, as we're redirecting
        } else {
          // Already authenticated - check if folder is configured
          if (result.folder_configured) {
            setIntegrationStatus('googleWorkspace', {
              enabled: true,
              authenticated: true,
              folderConfigured: true,
            })
            setIsLoading(false)
          } else {
            // Need to configure folder
            setIntegrationStatus('googleWorkspace', {
              enabled: false,
              authenticated: true,
              folderConfigured: false,
            })
            setIsLoading(false)
            setIsFolderSelectorOpen(true)
          }
        }
      } else {
        await disableGoogleWorkspace()
        setIntegrationStatus('googleWorkspace', {
          enabled: false,
          authenticated: false,
          folderConfigured: false,
        })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Workspace integration:', error)
      alert(error.message || 'Не удалось изменить настройки интеграции Google Workspace')
      setIsLoading(false)
    }
  }

  const handleFolderSelected = async () => {
    setIsFolderSelectorOpen(false)
    // Reload status to get updated folder configuration
    const workspaceStatus = await getGoogleWorkspaceStatus()
    const workspaceAuthenticated = workspaceStatus.authenticated || false
    const folderConfigured = workspaceStatus.folder_configured || false
    
    // Update status and ensure enabled is true when folder is configured
    setIntegrationStatus('googleWorkspace', {
      enabled: workspaceAuthenticated && folderConfigured,
      authenticated: workspaceAuthenticated,
      folderConfigured: folderConfigured,
      folderName: workspaceStatus.folder?.name,
      folderId: workspaceStatus.folder?.id,
    })
  }

  const handleSheetsToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGoogleSheets()
        if (result.status === 'oauth_required' && result.auth_url) {
          // Redirect directly to Google OAuth page instead of popup
          window.location.href = result.auth_url
          return // Don't set loading to false, as we're redirecting
        } else {
          // Already authenticated
          setIntegrationStatus('googleSheets', { enabled: true, authenticated: true })
          setIsLoading(false)
        }
      } else {
        await disableGoogleSheets()
        setIntegrationStatus('googleSheets', { enabled: false, authenticated: false })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Sheets integration:', error)
      alert(error.message || 'Не удалось изменить настройки интеграции Google Sheets')
      setIsLoading(false)
    }
  }

  const handleOneCConfigSaved = async () => {
    const onecStatus = await getOneCStatus()
    const onecConfigured = onecStatus.configured || false
    setIntegrationStatus('onec', {
      enabled: onecConfigured,
      authenticated: onecConfigured,
    })
  }


  return (
    <header className="compact-header">
      <div className="compact-header-content">
        {/* Active integrations badges */}
        <div className="integrations-badges-container">
          {integrations.gmail.authenticated && (
            <div className="integration-badge gmail-badge">
              <Mail className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Gmail</span>
            </div>
          )}
          {integrations.googleCalendar.authenticated && (
            <div className="integration-badge calendar-badge">
              <Calendar className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Calendar</span>
            </div>
          )}
          {integrations.googleSheets.authenticated && (
            <div className="integration-badge" style={{ backgroundColor: '#0f9d58', color: 'white' }}>
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Sheets</span>
            </div>
          )}
          {integrations.googleWorkspace.enabled && (
            <div className="integration-badge workspace-badge">
              <Folder className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Workspace</span>
            </div>
          )}
          {integrations.onec.authenticated && (
            <div className="integration-badge" style={{ backgroundColor: '#1c64f2', color: 'white' }}>
              <Database className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">1С</span>
            </div>
          )}
        </div>

        {/* Settings dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className="settings-button"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm">Настройки</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${isSettingsOpen ? 'rotate-180' : ''}`} />
          </button>

          {isSettingsOpen && (
            <div className="settings-dropdown">
              {/* Integrations */}
              <div className="settings-section">
                <h3 className="settings-section-title">
                  Интеграции
                </h3>
                <div className="space-y-2">
                  {/* Gmail */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className="integration-icon gmail-icon">
                        <Mail className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="integration-name">Gmail</div>
                        <div className="integration-status">
                          {integrations.gmail.authenticated 
                            ? (integrations.gmail.email || 'Подключено')
                            : 'Не подключено'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleGmailToggle(!integrations.gmail.authenticated)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider gmail-toggle ${integrations.gmail.authenticated ? 'active' : ''}`}></div>
                    </button>
                  </div>

                  {/* Calendar */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className="integration-icon calendar-icon">
                        <Calendar className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="integration-name">Google Calendar</div>
                        <div className="integration-status">
                          {integrations.googleCalendar.authenticated ? 'Подключено' : 'Не подключено'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleCalendarToggle(!integrations.googleCalendar.authenticated)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider calendar-toggle ${integrations.googleCalendar.authenticated ? 'active' : ''}`}></div>
                    </button>
                  </div>

                  {/* Google Sheets */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className="integration-icon" style={{ backgroundColor: integrations.googleSheets.authenticated ? '#0f9d58' : '#94a3b8', color: 'white' }}>
                        <FileSpreadsheet className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="integration-name">Google Sheets</div>
                        <div className="integration-status">
                          {integrations.googleSheets.authenticated ? 'Подключено' : 'Не подключено'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleSheetsToggle(!integrations.googleSheets.authenticated)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider ${integrations.googleSheets.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.googleSheets.authenticated ? '#0f9d58' : '#cbd5e1' }}></div>
                    </button>
                  </div>

                  {/* Google Workspace */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className={`integration-icon workspace-icon ${integrations.googleWorkspace.enabled ? 'active' : ''}`}>
                        <Folder className="w-4 h-4" />
                      </div>
                      <div className="flex-1">
                        <div className="integration-name">Google Workspace</div>
                        <div className="integration-status">
                          {integrations.googleWorkspace.authenticated 
                            ? (integrations.googleWorkspace.folderConfigured
                                ? (integrations.googleWorkspace.folderName || 'Папка настроена')
                                : 'Требуется выбор папки')
                            : 'Не подключено'}
                        </div>
                        {integrations.googleWorkspace.enabled && (
                          <button
                            onClick={() => setIsFolderSelectorOpen(true)}
                            className="text-xs text-blue-600 hover:text-blue-700 mt-1"
                          >
                            Изменить папку
                          </button>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleWorkspaceToggle(!integrations.googleWorkspace.enabled)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider workspace-toggle ${integrations.googleWorkspace.enabled ? 'active' : ''}`}></div>
                    </button>
                  </div>

                  {/* 1C:Бухгалтерия */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className={`integration-icon ${integrations.onec.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.onec.authenticated ? '#1c64f2' : '#94a3b8', color: 'white' }}>
                        <Database className="w-4 h-4" />
                      </div>
                      <div className="flex-1">
                        <div className="integration-name">1С:Бухгалтерия</div>
                        <div className="integration-status">
                          {integrations.onec.authenticated ? 'Настроено' : 'Не настроено'}
                        </div>
                        {integrations.onec.authenticated && (
                          <button
                            onClick={() => setIsOneCDialogOpen(true)}
                            className="text-xs text-blue-600 hover:text-blue-700 mt-1"
                          >
                            Изменить настройки
                          </button>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => setIsOneCDialogOpen(true)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider ${integrations.onec.authenticated ? 'active' : ''}`}></div>
                    </button>
                  </div>

                  {/* Project Lad */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-2">
                      <div className={`integration-icon ${integrations.projectlad.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.projectlad.authenticated ? '#8b5cf6' : '#94a3b8', color: 'white' }}>
                        <Folder className="w-4 h-4" />
                      </div>
                      <div className="flex-1">
                        <div className="integration-name">Project Lad</div>
                        <div className="integration-status">
                          {integrations.projectlad.authenticated ? 'Настроено' : 'Не настроено'}
                        </div>
                        {integrations.projectlad.authenticated && (
                          <button
                            onClick={() => setIsProjectLadDialogOpen(true)}
                            className="text-xs text-blue-600 hover:text-blue-700 mt-1"
                          >
                            Изменить настройки
                          </button>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => setIsProjectLadDialogOpen(true)}
                      disabled={isLoading}
                      className="toggle-button"
                    >
                      <div className={`toggle-slider ${integrations.projectlad.authenticated ? 'active' : ''}`}></div>
                    </button>
                  </div>
                </div>
              </div>

              {/* Account section */}
              <div className="settings-section">
                <h3 className="settings-section-title">
                  Аккаунт
                </h3>
                <div className="space-y-2">
                  {currentUser ? (
                    <>
                      <div className="integration-row">
                        <div className="flex items-center space-x-2">
                          <div>
                            <div className="integration-name">Пользователь</div>
                            <div className="integration-status">
                              {currentUser}
                            </div>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors border border-red-200 dark:border-red-800"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Выйти</span>
                      </button>
                    </>
                  ) : (
                    <div className="text-xs text-slate-500 dark:text-slate-400 py-1">
                      Не авторизован
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Workspace Folder Selector */}
      <WorkspaceFolderSelector
        isOpen={isFolderSelectorOpen}
        onClose={() => setIsFolderSelectorOpen(false)}
        onFolderSelected={handleFolderSelected}
      />
      
      {/* 1C Settings Dialog */}
      <OneCSettingsDialog
        isOpen={isOneCDialogOpen}
        onClose={() => setIsOneCDialogOpen(false)}
        onConfigSaved={handleOneCConfigSaved}
      />
      
      {/* Project Lad Settings Dialog */}
      <ProjectLadSettingsDialog
        isOpen={isProjectLadDialogOpen}
        onClose={() => setIsProjectLadDialogOpen(false)}
        onConfigSaved={async () => {
          await loadIntegrationStatus()
        }}
      />
    </header>
  )
}

