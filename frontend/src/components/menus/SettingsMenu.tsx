import { useState, useEffect, useRef } from 'react'
import { Settings, Moon, Sun, ChevronDown } from 'lucide-react'
import { useSettingsStore } from '../../store/settingsStore'

interface SettingsMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function SettingsMenu({ isOpen, onClose }: SettingsMenuProps) {
  const { theme, setTheme } = useSettingsStore()
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
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

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light')
  }

  if (!isOpen) return null

  return (
    <div className="settings-menu-dropdown" ref={menuRef}>
      <div className="settings-menu-header">
        <h3 className="settings-menu-title">Настройки</h3>
      </div>
      
      <div className="settings-menu-list">
        {/* Theme */}
        <div className="settings-menu-item">
          <div className="settings-menu-item-left">
            {theme === 'dark' ? (
              <Moon className="w-4 h-4" />
            ) : (
              <Sun className="w-4 h-4" />
            )}
            <span>Тема</span>
          </div>
          <button
            onClick={toggleTheme}
            className="settings-toggle-button"
          >
            {theme === 'dark' ? 'Тёмная' : 'Светлая'}
            <ChevronDown className="w-3.5 h-3.5 ml-1" />
          </button>
        </div>

      </div>
    </div>
  )
}

