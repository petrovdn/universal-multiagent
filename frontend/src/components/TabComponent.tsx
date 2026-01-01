import React from 'react'
import { X } from 'lucide-react'
import type { WorkspaceTab } from '../types/workspace'

interface TabComponentProps {
  tab: WorkspaceTab
  isActive: boolean
  onClick: () => void
  onClose: () => void
  isLast?: boolean
}

export function TabComponent({ tab, isActive, onClick, onClose, isLast = false }: TabComponentProps) {
  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClose()
  }

  return (
    <div
      data-tab-id={tab.id}
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'flex-start',
        flexWrap: 'nowrap',
        cursor: 'pointer',
        transition: 'all 0.15s',
        whiteSpace: 'nowrap',
        minHeight: '35px',
        minWidth: '120px',
        fontSize: '13px',
        paddingLeft: '12px',
        paddingRight: '12px',
        gap: '8px',
        borderRightWidth: isLast ? '0px' : '1px',
        borderRightStyle: 'solid',
        borderRightColor: isActive ? 'rgb(226 232 240)' : 'rgb(203 213 225)',
        borderBottomWidth: '0px',
        boxShadow: 'none',
        backgroundColor: isActive 
          ? (document.documentElement.classList.contains('dark')
              ? 'rgb(30 41 59)' // slate-800 темная
              : 'rgb(255 255 255)') // Белая (активная)
          : (document.documentElement.classList.contains('dark')
              ? 'rgb(15 23 42)' // slate-900 темная
              : 'rgb(229 231 235)') // slate-200 серая (неактивная)
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (!isActive && tab.closeable) {
          const closeBtn = e.currentTarget.querySelector('button[aria-label="Close tab"]') as HTMLElement
          if (closeBtn) closeBtn.style.opacity = '1'
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive && tab.closeable) {
          const closeBtn = e.currentTarget.querySelector('button[aria-label="Close tab"]') as HTMLElement
          if (closeBtn) closeBtn.style.opacity = '0'
        }
      }}
    >
      <span className="text-sm font-normal truncate">{tab.title}</span>
      {tab.closeable && (
        <button
          onClick={handleClose}
          aria-label="Close tab"
          style={{ 
            opacity: isActive ? 1 : 0,
            width: '20px',
            height: '20px',
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '3px',
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            pointerEvents: isActive ? 'auto' : 'none',
            color: 'rgb(100 116 139)' // slate-500
          }}
          onMouseEnter={(e) => {
            if (isActive) {
              e.currentTarget.style.backgroundColor = 'rgb(226 232 240)' // slate-200
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          <X size={12} strokeWidth={2} />
        </button>
      )}
    </div>
  )
}

