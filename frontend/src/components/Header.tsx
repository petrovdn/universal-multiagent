import { useState, useEffect, useRef } from 'react'
import { Settings, Calendar, Mail, ChevronDown, Folder } from 'lucide-react'
import { useSettingsStore } from '../store/settingsStore'
import { enableGoogleCalendar, disableGoogleCalendar, getGoogleCalendarStatus, enableGmail, disableGmail, getGmailStatus, enableGoogleWorkspace, disableGoogleWorkspace, getGoogleWorkspaceStatus } from '../services/api'
import { WorkspaceFolderSelector } from './WorkspaceFolderSelector'

export function Header() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isFolderSelectorOpen, setIsFolderSelectorOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { integrations, setIntegrationStatus } = useSettingsStore()

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
    
    return () => {
      window.removeEventListener('integration-status-changed', handleStatusChange)
      window.removeEventListener('workspace-needs-folder-config', handleWorkspaceNeedsFolderConfig)
    }
  }, [integrations.googleWorkspace.authenticated, integrations.googleWorkspace.folderConfigured])

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
          {integrations.googleWorkspace.enabled && (
            <div className="integration-badge workspace-badge">
              <Folder className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">Workspace</span>
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
              {/* Integrations only - убрали режим выполнения */}
              <div className="settings-section">
                <h3 className="settings-section-title">
                  Интеграции
                </h3>
                <div className="space-y-3">
                  {/* Gmail */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-3">
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
                    <div className="flex items-center space-x-3">
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

                  {/* Google Workspace */}
                  <div className="integration-row">
                    <div className="flex items-center space-x-3">
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
    </header>
  )
}
