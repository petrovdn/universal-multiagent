import { useEffect, useRef } from 'react'
import { HelpCircle, Book, Keyboard, Info, ExternalLink } from 'lucide-react'

interface HelpMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function HelpMenu({ isOpen, onClose }: HelpMenuProps) {
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

  if (!isOpen) return null

  return (
    <div className="help-menu-dropdown" ref={menuRef}>
      <div className="help-menu-header">
        <h3 className="help-menu-title">Помощь</h3>
      </div>
      
      <div className="help-menu-list">
        <button className="help-menu-item">
          <Book className="w-4 h-4" />
          <span>Документация</span>
          <ExternalLink className="w-3.5 h-3.5 ml-auto" />
        </button>
        
        <button className="help-menu-item">
          <Keyboard className="w-4 h-4" />
          <span>Горячие клавиши</span>
        </button>
        
        <div className="help-menu-divider"></div>
        
        <button className="help-menu-item">
          <Info className="w-4 h-4" />
          <span>О программе</span>
        </button>
      </div>
    </div>
  )
}

