import React, { useMemo } from 'react'
import { 
  X, 
  Loader2, 
  Table2, 
  FileText, 
  Presentation, 
  Mail, 
  LayoutDashboard, 
  BarChart2, 
  Code, 
  Calendar, 
  Sparkles 
} from 'lucide-react'
import type { WorkspaceTab, WorkspaceTabType } from '../types/workspace'

interface TabComponentProps {
  tab: WorkspaceTab
  isActive: boolean
  onClick: () => void
  onClose: () => void
  isLast?: boolean
}

// Функция для получения иконки по типу таба
function getTabIcon(type: WorkspaceTabType) {
  switch (type) {
    case 'sheets':
      return Table2
    case 'docs':
      return FileText
    case 'slides':
      return Presentation
    case 'email':
      return Mail
    case 'dashboard':
      return LayoutDashboard
    case 'chart':
      return BarChart2
    case 'code':
      return Code
    case 'calendar':
      return Calendar
    case 'placeholder':
    default:
      return Sparkles
  }
}

export function TabComponent({ tab, isActive, onClick, onClose, isLast = false }: TabComponentProps) {
  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClose()
  }

  const IconComponent = getTabIcon(tab.type)
  const isLoading = tab.isLoading ?? false

  // Вычисляем ширину на основе длины названия файла
  const tabWidth = useMemo(() => {
    const MIN_WIDTH = 50 // Минимальная ширина для коротких названий
    const MAX_WIDTH = 250 // Максимальная ширина
    const CHAR_WIDTH = 7.5 // Примерная ширина одного символа (зависит от шрифта)
    const PADDING_LEFT = 12 // paddingLeft
    const PADDING_RIGHT = 8 // paddingRight (уменьшено, так как после кнопки не нужно много места)
    const CLOSE_BUTTON_WIDTH = tab.closeable ? 20 : 0 // ширина кнопки закрытия
    const GAP = tab.closeable ? 8 : 0 // gap между текстом и кнопкой
    const ICON_WIDTH = 16 // ширина иконки типа файла
    const ICON_GAP = 6 // gap между иконкой и текстом
    
    // Вычисляем ширину текста
    const textWidth = tab.title.length * CHAR_WIDTH
    
    // Итоговая ширина = отступ слева + иконка + gap иконки + текст + gap + кнопка + отступ справа
    const calculatedWidth = PADDING_LEFT + ICON_WIDTH + ICON_GAP + textWidth + GAP + CLOSE_BUTTON_WIDTH + PADDING_RIGHT
    
    // Ограничиваем минимальной и максимальной шириной
    return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, calculatedWidth))
  }, [tab.title, tab.closeable])

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
        width: `${tabWidth}px`, // Используем вычисленную ширину
        fontSize: '13px',
        paddingLeft: '12px',
        paddingRight: '8px', // Уменьшено для более компактного вида
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
      onMouseEnter={(e) => {
        if (!isActive && tab.closeable && !isLoading) {
          const closeBtn = e.currentTarget.querySelector('button[aria-label="Close tab"]') as HTMLElement
          if (closeBtn) closeBtn.style.opacity = '1'
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive && tab.closeable && !isLoading) {
          const closeBtn = e.currentTarget.querySelector('button[aria-label="Close tab"]') as HTMLElement
          if (closeBtn) closeBtn.style.opacity = '0'
        }
      }}
    >
      {/* Иконка типа файла */}
      <IconComponent 
        size={16} 
        strokeWidth={2}
        style={{
          flexShrink: 0,
          color: 'rgb(100 116 139)', // slate-500
          marginRight: '6px'
        }}
      />
      <span 
        className="text-sm font-normal truncate"
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flex: '1 1 0%',
          minWidth: 0
        }}
      >
        {tab.title}
      </span>
      {tab.closeable && (
        <button
          onClick={handleClose}
          aria-label={isLoading ? "Loading" : "Close tab"}
          disabled={isLoading}
          style={{ 
            opacity: isLoading ? 1 : (isActive ? 1 : 0),
            width: '20px',
            height: '20px',
            padding: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '3px',
            backgroundColor: 'transparent',
            border: 'none',
            cursor: isLoading ? 'default' : 'pointer',
            transition: 'all 0.15s ease',
            pointerEvents: (isActive || isLoading) ? 'auto' : 'none',
            color: isLoading ? 'rgb(59 130 246)' : 'rgb(100 116 139)', // blue-500 для лоадера, slate-500 для крестика
            flexShrink: 0 // Кнопка не должна сжиматься
          }}
          onMouseEnter={(e) => {
            if (isActive && !isLoading) {
              e.currentTarget.style.backgroundColor = 'rgb(226 232 240)' // slate-200
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          {isLoading ? (
            <Loader2 size={14} strokeWidth={2.5} style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <X size={12} strokeWidth={2} />
          )}
        </button>
      )}
    </div>
  )
}

