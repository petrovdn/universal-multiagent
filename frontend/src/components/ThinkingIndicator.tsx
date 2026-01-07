import React from 'react'

interface ThinkingIndicatorProps {
  tool?: string
  description?: string
}

// Маппинг инструментов на эмодзи
function getToolEmoji(tool: string): string {
  const toolLower = tool.toLowerCase()
  
  if (toolLower.includes('email') || toolLower.includes('gmail') || toolLower.includes('mail')) {
    return '📧'
  }
  if (toolLower.includes('calendar') || toolLower.includes('event')) {
    return '📅'
  }
  if (toolLower.includes('file') || toolLower.includes('drive') || toolLower.includes('workspace') || toolLower.includes('document')) {
    return '📁'
  }
  if (toolLower.includes('search')) {
    return '🔍'
  }
  if (toolLower.includes('create') || toolLower.includes('write')) {
    return '✏️'
  }
  if (toolLower.includes('read') || toolLower.includes('get')) {
    return '📖'
  }
  if (toolLower === 'finish' || toolLower.includes('complete')) {
    return '✅'
  }
  
  return '🔄' // default
}

export function ThinkingIndicator({ tool, description }: ThinkingIndicatorProps) {
  // #region agent log
  fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'ThinkingIndicator.tsx:render',message:'ThinkingIndicator rendering',data:{tool,description,hasTool:!!tool,hasDescription:!!description},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H5'})}).catch(()=>{});
  // #endregion
  
  // Если есть описание действия, показываем его с эмодзи
  if (tool && description) {
    const emoji = getToolEmoji(tool)
    return (
      <div className="thinking-indicator-container">
        <span className="thinking-indicator-text">
          {emoji} {description}
        </span>
        <div className="thinking-indicator-dots">
          <span className="dot dot-1">.</span>
          <span className="dot dot-2">.</span>
          <span className="dot dot-3">.</span>
        </div>
      </div>
    )
  }
  
  // Fallback на стандартный текст
  return (
    <div className="thinking-indicator-container">
      <span className="thinking-indicator-text">Планирую действия</span>
      <div className="thinking-indicator-dots">
        <span className="dot dot-1">.</span>
        <span className="dot dot-2">.</span>
        <span className="dot dot-3">.</span>
      </div>
    </div>
  )
}

