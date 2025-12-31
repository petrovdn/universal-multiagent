import React from 'react'
import { CheckCircle } from 'lucide-react'

interface FinalResultBlockProps {
  content: string
}

export function FinalResultBlock({ content }: FinalResultBlockProps) {
  if (!content || content.trim().length === 0) {
    return null
  }

  return (
    <div style={{ 
      padding: '15px', 
      margin: '10px', 
      background: '#d4edda', 
      border: '2px solid #28a745', 
      borderRadius: '8px' 
    }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '10px', 
        marginBottom: '15px' 
      }}>
        <CheckCircle style={{ width: '20px', height: '20px', color: '#28a745' }} />
        <strong style={{ color: '#28a745', fontSize: '18px' }}>Результат</strong>
      </div>
      <div style={{ 
        whiteSpace: 'pre-wrap', 
        fontSize: '14px', 
        color: '#333' 
      }}>
        {content}
      </div>
    </div>
  )
}

