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

  // #region debug log
  useEffect(() => {
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:18',message:'HelpMenu state updated',data:{isOpen,documentationOpen,shortcutsOpen,aboutOpen},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
  }, [isOpen, documentationOpen, shortcutsOpen, aboutOpen]);
  // #endregion

  // Reset modal states when menu closes if modals are not actually open
  // This prevents modals from auto-opening when menu reopens
  // Use a delay to allow modals to render before checking
  // Don't reset if a modal was just opened (within last 500ms)
  useEffect(() => {
    if (!isOpen) {
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:25',message:'Menu closed, will check modals after delay',data:{documentationOpen,shortcutsOpen,aboutOpen,justOpened:justOpenedModalRef.current},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'G'})}).catch(()=>{});
      // #endregion
      // Wait a bit for modals to render before checking DOM
      const timeoutId = setTimeout(() => {
        // Check if modal was just opened (within last 500ms)
        const timeSinceModalOpened = Date.now() - justOpenedModalRef.current.timestamp
        const wasJustOpened = justOpenedModalRef.current.type !== null && timeSinceModalOpened < 500
        
        // Check if any modal is actually rendered in the DOM
        const anyModal = document.querySelector('.documentation-modal-overlay')
        
        // #region debug log
        fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:35',message:'Checking if modals are in DOM after delay',data:{hasModal:!!anyModal,documentationOpen,shortcutsOpen,aboutOpen,wasJustOpened,timeSinceModalOpened},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'G'})}).catch(()=>{});
        // #endregion
        
        // If no modal is in DOM and states say they should be open, reset them
        // BUT: don't reset if modal was just opened (it might still be rendering)
        if (!anyModal && (documentationOpen || shortcutsOpen || aboutOpen) && !wasJustOpened) {
          // #region debug log
          fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:42',message:'No modal in DOM but states are true, resetting',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'G'})}).catch(()=>{});
          // #endregion
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
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:37',message:'handleClickOutside called',data:{contains:menuRef.current?.contains(target),targetTag:(target as HTMLElement)?.tagName,targetClass:(target as HTMLElement)?.className},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'F'})}).catch(()=>{});
      // #endregion
      if (menuRef.current && !menuRef.current.contains(target)) {
        // #region debug log
        fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:40',message:'Calling onClose from handleClickOutside',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run2',hypothesisId:'F'})}).catch(()=>{});
        // #endregion
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
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:33',message:'handleDocumentationClick called',data:{documentationOpen},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    justOpenedModalRef.current = {type: 'doc', timestamp: Date.now()}
    setDocumentationOpen(true)
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:36',message:'setDocumentationOpen(true) called',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    onClose()
  }

  const handleShortcutsClick = () => {
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:40',message:'handleShortcutsClick called',data:{shortcutsOpen},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    justOpenedModalRef.current = {type: 'shortcuts', timestamp: Date.now()}
    setShortcutsOpen(true)
    onClose()
  }

  const handleAboutClick = () => {
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:47',message:'handleAboutClick called',data:{aboutOpen},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
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
                // #region debug log
                fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:76',message:'Documentation button onClick event',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
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
                // #region debug log
                fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:88',message:'Shortcuts button onClick event',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
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
                // #region debug log
                fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'HelpMenu.tsx:100',message:'About button onClick event',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
                // #endregion
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

