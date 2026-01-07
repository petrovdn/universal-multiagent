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
      paddingLeft: '0',
      paddingRight: '0',
      borderTop: 'none'
    }}>
      <div className="prose max-w-none final-result-prose"
        style={{ padding: '0', fontSize: '13px' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}

