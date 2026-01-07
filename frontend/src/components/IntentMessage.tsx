import React, { useMemo } from 'react'
import { ChevronDown, ChevronRight, Search, FileText, Play, Brain, Pencil, Check } from 'lucide-react'
import { IntentBlock, IntentDetailType } from '../store/chatStore'

interface IntentMessageProps {
  block: IntentBlock
  onToggleCollapse: () => void
}

export function IntentMessage({ block, onToggleCollapse }: IntentMessageProps) {
  // Склонение слов на русском
  const pluralize = (n: number, one: string, few: string, many: string) => {
    const mod10 = n % 10
    const mod100 = n % 100
    if (mod100 >= 11 && mod100 <= 14) return many
    if (mod10 === 1) return one
    if (mod10 >= 2 && mod10 <= 4) return few
    return many
  }

  // Summary для свёрнутого состояния
  // Приоритет: backend summary > счётчик деталей > статус
  const displaySummary = useMemo(() => {
    // Если есть summary от backend (результат действия) - показываем его
    if (block.summary) {
      return block.summary
    }
    
    // Иначе генерируем из деталей
    if (block.details.length > 0) {
      const counts: Record<IntentDetailType, number> = {
        search: 0,
        read: 0,
        execute: 0,
        analyze: 0,
        write: 0,
      }
      block.details.forEach(d => counts[d.type]++)
      
      const parts: string[] = []
      if (counts.read > 0) parts.push(`${counts.read} ${pluralize(counts.read, 'файл', 'файла', 'файлов')}`)
      if (counts.search > 0) parts.push(`${counts.search} ${pluralize(counts.search, 'поиск', 'поиска', 'поисков')}`)
      if (counts.execute > 0) parts.push(`${counts.execute} ${pluralize(counts.execute, 'действие', 'действия', 'действий')}`)
      if (counts.write > 0) parts.push(`${counts.write} ${pluralize(counts.write, 'запись', 'записи', 'записей')}`)
      if (counts.analyze > 0) parts.push(`${counts.analyze} ${pluralize(counts.analyze, 'результат', 'результата', 'результатов')}`)
      
      return parts.length > 0 ? parts.join(', ') : 'Обработка...'
    }
    
    // Статус по умолчанию
    if (block.status === 'completed') {
      return 'Выполнено'
    }
    return 'Выполняется...'
  }, [block.summary, block.details, block.status])
  
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
  const isCompleted = block.status === 'completed'
  const hasDetails = block.details.length > 0
  const showCollapsible = hasDetails || block.summary

  return (
    <div className={`intent-message ${isStreaming ? 'intent-message-streaming' : ''} ${isCompleted ? 'intent-message-completed' : ''}`}>
      {/* Текст намерения - простой текст */}
      <div className="intent-text">
        {block.intent}
        {isStreaming && <span className="intent-text-dots" />}
      </div>
      
      {/* Сворачиваемый блок с деталями */}
      {showCollapsible && (
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
            <span className="intent-summary">{displaySummary}</span>
          </div>
          
          {!block.isCollapsed && hasDetails && (
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
