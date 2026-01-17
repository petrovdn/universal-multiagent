/**
 * SourceCard component - Phase 1, Step 2.1.
 * 
 * Displays a Perplexity-style source card showing data source status
 * (loading, completed, error) with icon, name, and metadata.
 */
import React from 'react'
import { SourceCard as SourceCardType } from '../store/chatStore'

interface SourceCardProps {
  source: SourceCardType
  className?: string
}

export function SourceCard({ source, className = '' }: SourceCardProps) {
  const { name, icon, status, preview, item_count, error } = source
  
  // Determine background color based on status
  const getBackgroundColor = () => {
    switch (status) {
      case 'completed':
        return '#e8f5e9' // Light green
      case 'error':
        return '#ffebee' // Light red
      case 'loading':
      default:
        return '#fff3e0' // Light orange/amber
    }
  }
  
  // Determine border color based on status
  const getBorderColor = () => {
    switch (status) {
      case 'completed':
        return '#c8e6c9' // Green border
      case 'error':
        return '#ffcdd2' // Red border
      case 'loading':
      default:
        return '#ffe0b2' // Orange border
    }
  }
  
  // Get status indicator
  const getStatusIndicator = () => {
    switch (status) {
      case 'loading':
        return <span style={{ fontSize: '12px', color: '#666' }}>⏳</span>
      case 'completed':
        return <span style={{ fontSize: '12px', color: '#4caf50' }}>✓</span>
      case 'error':
        return <span style={{ fontSize: '12px', color: '#f44336' }}>✗</span>
      default:
        return null
    }
  }
  
  return (
    <div
      className={className}
      style={{
        padding: '8px 12px',
        backgroundColor: getBackgroundColor(),
        borderRadius: '6px',
        fontSize: '13px',
        border: `1px solid ${getBorderColor()}`,
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        minWidth: '150px'
      }}
    >
      {/* Icon */}
      <span style={{ fontSize: '16px' }}>{icon}</span>
      
      {/* Content */}
      <div style={{ flex: 1 }}>
        {/* Source name */}
        <div style={{ fontWeight: 500, color: '#333' }}>{name}</div>
        
        {/* Status-specific content */}
        {status === 'loading' && preview && (
          <div style={{ fontSize: '11px', color: '#666', fontStyle: 'italic' }}>
            {preview}
          </div>
        )}
        
        {status === 'completed' && item_count !== undefined && (
          <div style={{ fontSize: '11px', color: '#666' }}>
            Найдено: {item_count}
          </div>
        )}
        
        {status === 'error' && (
          <div style={{ fontSize: '11px', color: '#d32f2f' }}>
            Ошибка
          </div>
        )}
      </div>
      
      {/* Status indicator */}
      {getStatusIndicator()}
    </div>
  )
}
