import React from 'react'
import { Brain } from 'lucide-react'

interface ThinkingIndicatorProps {
  text?: string
}

export function ThinkingIndicator({ text = 'Планирую действия...' }: ThinkingIndicatorProps) {
  return (
    <div className="thinking-indicator-container">
      <Brain size={16} className="thinking-indicator-icon" />
      <span className="thinking-indicator-text">{text}</span>
      <div className="thinking-indicator-dots">
        <span className="dot dot-1">.</span>
        <span className="dot dot-2">.</span>
        <span className="dot dot-3">.</span>
      </div>
    </div>
  )
}

