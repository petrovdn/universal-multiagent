import { useEffect, useRef, useState } from 'react'
import { HelpCircle, Book, Keyboard, Info, ExternalLink } from 'lucide-react'
import { DocumentationModal } from '../help/DocumentationModal'
import { KeyboardShortcutsModal } from '../help/KeyboardShortcutsModal'
import { AboutModal } from '../help/AboutModal'

interface HelpMenuProps {
  isOpen: boolean
  onClose: () => void
}

export function HelpMenu({ isOpen, onClose }: HelpMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  const [documentationOpen, setDocumentationOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)
  const justOpenedModalRef = useRef<{type: 'doc' | 'shortcuts' | 'about' | null, timestamp: number}>({type: null, timestamp: 0})

  // Reset modal states when menu closes if modals are not actually open
  // This prevents modals from auto-opening when menu reopens
  // Use a delay to allow modals to render before checking
  // Don't reset if a modal was just opened (within last 500ms)
  useEffect(() => {
    if (!isOpen) {
      // Wait a bit for modals to render before checking DOM
      const timeoutId = setTimeout(() => {
        // Check if modal was just opened (within last 500ms)
        const timeSinceModalOpened = Date.now() - justOpenedModalRef.current.timestamp
        const wasJustOpened = justOpenedModalRef.current.type !== null && timeSinceModalOpened < 500
        
        // Check if any modal is actually rendered in the DOM
        const anyModal = document.querySelector('.documentation-modal-overlay')
        
        // If no modal is in DOM and states say they should be open, reset them
        // BUT: don't reset if modal was just opened (it might still be rendering)
        if (!anyModal && (documentationOpen || shortcutsOpen || aboutOpen) && !wasJustOpened) {
          setDocumentationOpen(false)
          setShortcutsOpen(false)
          setAboutOpen(false)
        } else if (wasJustOpened && anyModal) {
          // Modal was just opened and is now in DOM, clear the flag
          justOpenedModalRef.current = {type: null, timestamp: 0}
        }
      }, 300) // 300ms delay to allow modals to render
      
      return () => clearTimeout(timeoutId)
    }
  }, [isOpen, documentationOpen, shortcutsOpen, aboutOpen])

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node
      if (menuRef.current && !menuRef.current.contains(target)) {
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

  const handleDocumentationClick = () => {
    justOpenedModalRef.current = {type: 'doc', timestamp: Date.now()}
    setDocumentationOpen(true)
    onClose()
  }

  const handleShortcutsClick = () => {
    justOpenedModalRef.current = {type: 'shortcuts', timestamp: Date.now()}
    setShortcutsOpen(true)
    onClose()
  }

  const handleAboutClick = () => {
    justOpenedModalRef.current = {type: 'about', timestamp: Date.now()}
    setAboutOpen(true)
    onClose()
  }

  return (
    <>
      {isOpen && (
        <div className="help-menu-dropdown" ref={menuRef}>
          <div className="help-menu-header">
            <h3 className="help-menu-title">Помощь</h3>
          </div>
          
          <div className="help-menu-list">
            <button 
              className="help-menu-item" 
              onClick={(e) => {
                e.stopPropagation()
                handleDocumentationClick()
              }}
            >
              <Book className="w-4 h-4" />
              <span>Документация</span>
              <ExternalLink className="w-3.5 h-3.5 ml-auto" />
            </button>
            
            <button 
              className="help-menu-item" 
              onClick={(e) => {
                e.stopPropagation()
                handleShortcutsClick()
              }}
            >
              <Keyboard className="w-4 h-4" />
              <span>Горячие клавиши</span>
            </button>
            
            <div className="help-menu-divider"></div>
            
            <button 
              className="help-menu-item" 
              onClick={(e) => {
                e.stopPropagation()
                handleAboutClick()
              }}
            >
              <Info className="w-4 h-4" />
              <span>О программе</span>
            </button>
          </div>
        </div>
      )}

      {/* Модальные окна рендерятся независимо от состояния HelpMenu */}
      <DocumentationModal 
        isOpen={documentationOpen} 
        onClose={() => setDocumentationOpen(false)} 
      />
      <KeyboardShortcutsModal 
        isOpen={shortcutsOpen} 
        onClose={() => setShortcutsOpen(false)} 
      />
      <AboutModal 
        isOpen={aboutOpen} 
        onClose={() => setAboutOpen(false)} 
      />
    </>
  )
}

