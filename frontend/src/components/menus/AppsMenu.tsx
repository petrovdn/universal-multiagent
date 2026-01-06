import { useState, useEffect, useRef } from 'react'
import { Mail, Calendar, FileSpreadsheet, Folder, Database, Settings } from 'lucide-react'
import { useSettingsStore } from '../../store/settingsStore'
import { 
  enableGoogleCalendar, 
  disableGoogleCalendar, 
  getGoogleCalendarStatus,
  enableGmail, 
  disableGmail, 
  getGmailStatus,
  enableGoogleWorkspace, 
  disableGoogleWorkspace, 
  getGoogleWorkspaceStatus,
  enableGoogleSheets, 
  disableGoogleSheets, 
  getGoogleSheetsStatus,
  getOneCStatus,
  getProjectLadStatus,
  disableOneC,
  disableProjectLad
} from '../../services/api'
// WorkspaceFolderSelector removed - using separate window instead
// AppSettingsDialog removed - using separate windows instead

interface AppsMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function AppsMenu({ isOpen, onClose }: AppsMenuProps) {
  const [isLoading, setIsLoading] = useState(false)
  // All dialogs now open in separate windows, no need for state
  const menuRef = useRef<HTMLDivElement>(null)
  const { integrations, setIntegrationStatus } = useSettingsStore()

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node
      const isInside = menuRef.current?.contains(target)
      // Don't close if clicking on a button inside the menu
      const targetElement = target as HTMLElement
      if (targetElement?.closest('button')) {
        return
      }
      if (menuRef.current && !isInside) {
        onClose()
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      loadIntegrationStatus()
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  useEffect(() => {
    const handleStatusChange = () => {
      loadIntegrationStatus()
    }
    window.addEventListener('integration-status-changed', handleStatusChange)
    return () => {
      window.removeEventListener('integration-status-changed', handleStatusChange)
    }
  }, [])

  const openWorkspaceFolderSelectorWindow = () => {
    const width = 700
    const height = 600
    const left = (window.screen.width - width) / 2
    const top = (window.screen.height - height) / 2
    
    window.open(
      '/workspace-folder-selector.html',
      'workspaceFolderSelector',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    )
  }
  
  // Handle workspace-needs-folder-config event (after OAuth callback)
  useEffect(() => {
    const handleWorkspaceNeedsFolderConfig = () => {
      openWorkspaceFolderSelectorWindow()
    }
    
    window.addEventListener('workspace-needs-folder-config', handleWorkspaceNeedsFolderConfig)
    return () => {
      window.removeEventListener('workspace-needs-folder-config', handleWorkspaceNeedsFolderConfig)
    }
  }, [])

  const loadIntegrationStatus = async () => {
    try {
      const calendarStatus = await getGoogleCalendarStatus()
      setIntegrationStatus('googleCalendar', {
        enabled: calendarStatus.authenticated || false,
        authenticated: calendarStatus.authenticated || false,
      })
      
      const gmailStatus = await getGmailStatus()
      setIntegrationStatus('gmail', {
        enabled: gmailStatus.authenticated || false,
        authenticated: gmailStatus.authenticated || false,
        email: gmailStatus.email,
      })
      
      const workspaceStatus = await getGoogleWorkspaceStatus()
      const folderConfigured = workspaceStatus.folder_configured || false
      setIntegrationStatus('googleWorkspace', {
        enabled: workspaceStatus.authenticated && folderConfigured,
        authenticated: workspaceStatus.authenticated || false,
        folderConfigured: folderConfigured,
        folderName: workspaceStatus.folder?.name,
        folderId: workspaceStatus.folder?.id,
      })
      
      const sheetsStatus = await getGoogleSheetsStatus()
      setIntegrationStatus('googleSheets', {
        enabled: sheetsStatus.authenticated || false,
        authenticated: sheetsStatus.authenticated || false,
      })
      
      const onecStatus = await getOneCStatus()
      setIntegrationStatus('onec', {
        enabled: onecStatus.configured || false,
        authenticated: onecStatus.configured || false,
      })
      
      const projectladStatus = await getProjectLadStatus()
      setIntegrationStatus('projectlad', {
        enabled: projectladStatus.configured || false,
        authenticated: projectladStatus.configured || false,
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
          window.location.href = result.auth_url
          return
        } else {
          setIntegrationStatus('googleCalendar', { enabled: true, authenticated: true })
          setIsLoading(false)
        }
      } else {
        await disableGoogleCalendar()
        setIntegrationStatus('googleCalendar', { enabled: false, authenticated: false })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Calendar:', error)
      alert(error.message || 'Не удалось изменить настройки')
      setIsLoading(false)
    }
  }

  const handleGmailToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGmail()
        if (result.status === 'oauth_required' && result.auth_url) {
          window.location.href = result.auth_url
          return
        } else {
          setIntegrationStatus('gmail', { enabled: true, authenticated: true, email: result.email })
          setIsLoading(false)
        }
      } else {
        await disableGmail()
        setIntegrationStatus('gmail', { enabled: false, authenticated: false, email: undefined })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Gmail:', error)
      alert(error.message || 'Не удалось изменить настройки')
      setIsLoading(false)
    }
  }

  const handleWorkspaceToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGoogleWorkspace()
        if (result.status === 'oauth_required' && result.auth_url) {
          window.location.href = result.auth_url
          return
        } else {
          if (result.folder_configured) {
            setIntegrationStatus('googleWorkspace', {
              enabled: true,
              authenticated: true,
              folderConfigured: true,
            })
            setIsLoading(false)
          } else {
            setIntegrationStatus('googleWorkspace', {
              enabled: false,
              authenticated: true,
              folderConfigured: false,
            })
            setIsLoading(false)
            openWorkspaceFolderSelectorWindow()
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
      console.error('Failed to toggle Workspace:', error)
      alert(error.message || 'Не удалось изменить настройки')
      setIsLoading(false)
    }
  }

  const handleSheetsToggle = async (enabled: boolean) => {
    setIsLoading(true)
    try {
      if (enabled) {
        const result = await enableGoogleSheets()
        if (result.status === 'oauth_required' && result.auth_url) {
          window.location.href = result.auth_url
          return
        } else {
          setIntegrationStatus('googleSheets', { enabled: true, authenticated: true })
          setIsLoading(false)
        }
      } else {
        await disableGoogleSheets()
        setIntegrationStatus('googleSheets', { enabled: false, authenticated: false })
        setIsLoading(false)
      }
    } catch (error: any) {
      console.error('Failed to toggle Sheets:', error)
      alert(error.message || 'Не удалось изменить настройки')
      setIsLoading(false)
    }
  }

  const openOneCSettingsWindow = () => {
    const width = 600
    const height = 650
    const left = (window.screen.width - width) / 2
    const top = (window.screen.height - height) / 2
    
    window.open(
      '/onec-settings.html',
      'onecSettings',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    )
  }

  const handleOneCToggle = async (e?: React.MouseEvent) => {
    
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    if (isLoading) {
      return
    }
    
    setIsLoading(true)
    try {
      if (integrations.onec.authenticated) {
        // If configured, disable it using disable endpoint
        await disableOneC()
        setIntegrationStatus('onec', {
          enabled: false,
          authenticated: false,
        })
        await loadIntegrationStatus()
        setIsLoading(false)
      } else {
        setIsLoading(false)
        openOneCSettingsWindow()
      }
    } catch (error: any) {
      console.error('Failed to toggle 1C:', error)
      alert(error.message || 'Не удалось изменить настройки приложения')
      setIsLoading(false)
    }
  }

  // 1C save/test handlers removed - now handled in separate window

  // ProjectLad config loading removed - now handled in separate window

  const openProjectLadSettingsWindow = () => {
    const width = 600
    const height = 550
    const left = (window.screen.width - width) / 2
    const top = (window.screen.height - height) / 2
    
    window.open(
      '/projectlad-settings.html',
      'projectladSettings',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    )
  }

  const handleProjectLadToggle = async (e?: React.MouseEvent) => {
    
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    if (isLoading) {
      return
    }
    
    setIsLoading(true)
    try {
      if (integrations.projectlad.authenticated) {
        // If configured, disable it using disable endpoint
        await disableProjectLad()
        setIntegrationStatus('projectlad', {
          enabled: false,
          authenticated: false,
        })
        await loadIntegrationStatus()
        setIsLoading(false)
      } else {
        setIsLoading(false)
        openProjectLadSettingsWindow()
      }
    } catch (error: any) {
      console.error('Failed to toggle ProjectLad:', error)
      alert(error.message || 'Не удалось изменить настройки приложения')
      setIsLoading(false)
    }
  }

  // All configuration handling removed - now handled in separate windows

  if (!isOpen) return null


  return (
    <>
      <div className="apps-menu-dropdown" ref={menuRef}>
        <div className="apps-menu-header">
          <h3 className="apps-menu-title">Приложения</h3>
        </div>
        
        <div className="apps-menu-list">
          {/* Gmail */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.gmail.authenticated ? 'active' : ''}`}>
                <Mail className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">Gmail</div>
                <div className="app-status">
                  {integrations.gmail.authenticated 
                    ? (integrations.gmail.email || 'Подключено')
                    : 'Не подключено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              <button
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleGmailToggle(!integrations.gmail.authenticated)
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider gmail-toggle ${integrations.gmail.authenticated ? 'active' : ''}`}></div>
              </button>
            </div>
          </div>

          {/* Calendar */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.googleCalendar.authenticated ? 'active' : ''}`}>
                <Calendar className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">Google Calendar</div>
                <div className="app-status">
                  {integrations.googleCalendar.authenticated ? 'Подключено' : 'Не подключено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              <button
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleCalendarToggle(!integrations.googleCalendar.authenticated)
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider calendar-toggle ${integrations.googleCalendar.authenticated ? 'active' : ''}`}></div>
              </button>
            </div>
          </div>

          {/* Sheets */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.googleSheets.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.googleSheets.authenticated ? '#0f9d58' : '#94a3b8', color: 'white' }}>
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">Google Sheets</div>
                <div className="app-status">
                  {integrations.googleSheets.authenticated ? 'Подключено' : 'Не подключено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              <button
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleSheetsToggle(!integrations.googleSheets.authenticated)
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider ${integrations.googleSheets.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.googleSheets.authenticated ? '#0f9d58' : '#cbd5e1' }}></div>
              </button>
            </div>
          </div>

          {/* Workspace */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.googleWorkspace.enabled ? 'active' : ''}`}>
                <Folder className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">Google Workspace</div>
                <div className="app-status">
                  {integrations.googleWorkspace.authenticated 
                    ? (integrations.googleWorkspace.folderConfigured
                        ? (integrations.googleWorkspace.folderName || 'Папка настроена')
                        : 'Требуется выбор папки')
                    : 'Не подключено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              {integrations.googleWorkspace.enabled && (
                <button 
                  className="app-settings-btn" 
                  title="Настройки"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    openWorkspaceFolderSelectorWindow()
                  }}
                  type="button"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleWorkspaceToggle(!integrations.googleWorkspace.enabled)
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider workspace-toggle ${integrations.googleWorkspace.enabled ? 'active' : ''}`}></div>
              </button>
            </div>
          </div>

          {/* 1C */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.onec.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.onec.authenticated ? '#1c64f2' : '#94a3b8', color: 'white' }}>
                <Database className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">1С:Бухгалтерия</div>
                <div className="app-status">
                  {integrations.onec.authenticated ? 'Настроено' : 'Не настроено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              {integrations.onec.authenticated && (
                <button 
                  className="app-settings-btn" 
                  title="Настройки"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    openOneCSettingsWindow()
                  }}
                  type="button"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleOneCToggle(e)
                }}
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider onec-toggle ${integrations.onec.authenticated ? 'active' : ''}`}></div>
              </button>
            </div>
          </div>

          {/* Project Lad */}
          <div className="app-menu-item">
            <div className="app-menu-item-left">
              <div className={`app-icon ${integrations.projectlad.authenticated ? 'active' : ''}`} style={{ backgroundColor: integrations.projectlad.authenticated ? '#8b5cf6' : '#94a3b8', color: 'white' }}>
                <Folder className="w-4 h-4" />
              </div>
              <div className="app-menu-item-info">
                <div className="app-name">Project Lad</div>
                <div className="app-status">
                  {integrations.projectlad.authenticated ? 'Настроено' : 'Не настроено'}
                </div>
              </div>
            </div>
            <div className="app-menu-item-right">
              {integrations.projectlad.authenticated && (
                <button 
                  className="app-settings-btn" 
                  title="Настройки"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    openProjectLadSettingsWindow()
                  }}
                  type="button"
                >
                  <Settings className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleProjectLadToggle(e)
                }}
                onMouseDown={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                disabled={isLoading}
                className="toggle-button"
                type="button"
              >
                <div className={`toggle-slider projectlad-toggle ${integrations.projectlad.authenticated ? 'active' : ''}`}></div>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* All dialogs removed - using separate windows instead */}
    </>
  )
}
