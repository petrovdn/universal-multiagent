import React, { useState } from 'react'
import { 
  Search, 
  FileText, 
  Globe, 
  Mail, 
  Calendar, 
  Settings, 
  Wrench,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Lightbulb
} from 'lucide-react'
import { ActionMessageData } from '../store/chatStore'

interface ActionItemProps {
  action: ActionMessageData
  isLast?: boolean
}

// Иконки по типу действия
const getActionIcon = (icon: ActionMessageData['icon']) => {
  const iconSize = 14
  const iconColor = 'var(--text-secondary)'
  
  switch (icon) {
    case 'search':
      return <Search size={iconSize} color={iconColor} />
    case 'file':
      return <FileText size={iconSize} color={iconColor} />
    case 'api':
      return <Globe size={iconSize} color={iconColor} />
    case 'email':
      return <Mail size={iconSize} color={iconColor} />
    case 'calendar':
      return <Calendar size={iconSize} color={iconColor} />
    case 'process':
      return <Settings size={iconSize} color={iconColor} />
    case 'tool':
      return <Wrench size={iconSize} color={iconColor} />
    default:
      return <Settings size={iconSize} color={iconColor} />
  }
}

// Иконка статуса
const getStatusIcon = (status: ActionMessageData['status']) => {
  const iconSize = 14
  
  switch (status) {
    case 'pending':
      return <Clock size={iconSize} className="action-status-icon action-status-pending" />
    case 'in_progress':
      return (
        <div className="action-status-icon action-status-in-progress">
          <div className="spinner-small" />
        </div>
      )
    case 'success':
      return <CheckCircle size={iconSize} className="action-status-icon action-status-success" />
    case 'error':
      return <XCircle size={iconSize} className="action-status-icon action-status-error" />
    case 'alternative':
      return <Lightbulb size={iconSize} className="action-status-icon action-status-alternative" />
    default:
      return null
  }
}

export function ActionItem({ action, isLast = false }: ActionItemProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasDetails = !!(action.details || action.error || action.alternativeUsed)

  return (
    <div className={`action-item action-item-${action.status} ${isLast ? 'action-item-last' : ''}`}>
      <div className="action-item-header">
        <div className="action-item-icon">
          {getActionIcon(action.icon)}
        </div>
        
        <div className="action-item-content">
          <div className="action-item-title-row">
            <span className="action-item-title">{action.title}</span>
            <div className="action-item-status">
              {getStatusIcon(action.status)}
            </div>
          </div>
          
          {action.description && (
            <div className="action-item-description">{action.description}</div>
          )}
          
          {/* Показываем ошибку или альтернативу inline */}
          {action.status === 'error' && action.error && (
            <div className="action-item-error">
              {action.error}
            </div>
          )}
          
          {action.status === 'alternative' && action.alternativeUsed && (
            <div className="action-item-alternative">
              Использовано: {action.alternativeUsed}
            </div>
          )}
        </div>
        
        {hasDetails && (
          <button
            className="action-item-expand-button"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Свернуть детали' : 'Развернуть детали'}
          >
            {isExpanded ? (
              <ChevronUp size={14} />
            ) : (
              <ChevronDown size={14} />
            )}
          </button>
        )}
      </div>
      
      {/* Детали (раскрываемые) */}
      {hasDetails && isExpanded && (
        <div className="action-item-details">
          {action.details && (
            <div className="action-item-details-content">
              <pre>{action.details}</pre>
            </div>
          )}
          {action.error && action.status !== 'error' && (
            <div className="action-item-details-error">
              Ошибка: {action.error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

