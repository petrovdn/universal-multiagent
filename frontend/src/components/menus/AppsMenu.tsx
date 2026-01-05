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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleCalendarToggle:entry',message:'handleCalendarToggle called',data:{enabled,currentAuthenticated:integrations.googleCalendar.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleGmailToggle:entry',message:'handleGmailToggle called',data:{enabled,currentAuthenticated:integrations.gmail.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleWorkspaceToggle:entry',message:'handleWorkspaceToggle called',data:{enabled,currentEnabled:integrations.googleWorkspace.enabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleSheetsToggle:entry',message:'handleSheetsToggle called',data:{enabled,currentAuthenticated:integrations.googleSheets.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:entry',message:'handleOneCToggle called',data:{hasEvent:!!e,isLoading,onecAuthenticated:integrations.onec.authenticated,onecEnabled:integrations.onec.enabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    if (isLoading) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:early_return',message:'Early return due to isLoading',data:{isLoading},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      return
    }
    
    setIsLoading(true)
    try {
      if (integrations.onec.authenticated) {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:disable_path',message:'Disabling 1C (authenticated=true)',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        // If configured, disable it using disable endpoint
        await disableOneC()
        setIntegrationStatus('onec', {
          enabled: false,
          authenticated: false,
        })
        await loadIntegrationStatus()
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:disable_complete',message:'1C disabled successfully',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
      } else {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:open_window_path',message:'Opening 1C settings window (authenticated=false)',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        setIsLoading(false)
        openOneCSettingsWindow()
      }
    } catch (error: any) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleOneCToggle:error',message:'Error in handleOneCToggle',data:{error:error?.message,errorType:error?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:entry',message:'handleProjectLadToggle called',data:{hasEvent:!!e,isLoading,projectladAuthenticated:integrations.projectlad.authenticated,projectladEnabled:integrations.projectlad.enabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    
    if (isLoading) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:early_return',message:'Early return due to isLoading',data:{isLoading},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      return
    }
    
    setIsLoading(true)
    try {
      if (integrations.projectlad.authenticated) {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:disable_path',message:'Disabling ProjectLad (authenticated=true)',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        // If configured, disable it using disable endpoint
        await disableProjectLad()
        setIntegrationStatus('projectlad', {
          enabled: false,
          authenticated: false,
        })
        await loadIntegrationStatus()
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:disable_complete',message:'ProjectLad disabled successfully',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
      } else {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:open_window_path',message:'Opening ProjectLad settings window (authenticated=false)',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        setIsLoading(false)
        openProjectLadSettingsWindow()
      }
    } catch (error: any) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:handleProjectLadToggle:error',message:'Error in handleProjectLadToggle',data:{error:error?.message,errorType:error?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      console.error('Failed to toggle ProjectLad:', error)
      alert(error.message || 'Не удалось изменить настройки приложения')
      setIsLoading(false)
    }
  }

  // All configuration handling removed - now handled in separate windows

  if (!isOpen) return null

  // #region agent log
  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:render',message:'AppsMenu rendering',data:{isOpen,onecAuthenticated:integrations.onec.authenticated,projectladAuthenticated:integrations.projectlad.authenticated,isLoading},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion

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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:gmail_toggle_button:mousedown',message:'Gmail toggle button mousedown',data:{isLoading,gmailAuthenticated:integrations.gmail.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:gmail_toggle_button:click',message:'Gmail toggle button clicked',data:{isLoading,gmailAuthenticated:integrations.gmail.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:calendar_toggle_button:mousedown',message:'Calendar toggle button mousedown',data:{isLoading,calendarAuthenticated:integrations.googleCalendar.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:calendar_toggle_button:click',message:'Calendar toggle button clicked',data:{isLoading,calendarAuthenticated:integrations.googleCalendar.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:sheets_toggle_button:mousedown',message:'Sheets toggle button mousedown',data:{isLoading,sheetsAuthenticated:integrations.googleSheets.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:sheets_toggle_button:click',message:'Sheets toggle button clicked',data:{isLoading,sheetsAuthenticated:integrations.googleSheets.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:workspace_settings_button:mousedown',message:'Workspace settings button mousedown',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:workspace_settings_button:click',message:'Workspace settings button clicked',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:workspace_toggle_button:mousedown',message:'Workspace toggle button mousedown',data:{isLoading,workspaceEnabled:integrations.googleWorkspace.enabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                }}
                onClick={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:workspace_toggle_button:click',message:'Workspace toggle button clicked',data:{isLoading,workspaceEnabled:integrations.googleWorkspace.enabled},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:onec_settings_button:mousedown',message:'1C settings button mousedown',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:onec_settings_button:click',message:'1C settings button clicked',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:onec_toggle_button:click',message:'1C toggle button clicked',data:{isLoading,onecAuthenticated:integrations.onec.authenticated,targetTagName:e.target?.tagName,targetClassName:(e.target as HTMLElement)?.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                  handleOneCToggle(e)
                }}
                onMouseDown={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:onec_toggle_button:mousedown',message:'1C toggle button mousedown',data:{isLoading,onecAuthenticated:integrations.onec.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:projectlad_settings_button:mousedown',message:'ProjectLad settings button mousedown',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onClick={(e) => {
                    // #region agent log
                    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:projectlad_settings_button:click',message:'ProjectLad settings button clicked',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                    // #endregion
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
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:projectlad_toggle_button:click',message:'ProjectLad toggle button clicked',data:{isLoading,projectladAuthenticated:integrations.projectlad.authenticated,targetTagName:e.target?.tagName,targetClassName:(e.target as HTMLElement)?.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
                  e.preventDefault()
                  e.stopPropagation()
                  handleProjectLadToggle(e)
                }}
                onMouseDown={(e) => {
                  // #region agent log
                  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppsMenu.tsx:projectlad_toggle_button:mousedown',message:'ProjectLad toggle button mousedown',data:{isLoading,projectladAuthenticated:integrations.projectlad.authenticated},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'F'})}).catch(()=>{});
                  // #endregion
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
