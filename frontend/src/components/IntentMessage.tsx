import React, { useMemo } from 'react'
import { ChevronDown, ChevronRight, Search, FileText, Play, Brain, Pencil, Check } from 'lucide-react'
import { IntentBlock, IntentDetailType } from '../store/chatStore'

interface IntentMessageProps {
  block: IntentBlock
  onToggleCollapse: () => void
}

export function IntentMessage({ block, onToggleCollapse }: IntentMessageProps) {
  // Генерируем summary из details
  const summary = useMemo(() => {
    const counts: Record<IntentDetailType, number> = {
      search: 0,
      read: 0,
      execute: 0,
      analyze: 0,
      write: 0,
    }
    block.details.forEach(d => counts[d.type]++)
    
    const parts: string[] = []
    if (counts.read > 0) parts.push(`${counts.read} file${counts.read > 1 ? 's' : ''}`)
    if (counts.search > 0) parts.push(`${counts.search} search${counts.search > 1 ? 'es' : ''}`)
    if (counts.execute > 0) parts.push(`${counts.execute} action${counts.execute > 1 ? 's' : ''}`)
    if (counts.write > 0) parts.push(`${counts.write} write${counts.write > 1 ? 's' : ''}`)
    if (counts.analyze > 0) parts.push(`${counts.analyze} result${counts.analyze > 1 ? 's' : ''}`)
    
    // Определяем главное действие
    let actionWord = 'Explored'
    if (counts.read > 0 && counts.search === 0) {
      actionWord = 'Read'
    } else if (counts.search > 0 && counts.read === 0) {
      actionWord = 'Searched'
    } else if (counts.execute > 0) {
      actionWord = 'Executed'
    } else if (counts.write > 0) {
      actionWord = 'Wrote'
    }
    
    return parts.length > 0 ? `${actionWord} ${parts.join(' ')}` : 'Processing...'
  }, [block.details])
  
  const getIcon = (type: IntentDetailType) => {
    switch (type) {
      case 'search': return <Search size={12} className="intent-detail-icon" />
      case 'read': return <FileText size={12} className="intent-detail-icon" />
      case 'execute': return <Play size={12} className="intent-detail-icon" />
      case 'write': return <Pencil size={12} className="intent-detail-icon" />
      case 'analyze': return <Check size={12} className="intent-detail-icon intent-detail-icon-success" />
      default: return <Brain size={12} className="intent-detail-icon" />
    }
  }

  const isStreaming = block.status === 'streaming' || block.status === 'started'
  const hasDetails = block.details.length > 0

  return (
    <div className={`intent-message ${isStreaming ? 'intent-message-streaming' : ''}`}>
      {/* Текст намерения - простой текст */}
      <div className="intent-text">
        {block.intent}
        {isStreaming && <span className="intent-text-dots" />}
      </div>
      
      {/* Сворачиваемый блок с деталями */}
      {hasDetails && (
        <div 
          className={`intent-details ${block.isCollapsed ? 'intent-details-collapsed' : ''}`}
        >
          <div 
            className="intent-details-header"
            onClick={onToggleCollapse}
          >
            {block.isCollapsed ? (
              <ChevronRight size={14} className="intent-chevron" />
            ) : (
              <ChevronDown size={14} className="intent-chevron" />
            )}
            <span className="intent-summary">{summary}</span>
          </div>
          
          {!block.isCollapsed && (
            <div className="intent-details-content">
              {block.details.map((detail, i) => (
                <div key={i} className="intent-detail-item">
                  {getIcon(detail.type)}
                  <span className="intent-detail-text">{detail.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

