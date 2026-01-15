import { useState, useEffect } from 'react'
import { Smartphone, Settings, HelpCircle, User, ChevronDown } from 'lucide-react'
import { Logo } from './Logo'
import { ProfileMenu } from './menus/ProfileMenu'
import { AppsMenu } from './menus/AppsMenu'
import { SettingsMenu } from './menus/SettingsMenu'
import { HelpMenu } from './menus/HelpMenu'

export function Header() {
  const [activeMenu, setActiveMenu] = useState<'profile' | 'apps' | 'settings' | 'help' | null>(null)

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as HTMLElement
      if (!target.closest('.header-menu-button') && 
          !target.closest('.menu-dropdown') && 
          !target.closest('.help-menu-dropdown') &&
          !target.closest('.settings-menu-dropdown') &&
          !target.closest('.apps-menu-dropdown') &&
          !target.closest('.profile-menu-dropdown')) {
        setActiveMenu(null)
      }
    }
    if (activeMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [activeMenu])

  // Handle messages from file selector window to open workspace settings
  useEffect(() => {
    const handleOpenWorkspaceSettings = (event: CustomEvent) => {
      setActiveMenu('apps')
      if (event.detail?.action === 'configure-folder') {
        // AppsMenu will handle folder selector
      }
    }

    window.addEventListener('open-workspace-settings', handleOpenWorkspaceSettings as EventListener)
    return () => {
      window.removeEventListener('open-workspace-settings', handleOpenWorkspaceSettings as EventListener)
    }
  }, [])

  const toggleMenu = (menu: 'profile' | 'apps' | 'settings' | 'help') => {
    setActiveMenu(activeMenu === menu ? null : menu)
  }

  return (
    <header className="compact-header">
      <div className="compact-header-content">
        {/* Logo */}
        <div className="header-logo">
          <Logo />
        </div>

        {/* Right menu buttons */}
        <div className="header-menu-buttons">
          <div className="relative">
            <button
              onClick={() => toggleMenu('apps')}
              className={`header-menu-button ${activeMenu === 'apps' ? 'active' : ''}`}
              title="Приложения"
            >
              <Smartphone className="w-4 h-4" />
            </button>
            <AppsMenu isOpen={activeMenu === 'apps'} onClose={() => setActiveMenu(null)} />
          </div>

          <div className="relative">
            <button
              onClick={() => toggleMenu('settings')}
              className={`header-menu-button ${activeMenu === 'settings' ? 'active' : ''}`}
              title="Настройки"
            >
              <Settings className="w-4 h-4" />
            </button>
            <SettingsMenu isOpen={activeMenu === 'settings'} onClose={() => setActiveMenu(null)} />
          </div>

          <div className="relative">
            <button
              onClick={() => {
                // #region debug log
                fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'Header.tsx:81',message:'Help button clicked',data:{activeMenu},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
                toggleMenu('help')
              }}
              className={`header-menu-button ${activeMenu === 'help' ? 'active' : ''}`}
              title="Помощь"
            >
              <HelpCircle className="w-4 h-4" />
            </button>
            <HelpMenu isOpen={activeMenu === 'help'} onClose={() => setActiveMenu(null)} />
          </div>

          <div className="relative">
            <button
              onClick={() => toggleMenu('profile')}
              className={`header-menu-button header-menu-button-profile ${activeMenu === 'profile' ? 'active' : ''}`}
              title="Профиль"
            >
              <User className="w-4 h-4" />
              <ChevronDown className={`w-3 h-3 transition-transform ${activeMenu === 'profile' ? 'rotate-180' : ''}`} />
            </button>
            <ProfileMenu isOpen={activeMenu === 'profile'} onClose={() => setActiveMenu(null)} />
          </div>
        </div>
      </div>
    </header>
  )
}

