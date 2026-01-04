import { useState, useEffect, useRef } from 'react'
import { User, LogOut, Key, Coins, ChevronDown } from 'lucide-react'
import { logout, getCurrentUser } from '../../services/api'

interface ProfileMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function ProfileMenu({ isOpen, onClose }: ProfileMenuProps) {
  const [currentUser, setCurrentUser] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      loadCurrentUser()
    }
  }, [isOpen])

  useEffect(() => {
    const handleAuthChange = () => {
      loadCurrentUser()
    }
    window.addEventListener('auth-status-changed', handleAuthChange)
    return () => {
      window.removeEventListener('auth-status-changed', handleAuthChange)
    }
  }, [])

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node
      const isInside = menuRef.current?.contains(target)
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleClickOutside',message:'Click outside handler',data:{targetTagName:(target as HTMLElement)?.tagName,targetClassName:(target as HTMLElement)?.className,isInside,willClose:!isInside},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
      // #endregion
      // Don't close if clicking on a button inside the menu
      const targetElement = target as HTMLElement
      if (targetElement?.closest('button')) {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleClickOutside:button_click',message:'Click on button inside menu, not closing',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        return
      }
      if (menuRef.current && !isInside) {
        onClose()
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, onClose])

  const loadCurrentUser = async () => {
    try {
      const user = await getCurrentUser()
      setCurrentUser(user.username)
    } catch (err) {
      console.log('Failed to load current user:', err)
      setCurrentUser(null)
    }
  }

  const handleLogout = async () => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleLogout:entry',message:'handleLogout called',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    try {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleLogout:before_logout',message:'About to call logout API',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      await logout()
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleLogout:after_logout',message:'Logout API call successful',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      setCurrentUser(null)
      onClose()
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleLogout:before_redirect',message:'About to redirect to /',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      window.location.href = '/'
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:handleLogout:error',message:'Logout error',data:{error:String(err),errorType:err?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      console.error('Logout error:', err)
    }
  }

  if (!isOpen) return null

  // #region agent log
  fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:render',message:'ProfileMenu rendering',data:{isOpen,currentUser,hasCurrentUser:!!currentUser},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
  // #endregion

  return (
    <div className="profile-menu-dropdown" ref={menuRef}>
      {currentUser ? (
        <>
          <div className="profile-menu-header">
            <div className="profile-avatar">
              <User className="w-5 h-5" />
            </div>
            <div className="profile-info">
              <div className="profile-name">{currentUser}</div>
              <div className="profile-email">{/* Email будет добавлен позже */}</div>
            </div>
          </div>
          
          <div className="profile-menu-divider"></div>
          
          <div className="profile-menu-item">
            <Coins className="w-4 h-4" />
            <span>Баланс токенов</span>
            <span className="profile-menu-value">—</span>
          </div>
          
          <div className="profile-menu-divider"></div>
          
          <button className="profile-menu-item" onClick={() => {/* TODO: открыть диалог смены пароля */}}>
            <Key className="w-4 h-4" />
            <span>Изменить пароль</span>
          </button>
          
          <div className="profile-menu-divider"></div>
          
          <button 
            className="profile-menu-item logout-item" 
            onMouseDown={(e) => {
              // #region agent log
              fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:logout_button:mousedown',message:'Logout button mousedown',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
              // #endregion
              e.preventDefault()
              e.stopPropagation()
            }}
            onClick={(e) => {
              // #region agent log
              const target = e.target as HTMLElement
              fetch('http://127.0.0.1:7243/ingest/e3d3ec53-ef20-4f00-981c-41ed4e0b4a01',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ProfileMenu.tsx:logout_button:click',message:'Logout button clicked',data:{targetTagName:target?.tagName,targetClassName:target?.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
              // #endregion
              e.preventDefault()
              e.stopPropagation()
              handleLogout()
            }}
            type="button"
          >
            <LogOut className="w-4 h-4" />
            <span>Выйти</span>
          </button>
        </>
      ) : (
        <div className="profile-menu-empty">
          <div className="text-xs text-slate-500 dark:text-slate-400 py-2">
            Не авторизован
          </div>
        </div>
      )}
    </div>
  )
}

