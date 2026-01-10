import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface FinalResultBlockProps {
  content: string
}

export function FinalResultBlock({ content }: FinalResultBlockProps) {
  if (!content || content.trim().length === 0) {
    return null
  }

  return (
    <div style={{ 
      maxWidth: '900px',
      width: '100%',
      margin: '0 auto',
      marginTop: '24px',
      paddingTop: '0',
      paddingBottom: '0',
      paddingLeft: '14px',
      paddingRight: '14px',
      borderTop: 'none'
    }}>
      {/* Заголовок результата */}
      <div className="final-result-header">
        Результат
      </div>
      
      <div className="prose max-w-none final-result-prose"
        style={{ padding: '0', fontSize: '13px', marginTop: '12px' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

