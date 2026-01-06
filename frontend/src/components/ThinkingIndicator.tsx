import React from 'react'

interface ThinkingIndicatorProps {
  text?: string
}

export function ThinkingIndicator({ text = 'Планирую действия...' }: ThinkingIndicatorProps) {
  return (
    <div className="thinking-indicator">
      <div className="thinking-indicator-text">
        {text.split('').map((char, index) => (
          <span 
            key={index} 
            className="thinking-indicator-char"
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            {char === ' ' ? '\u00A0' : char}
          </span>
        ))}
      </div>
    </div>
  )
}

