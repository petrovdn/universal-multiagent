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
    try {
      await logout()
      setCurrentUser(null)
      onClose()
      window.location.href = '/'
    } catch (err) {
      console.error('Logout error:', err)
    }
  }

  if (!isOpen) return null


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
              e.preventDefault()
              e.stopPropagation()
            }}
            onClick={(e) => {
              const target = e.target as HTMLElement
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

